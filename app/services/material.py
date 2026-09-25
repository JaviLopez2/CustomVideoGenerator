import base64
import gc
import io
import json
import math
import os
import random
import re
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, List
from urllib.parse import quote_plus, urlencode, urlsplit, urlunsplit

import requests
import numpy as np
from loguru import logger
from moviepy.video.io.VideoFileClip import VideoFileClip
from PIL import Image, ImageDraw, ImageStat, UnidentifiedImageError

from app.config import config
from app.models.schema import MaterialInfo, VideoAspect, VideoConcatMode
from app.services import (
    material_cache,
    metaso_minimax,
    ofox,
    task_artifacts,
    video,
    volcengine_seedance,
)
from app.utils import utils

# Thread-safe counter for API key rotation
_api_key_counter = 0
_api_key_lock = threading.Lock()

# Lazy, process-wide rembg session for precision-scene foreground extraction.
# Kept optional so MoneyPrinterTurbo can still run if the extra dependency is absent.
_precision_rembg_session: Any | None = None
_precision_rembg_session_model = ""
_precision_rembg_session_lock = threading.Lock()

# Florence-2 is loaded lazily only while precision candidates are judged.
# Default device is CPU to avoid competing with FLUX/ComfyUI for the user's GPU VRAM.
_precision_semantic_model: Any | None = None
_precision_semantic_processor: Any | None = None
_precision_semantic_model_name_loaded = ""
_precision_semantic_device_loaded = ""
_precision_semantic_lock = threading.Lock()


class _OpenAIImageDecodeError(ValueError):
    """表示兼容接口返回的字节无法解码为图片，不包含本地文件写入故障。"""


def _safe_public_url(value: Any) -> str | None:
    """
    只保留可公开展示的 HTTP(S) 页面地址，并移除查询参数和凭据。

    素材下载地址可能携带 API Key、签名 JWT 或临时 token。任务清单只需要
    帮助用户回到供应商的公开素材页，不应保存鉴权参数；用户信息形式的 URL
    同样拒绝，避免 ``https://user:pass@example.com`` 一类内容落盘。
    """
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _creator_info(value: Any) -> dict[str, str] | None:
    """从不同供应商的作者结构中提取统一的公开字段。"""
    if isinstance(value, str) and value.strip():
        return {"name": value.strip()}
    if not isinstance(value, dict):
        return None

    creator: dict[str, str] = {}
    creator_id = value.get("id")
    creator_name = value.get("name") or value.get("username")
    creator_page = _safe_public_url(
        value.get("url") or value.get("profile_url") or value.get("profile_page")
    )
    if creator_id is not None:
        creator["id"] = str(creator_id)
    if creator_name:
        creator["name"] = str(creator_name)
    if creator_page:
        creator["profile_page"] = creator_page
    return creator or None


def _material_source_record(item: MaterialInfo, local_path: str) -> dict[str, Any]:
    """
    为成功下载的素材生成轻量来源记录。

    ``source_info`` 可能来自缓存，甚至来自外部构造的 ``MaterialInfo``，因此
    不能原样写入。这里按白名单重新构造，只保留公开页面、业务标识和尺寸，
    并只记录本地文件名，避免用户目录或 Docker 挂载路径进入任务文件。
    """
    source = item.source_info if isinstance(item.source_info, dict) else {}
    record: dict[str, Any] = {
        "provider": str(item.provider or source.get("provider") or ""),
        "local_file": Path(local_path).name,
        "duration": int(item.duration),
    }

    search_term = source.get("search_term")
    asset_id = source.get("asset_id")
    source_page = _safe_public_url(source.get("source_page"))
    if isinstance(search_term, str) and search_term.strip():
        record["search_term"] = search_term.strip()
    if asset_id not in (None, ""):
        record["asset_id"] = str(asset_id)
    if source_page:
        record["source_page"] = source_page

    creator = _creator_info(source.get("creator"))
    if creator:
        record["creator"] = creator

    raw_rendition = source.get("rendition")
    if isinstance(raw_rendition, dict):
        rendition = {}
        for field in ("id", "width", "height"):
            value = raw_rendition.get(field)
            if value not in (None, ""):
                rendition[field] = str(value) if field == "id" else value
        if rendition:
            record["rendition"] = rendition

    # Precision validation metadata is local diagnostic data: scores, captions and
    # decisions only. Preserve it so later tests can compare good/bad generations.
    precision_selection = source.get("precision_candidate_selection")
    if isinstance(precision_selection, dict):
        record["precision_candidate_selection"] = precision_selection
    return record


def _persist_material_sources(
    task_id: str,
    material_sources: list[dict[str, Any]],
) -> None:
    """
    将当前实际下载成功的素材来源补充到任务清单。

    任务记录是辅助能力，不能改变视频下载函数的返回值，也不能因为写盘失败
    中断成片主流程。``patch_script_data`` 会负责原子替换和异常日志；这里仅在
    成功后记录数量，便于确认任务追溯信息是否已经落盘。
    """
    try:
        saved = task_artifacts.patch_script_data(
            task_id,
            material_sources=material_sources,
        )
        if saved:
            logger.info(
                f"saved material source records: "
                f"task_id={task_id}, count={len(material_sources)}"
            )
    except Exception as exc:
        # task_artifacts 自身已经按失败降级设计，这里仍保留最后一道隔离，
        # 防止未来实现调整或目录解析异常意外影响素材下载返回值。
        logger.warning(
            "failed to persist material source records: "
            f"task_id={task_id}, error={type(exc).__name__}, detail={exc}"
        )



def _precision_diagnostics_enabled() -> bool:
    value = config.app.get("openai_image_precision_diagnostics_enabled", True)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _precision_diagnostics_copy_images_enabled() -> bool:
    """Copy candidate images only in Quality mode; JSON diagnostics stay available."""
    if _openai_image_performance_profile() != "quality":
        return False
    value = config.app.get(
        "openai_image_precision_diagnostics_copy_images_enabled",
        True,
    )
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)

def _precision_diagnostics_file(task_id: str) -> Path:
    return Path(utils.task_dir(task_id)) / "precision_diagnostics.json"


def _precision_diagnostics_json_safe(value: Any) -> Any:
    """Convert local diagnostic metadata into a JSON-safe representation."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return value.name
    if isinstance(value, dict):
        return {
            str(key): _precision_diagnostics_json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_precision_diagnostics_json_safe(item) for item in value]
    return str(value)


def _precision_diagnostics_reference_info(
    reference_info: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(reference_info, dict):
        return {}

    result: dict[str, Any] = {}
    for key in (
        "provider",
        "subject",
        "title",
        "source_page",
        "image_url",
        "license",
        "artist",
        "width",
        "height",
        "query",
        "comfyui_input",
        "manual_reference_mode",
        "reference_pack",
        "reference_selection",
        "reference_preparation",
    ):
        if key in reference_info:
            result[key] = _precision_diagnostics_json_safe(reference_info.get(key))

    for source_key, output_key in (
        ("local_path", "local_file"),
        ("original_local_path", "original_local_file"),
    ):
        value = reference_info.get(source_key)
        if value:
            result[output_key] = Path(str(value)).name

    return result


def _precision_diagnostics_copy_file(
    *,
    task_id: str,
    source_path: str,
    target_stem: str,
) -> str:
    """Copy a diagnostic image into the task folder using a stable readable name."""
    if not _precision_diagnostics_copy_images_enabled():
        return Path(str(source_path)).name if source_path else ""

    source = Path(str(source_path))
    if not source.is_file():
        return source.name if source_path else ""

    task_dir = Path(utils.task_dir(task_id))
    task_dir.mkdir(parents=True, exist_ok=True)

    suffix = source.suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        suffix = ".png"

    target = task_dir / f"{target_stem}{suffix}"
    try:
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        return target.name
    except Exception as exc:
        logger.warning(
            "failed to copy precision diagnostic image: "
            f"source={source.name!r}, target={target.name!r}, "
            f"error={type(exc).__name__}, detail={exc}"
        )
        return source.name


def _precision_diagnostics_persist(
    task_id: str,
    diagnostics: dict[str, Any],
) -> None:
    """Atomically persist precision diagnostics without affecting video generation."""
    if not _precision_diagnostics_enabled():
        return

    try:
        task_dir = Path(utils.task_dir(task_id))
        task_dir.mkdir(parents=True, exist_ok=True)
        target = _precision_diagnostics_file(task_id)
        temporary = target.with_suffix(".json.tmp")

        payload = _precision_diagnostics_json_safe(diagnostics)
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, target)
    except Exception as exc:
        logger.warning(
            "failed to persist precision diagnostics: "
            f"task_id={task_id}, error={type(exc).__name__}, detail={exc}"
        )


def _precision_diagnostics_scene_record(
    *,
    task_id: str,
    scene_index: int,
    prompt: str,
    route: str,
    duration: float,
    canonical_subject: str,
    required_features: list[str],
    forbidden_features: list[str],
    reference_info: dict[str, Any] | None,
    reference_need: str = "",
    reference_query: str = "",
    shot_type: str = "",
    framing_intent: str = "",
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "scene": int(scene_index) + 1,
        "route": str(route),
        "duration": round(float(duration), 3),
        "canonical_subject": str(canonical_subject or ""),
        "prompt": str(prompt or ""),
        "required_features": list(required_features or []),
        "forbidden_features": list(forbidden_features or []),
        "reference_need": str(reference_need or ""),
        "reference_query": str(reference_query or ""),
        "shot_type": str(shot_type or ""),
        "framing_intent": str(framing_intent or ""),
        "reference": _precision_diagnostics_reference_info(reference_info),
        "candidates": [],
        "selection": {},
        "status": "initialized",
    }

    if isinstance(reference_info, dict):
        reference_path = str(
            reference_info.get("local_path")
            or reference_info.get("original_local_path")
            or ""
        )
        if reference_path:
            record["reference"]["diagnostic_file"] = (
                _precision_diagnostics_copy_file(
                    task_id=task_id,
                    source_path=reference_path,
                    target_stem="precision_reference",
                )
            )

    return record


def _precision_diagnostics_add_candidate(
    *,
    task_id: str,
    scene_record: dict[str, Any],
    candidate: MaterialInfo,
    candidate_index: int,
) -> None:
    image_path = str(candidate.url or "")
    scene_number = int(scene_record.get("scene") or 0)
    diagnostic_file = _precision_diagnostics_copy_file(
        task_id=task_id,
        source_path=image_path,
        target_stem=f"candidate_scene_{scene_number:02d}_{candidate_index:02d}",
    )

    entry = {
        "index": int(candidate_index),
        "original_file": Path(image_path).name if image_path else "",
        "diagnostic_file": diagnostic_file,
    }

    source = candidate.source_info if isinstance(candidate.source_info, dict) else {}
    if source.get("model"):
        entry["model"] = str(source.get("model"))
    if source.get("route"):
        entry["route"] = str(source.get("route"))

    candidates = scene_record.setdefault("candidates", [])
    # Replace a matching index instead of duplicating it when partial diagnostics
    # are updated after a later phase.
    for existing_index, existing in enumerate(candidates):
        if isinstance(existing, dict) and existing.get("index") == int(candidate_index):
            candidates[existing_index] = entry
            return
    candidates.append(entry)


def _precision_diagnostics_finalize_scene(
    *,
    scene_record: dict[str, Any],
    candidate_items: list[MaterialInfo],
    selected_item: MaterialInfo | None,
    stop_reason: str,
) -> None:
    selection = _precision_selection_metadata(selected_item)
    scene_record["selection"] = _precision_diagnostics_json_safe(selection)
    scene_record["adaptive_stop_reason"] = str(stop_reason or "")

    selected_index = selection.get("selected_index")
    try:
        selected_index = int(selected_index)
    except (TypeError, ValueError):
        selected_index = None

    scene_record["selected_index"] = selected_index
    if selected_item is not None:
        scene_record["selected_original_file"] = Path(
            str(selected_item.url or "")
        ).name

    # Merge the detailed per-candidate score/caption/judgment records produced by
    # V5 into the readable candidate entries.
    score_rows = selection.get("scores")
    if isinstance(score_rows, list):
        by_index = {
            int(row.get("index")): row
            for row in score_rows
            if isinstance(row, dict)
            and str(row.get("index") or "").isdigit()
        }
        for candidate in scene_record.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            idx = candidate.get("index")
            if idx in by_index:
                candidate["evaluation"] = _precision_diagnostics_json_safe(
                    by_index[idx]
                )

    if selected_index is not None:
        for candidate in scene_record.get("candidates", []):
            if (
                isinstance(candidate, dict)
                and candidate.get("index") == selected_index
            ):
                candidate["selected"] = True
                scene_record["selected_diagnostic_file"] = candidate.get(
                    "diagnostic_file"
                )
            elif isinstance(candidate, dict):
                candidate["selected"] = False

    scene_record["status"] = str(selection.get("status") or "completed")
    scene_record["reason"] = str(selection.get("reason") or "")



def _get_tls_verify() -> bool:
    # 默认开启 TLS 证书校验，防止素材搜索和下载过程被中间人篡改。
    # 仅在企业代理、自签证书等明确需要的场景下，允许用户通过
    # `config.toml` 显式设置 `tls_verify = false` 临时关闭。
    tls_verify = config.app.get("tls_verify", True)
    if isinstance(tls_verify, str):
        tls_verify = tls_verify.strip().lower() not in ("0", "false", "no", "off")

    if not tls_verify:
        logger.warning(
            "TLS certificate verification is disabled by config.app.tls_verify=false. "
            "Only use this in trusted proxy environments."
        )

    return bool(tls_verify)


def get_api_key(cfg_key: str):
    api_keys = config.app.get(cfg_key)
    if not api_keys:
        raise ValueError(
            f"\n\n##### {cfg_key} is not set #####\n\n"
            f"Please set it in the config.toml file: {config.config_file}\n"
        )

    # if only one key is provided, return it
    if isinstance(api_keys, str):
        return api_keys

    global _api_key_counter
    with _api_key_lock:
        _api_key_counter += 1
        return api_keys[_api_key_counter % len(api_keys)]


def _redact_secret(message: str, secret: str) -> str:
    """
    对即将写入日志的异常文本做最小范围脱敏。

    requests 的连接异常可能包含完整请求 URL，而 Pixabay API Key 通过查询
    参数传递。这里同时替换原始值和 URL 编码值，既保留网络错误信息用于排查，
    又避免密钥进入日志文件。
    """
    safe_message = str(message)
    if not secret:
        return safe_message

    safe_message = safe_message.replace(secret, "***")
    encoded_secret = quote_plus(secret)
    if encoded_secret != secret:
        safe_message = safe_message.replace(encoded_secret, "***")
    return safe_message


def _redact_request_error(error: Exception, *secrets: str) -> str:
    """
    保留网络异常的可排查信息，同时移除 API Key 和代理凭据。

    直接只记录异常类型会丢失 DNS、证书、超时等关键上下文；直接记录原始异常
    又可能回显完整请求 URL。统一入口可以让三个素材供应商使用相同脱敏规则。
    """
    safe_message = str(error)
    for secret in secrets:
        safe_message = _redact_secret(safe_message, str(secret or ""))
    for proxy_url in config.proxy.values():
        safe_message = _redact_secret(safe_message, str(proxy_url))
    return safe_message


def _is_cloudflare_challenge(response: requests.Response) -> bool:
    """
    识别 Cloudflare 返回的 HTML Challenge，而不是把它当成 Pixabay JSON。

    Cloudflare 通常会设置 `cf-mitigated: challenge`；部分部署只返回带有
    "Just a moment" 或 challenge-platform 的 HTML，因此保留内容特征兜底。
    响应正文仅在内存中判断，不写入日志，避免记录无价值的大段 HTML。
    """
    headers = getattr(response, "headers", {}) or {}
    if str(headers.get("cf-mitigated", "")).lower() == "challenge":
        return True

    content_type = str(headers.get("content-type", "")).lower()
    if "text/html" not in content_type:
        return False

    body = str(getattr(response, "text", "")).lower()
    return "just a moment" in body or "/cdn-cgi/challenge-platform/" in body


def _matches_video_aspect(
    width: Any,
    height: Any,
    video_aspect: VideoAspect,
    *,
    is_vertical: Any = None,
) -> bool:
    """
    判断远端素材是否与目标画面方向一致。

    Pexels、Pixabay 和 Coverr 的响应字段并不统一，因此先使用宽高做可靠判断；
    Coverr 部分历史响应缺少尺寸时，再使用明确的 ``is_vertical`` 布尔值兜底。
    无法确认方向的素材直接跳过，避免竖屏任务混入横屏素材并在成片中产生黑边。
    """
    aspect = VideoAspect(video_aspect)
    try:
        normalized_width = int(float(width))
        normalized_height = int(float(height))
    except (TypeError, ValueError):
        normalized_width = 0
        normalized_height = 0

    if normalized_width > 0 and normalized_height > 0:
        if aspect == VideoAspect.portrait:
            return normalized_height > normalized_width
        if aspect == VideoAspect.landscape:
            return normalized_width > normalized_height
        return normalized_width == normalized_height

    if isinstance(is_vertical, bool) and aspect != VideoAspect.square:
        return is_vertical == (aspect == VideoAspect.portrait)
    return False


def _filter_materials_by_aspect(
    items: List[MaterialInfo],
    video_aspect: VideoAspect,
) -> List[MaterialInfo]:
    """
    对缓存结果再次校验方向。

    素材搜索缓存最长保留 24 小时，升级前写入的缓存可能包含方向不匹配的素材。
    在统一缓存入口过滤可以让修复立即生效，也能防御第三方 Provider 或旧缓存
    遗漏远端筛选。无法读取 rendition 尺寸的旧条目按未验证处理并跳过。
    """
    aspect = VideoAspect(video_aspect)
    if aspect == VideoAspect.square:
        # Pixabay 和 Coverr 很少提供原生方形素材。方形输出沿用既有行为，
        # 接受可用候选并交给视频合成阶段裁剪，避免升级后 1:1 任务无素材。
        return list(items)

    filtered_items = []
    for item in items:
        source_info = item.source_info if isinstance(item.source_info, dict) else {}
        rendition = source_info.get("rendition")
        rendition = rendition if isinstance(rendition, dict) else {}
        if _matches_video_aspect(
            rendition.get("width"),
            rendition.get("height"),
            aspect,
        ):
            filtered_items.append(item)
    return filtered_items


def search_videos_pexels(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    aspect = VideoAspect(video_aspect)
    video_orientation = aspect.name
    video_width, video_height = aspect.to_resolution()
    api_key = get_api_key("pexels_api_keys")
    headers = {
        "Authorization": api_key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    }
    # Build URL
    params = {"query": search_term, "per_page": 20, "orientation": video_orientation}
    query_url = f"https://api.pexels.com/v1/videos/search?{urlencode(params)}"
    logger.info(f"searching videos on pexels: term={search_term!r}")

    try:
        r = requests.get(
            query_url,
            headers=headers,
            proxies=config.proxy,
            verify=_get_tls_verify(),
            timeout=(30, 60),
        )
        response = r.json()
        video_items = []
        if "videos" not in response:
            logger.error("pexels video search returned an unsupported response")
            return video_items
        videos = response["videos"]
        # loop through each video in the result
        for v in videos:
            duration = v["duration"]
            # check if video has desired minimum duration
            if duration < minimum_duration:
                continue
            video_files = v["video_files"]
            # loop through each url to determine the best quality
            for video in video_files:
                w = int(video["width"])
                h = int(video["height"])
                if (
                    _matches_video_aspect(w, h, aspect)
                    and w == video_width
                    and h == video_height
                ):
                    item = MaterialInfo()
                    item.provider = "pexels"
                    item.url = video["link"]
                    item.duration = duration
                    item.source_info = {
                        "provider": "pexels",
                        "search_term": search_term,
                        "asset_id": (
                            str(v.get("id")) if v.get("id") is not None else None
                        ),
                        "source_page": _safe_public_url(v.get("url")),
                        "creator": _creator_info(v.get("user")),
                        "rendition": {
                            "id": (
                                str(video.get("id"))
                                if video.get("id") is not None
                                else None
                            ),
                            "width": w,
                            "height": h,
                        },
                    }
                    video_items.append(item)
                    break
        return video_items
    except Exception as e:
        logger.error(
            "pexels video search failed: "
            f"error={type(e).__name__}, detail={_redact_request_error(e, api_key)}"
        )

    return []


def search_videos_pixabay(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    aspect = VideoAspect(video_aspect)

    video_width, video_height = aspect.to_resolution()

    api_key = get_api_key("pixabay_api_keys")
    # Build URL
    params = {
        "q": search_term,
        "video_type": "all",  # Accepted values: "all", "film", "animation"
        "per_page": 50,
        "key": api_key,
    }
    query_url = f"https://pixabay.com/api/videos/?{urlencode(params)}"
    logger.info(
        f"searching videos on pixabay: term={search_term!r}, "
        f"proxy_enabled={bool(config.proxy)}"
    )

    try:
        r = requests.get(
            query_url, proxies=config.proxy, verify=_get_tls_verify(), timeout=(30, 60)
        )
        status_code = int(getattr(r, "status_code", 200))
        headers = getattr(r, "headers", {}) or {}
        content_type = str(headers.get("content-type", ""))
        retry_after = headers.get("retry-after")
        cf_ray = headers.get("cf-ray")

        if _is_cloudflare_challenge(r):
            logger.error(
                "pixabay search was blocked by a Cloudflare challenge: "
                f"status={status_code}, cf_ray={cf_ray or 'unknown'}. "
                "Check the server network or proxy, or use Pexels/Coverr instead."
            )
            return []

        if status_code == 429:
            logger.error(
                "pixabay API rate limit exceeded: "
                f"status=429, retry_after={retry_after or 'unknown'}"
            )
            return []

        if status_code >= 400:
            logger.error(
                "pixabay search request failed: "
                f"status={status_code}, content_type={content_type or 'unknown'}"
            )
            return []

        try:
            response = r.json()
        except ValueError:
            logger.error(
                "pixabay returned an unexpected non-JSON response: "
                f"status={status_code}, content_type={content_type or 'unknown'}"
            )
            return []

        video_items = []
        if "hits" not in response:
            logger.error("pixabay video search returned an unsupported response")
            return video_items
        videos = response["hits"]
        # loop through each video in the result
        for v in videos:
            duration = v["duration"]
            # check if video has desired minimum duration
            if duration < minimum_duration:
                continue
            video_files = v["videos"]
            # loop through each url to determine the best quality
            for video_type in video_files:
                video = video_files[video_type]
                try:
                    w = int(video["width"])
                    h = int(video["height"])
                except (KeyError, TypeError, ValueError):
                    continue
                # Pixabay 很少返回原生方形视频；1:1 输出继续接受满足分辨率的
                # 候选并由合成阶段裁剪。横竖屏则必须严格匹配目标方向。
                orientation_matches = aspect == VideoAspect.square or (
                    _matches_video_aspect(w, h, aspect)
                )
                if orientation_matches and w >= video_width:
                    item = MaterialInfo()
                    item.provider = "pixabay"
                    item.url = video["url"]
                    item.duration = duration
                    item.source_info = {
                        "provider": "pixabay",
                        "search_term": search_term,
                        "asset_id": (
                            str(v.get("id")) if v.get("id") is not None else None
                        ),
                        "source_page": _safe_public_url(v.get("pageURL")),
                        "creator": _creator_info(
                            {
                                "id": v.get("user_id"),
                                "name": v.get("user"),
                            }
                        ),
                        "rendition": {
                            "id": video_type,
                            "width": w,
                            "height": video.get("height"),
                        },
                    }
                    video_items.append(item)
                    break
        return video_items
    except Exception as e:
        error_message = _redact_request_error(e, api_key)
        logger.error(
            "pixabay search request failed: "
            f"error={type(e).__name__}, detail={error_message}"
        )

    return []


def search_videos_coverr(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    """
    Coverr (https://coverr.co) - free HD/4K stock videos,
    subject to Coverr license terms (https://coverr.co/license).

    Coverr API notes (based on official docs at api.coverr.co/docs/):
      - 鉴权: Authorization: Bearer <api_key>
      - 搜索端点: GET /videos?query=...,响应结构 {"hits": [...], ...}
      - 加 ?urls=true 在搜索响应里直接返回 mp4 直链
      - URL 是 signed JWT(绑定 API key,无过期时间)
      - Coverr 支持通过 filter=is_vertical:true/false 筛选横竖屏素材；
        响应返回后仍根据 max_width/max_height 或 is_vertical 做本地校验
      - duration 字段同时存在 number 和 string 两种形态,本函数都接受

    本函数使用 urls.mp4_download 字段作为下载地址 —— 按 Coverr 官方文档
    (https://api.coverr.co/docs/videos/#download-a-video) 的说法,
    GET 这个 URL 本身就被 Coverr 当作一次合法的 download 事件计入统计,
    无需再调用 PATCH /videos/:id/stats/downloads。
    """
    aspect = VideoAspect(video_aspect)
    api_key = get_api_key("coverr_api_keys")
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {
        "query": search_term,
        "page_size": 20,
        "urls": "true",
        "sort": "popular",
    }
    # 服务端方向筛选可以直接从完整搜索结果中返回目标素材，避免先取热门结果再
    # 本地过滤导致竖屏候选为空。方形素材没有对应布尔条件，继续依赖本地宽高校验。
    if aspect == VideoAspect.portrait:
        params["filter"] = "is_vertical:true"
    elif aspect == VideoAspect.landscape:
        params["filter"] = "is_vertical:false"
    query_url = f"https://api.coverr.co/videos?{urlencode(params)}"
    logger.info(f"searching videos on coverr: term={search_term!r}")

    try:
        r = requests.get(
            query_url,
            headers=headers,
            proxies=config.proxy,
            verify=_get_tls_verify(),
            timeout=(30, 60),
        )
        response = r.json()
        video_items: List[MaterialInfo] = []

        if not isinstance(response, dict) or "hits" not in response:
            logger.error("coverr video search returned an unsupported response")
            return video_items

        for v in response["hits"]:
            # duration 在不同响应里可能是 number(11.625) 或 string("10.500000")
            try:
                duration = int(float(v.get("duration") or 0))
            except (TypeError, ValueError):
                continue
            if duration < minimum_duration:
                continue

            video_id = v.get("id")
            mp4_download_url = (v.get("urls") or {}).get("mp4_download")
            if not video_id or not mp4_download_url:
                continue
            if aspect != VideoAspect.square and not _matches_video_aspect(
                v.get("max_width"),
                v.get("max_height"),
                aspect,
                is_vertical=v.get("is_vertical"),
            ):
                continue

            item = MaterialInfo()
            item.provider = "coverr"
            item.url = mp4_download_url
            item.duration = duration
            item.source_info = {
                "provider": "coverr",
                "search_term": search_term,
                "asset_id": str(video_id),
                "source_page": _safe_public_url(v.get("canonical_url") or v.get("url")),
                "creator": _creator_info(v.get("creator") or v.get("author")),
                "rendition": {
                    "id": "mp4_download",
                    "width": v.get("max_width"),
                    "height": v.get("max_height"),
                },
            }
            video_items.append(item)
        return video_items
    except Exception as e:
        logger.error(
            "coverr video search failed: "
            f"error={type(e).__name__}, detail={_redact_request_error(e, api_key)}"
        )

    return []


# WaveSpeed AI (https://wavespeed.ai) 通过文生视频模型按脚本关键词直接生成素材，
# 与三个库存素材源共用 MaterialInfo 结果结构和后续下载、剪辑流程。
WAVESPEED_API_BASE_URL = "https://api.wavespeed.ai/api/v3"
WAVESPEED_DEFAULT_T2V_MODEL = "bytedance/seedance-2.0-fast/text-to-video"
WAVESPEED_POLL_INTERVAL_SECONDS = 2.0
WAVESPEED_RUN_TIMEOUT_SECONDS = 600.0
# 默认模型 bytedance/seedance-2.0-fast/text-to-video 只接受 4-15 秒；超出
# 范围的请求会被 API 直接拒绝。WebUI 默认片段时长是 3 秒，因此必须在提交
# 前收敛到模型支持区间，多出的时长由现有剪辑流程按片段时长裁掉。
WAVESPEED_MIN_DURATION_SECONDS = 4
WAVESPEED_MAX_DURATION_SECONDS = 15
# 三个失败态语义不同（模型报错 / 用户取消 / 平台超时），但对素材流程都意味着
# 本关键词没有产物，统一按空结果处理，交给上层跳过该片段继续生成。
WAVESPEED_FAILURE_STATUSES = frozenset({"failed", "cancelled", "timeout"})
# 与 WaveSpeed 官方 Python SDK / n8n 节点保持同一口径：429 与 5xx 属于临时
# 故障，值得有限次退避重试；4xx 是明确的客户端错误，快速失败。
WAVESPEED_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
# 单次轮询允许的连续临时失败次数。一次不走运的 GET 不能让已经计费的任务失联。
WAVESPEED_MAX_POLL_RETRIES = 5
# 线性退避基数，第 n 次重试等待 base * n 秒。
WAVESPEED_RETRY_BASE_SECONDS = 1.0
# 产物下载失败时对同一个签名地址的重试次数。素材已经付费生成，优先重试原
# 地址，不能因为一次下载抖动就重新提交一次付费生成任务。
WAVESPEED_MAX_DOWNLOAD_RETRIES = 2


class WaveSpeedUnconfirmedTaskError(RuntimeError):
    """
    付费生成任务已提交，但最终状态无法在本地确认。

    这类异常绝不等价于“该任务失败、可以重来”：远端任务可能仍在运行或已经
    完成并计费。素材流程必须就此停止，不再为后续关键词提交新的付费任务，
    并把已提交的 prediction id 留在日志中供人工找回。
    """

    def __init__(self, message: str, prediction_id: str = ""):
        super().__init__(message)
        self.prediction_id = prediction_id


def _wavespeed_status_code(response: Any) -> int:
    """读取响应状态码；测试替身或异常对象缺少该字段时按 200 处理。"""
    try:
        return int(getattr(response, "status_code", 200))
    except (TypeError, ValueError):
        return 200


def _is_wavespeed_retryable_error(error: Exception) -> bool:
    """
    判断轮询异常是否值得重试。

    连接、超时一类网络异常没有状态码，按临时故障处理；带状态码的响应只在
    429 和 5xx 时重试，与官方 SDK 的重试集合保持一致。
    """
    if isinstance(
        error,
        (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
        ),
    ):
        return True
    response = getattr(error, "response", None)
    if response is not None:
        return _wavespeed_status_code(response) in WAVESPEED_RETRYABLE_STATUS_CODES
    return False


def _wavespeed_duration_bounds() -> tuple[int, int]:
    """
    返回当前模型支持的生成时长区间（秒）。

    默认区间对应默认 Seedance 模型；用户切换到其它文生视频模型时，可以在
    配置中同步调整区间。任何异常配置都退回默认值，并保证 min <= max，
    避免把用户输入变成必然失败的远端请求。
    """

    def read_bound(key: str, fallback: int) -> int:
        try:
            value = int(config.app.get(key, fallback))
        except (TypeError, ValueError):
            return fallback
        return value if value >= 1 else fallback

    min_duration = read_bound("wavespeed_min_duration", WAVESPEED_MIN_DURATION_SECONDS)
    max_duration = read_bound("wavespeed_max_duration", WAVESPEED_MAX_DURATION_SECONDS)
    return min_duration, max(max_duration, min_duration)


def generate_videos_wavespeed(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
) -> List[MaterialInfo]:
    """
    用 WaveSpeed 文生视频模型为一个脚本关键词生成一段素材。

    与库存素材源的 search_videos_* 保持同一签名和空列表失败约定，
    使其可以直接接入 ``download_videos`` 的通用下载与时长核算流程。
    ``minimum_duration`` 在生成语境下就是目标片段时长（秒）。
    """
    aspect = VideoAspect(video_aspect)
    video_width, video_height = aspect.to_resolution()
    api_key = get_api_key("wavespeed_api_keys")
    model_id = (
        str(
            config.app.get("wavespeed_text_to_video_model", "")
            or WAVESPEED_DEFAULT_T2V_MODEL
        )
        .strip()
        .strip("/")
    )
    headers = {"Authorization": f"Bearer {api_key}"}
    requested_duration = max(int(minimum_duration), 1)
    min_duration, max_duration = _wavespeed_duration_bounds()
    duration = min(max(requested_duration, min_duration), max_duration)
    if duration != requested_duration:
        # 生成比请求更长不会影响成片：剪辑流程仍按片段时长裁剪；生成比请求
        # 更短的情况只发生在请求超过模型上限时，此时也只能收敛到上限。
        logger.info(
            f"wavespeed clip duration clamped to model-supported range: "
            f"requested={requested_duration}s, using={duration}s "
            f"(supported {min_duration}-{max_duration}s)"
        )
    payload = {
        "prompt": search_term,
        "aspect_ratio": aspect.value,
        "duration": duration,
    }
    logger.info(
        f"generating video on wavespeed: model={model_id}, "
        f"term={search_term!r}, duration={duration}s"
    )

    # 提交 POST 绝不自动重试：请求可能已经在远端创建了付费任务，重发会造成
    # 重复生成和重复扣费（与官方 SDK 的 submission 策略一致）。
    try:
        submit_response = requests.post(
            f"{WAVESPEED_API_BASE_URL}/{model_id}",
            json=payload,
            headers=headers,
            proxies=config.proxy,
            verify=_get_tls_verify(),
            timeout=(30, 60),
        )
    except Exception as e:
        # 没有收到响应并不代表任务没有创建。此时状态不明，必须终止整个生成
        # 流程，而不是继续为下一个关键词提交新的付费任务。
        raise WaveSpeedUnconfirmedTaskError(
            "wavespeed submission did not return a response, the task may "
            "already exist remotely: "
            f"error={type(e).__name__}, detail={_redact_request_error(e, api_key)}"
        ) from e

    submit_status = _wavespeed_status_code(submit_response)
    if submit_status >= 500:
        # 5xx 可能发生在任务创建之后，无法判断是否已经计费。
        raise WaveSpeedUnconfirmedTaskError(
            f"wavespeed submission failed with HTTP {submit_status}, "
            "the task may already exist remotely"
        )
    try:
        submit_body = submit_response.json()
    except Exception as e:
        raise WaveSpeedUnconfirmedTaskError(
            "wavespeed submission returned an unreadable response, the task "
            f"may already exist remotely: error={type(e).__name__}"
        ) from e

    submit_data = submit_body.get("data") if isinstance(submit_body, dict) else None
    if not isinstance(submit_body, dict) or submit_body.get("code") != 200:
        # 4xx 与业务错误码是明确的拒绝，远端没有创建任务，也就不存在重复
        # 计费风险，按现有素材源约定返回空结果并继续。
        logger.error(
            "wavespeed video generation request rejected: "
            f"http_status={submit_status}, "
            f"code={submit_body.get('code') if isinstance(submit_body, dict) else None}, "
            f"detail={_redact_secret(str((submit_body or {}).get('message') or ''), api_key)}"
        )
        return []
    prediction_id = (
        str(submit_data.get("id") or "") if isinstance(submit_data, dict) else ""
    )
    if not prediction_id:
        # 提交被接受但没拿到 ID：任务可能已经存在却无法追踪，不能继续下单。
        raise WaveSpeedUnconfirmedTaskError(
            "wavespeed accepted the submission without returning a prediction id"
        )
    # 生成任务提交成功即产生远端计费副作用，先落日志记录任务 ID，
    # 即使后续轮询失败，用户仍能凭 ID 在 WaveSpeed 控制台找回产物。
    logger.info(f"wavespeed prediction created: id={prediction_id}")

    result_data = _wait_for_wavespeed_prediction(
        prediction_id=prediction_id,
        headers=headers,
        api_key=api_key,
    )
    if result_data is None:
        return []

    try:
        video_items = []
        outputs = result_data.get("outputs")
        for output in outputs if isinstance(outputs, list) else []:
            # 产物 URL 是带签名的临时下载地址，必须整体保留（不能剥离查询参
            # 数），因此不写入 source_info，只用于随后的立即下载。
            if not isinstance(output, str) or not output.startswith(
                ("http://", "https://")
            ):
                continue
            item = MaterialInfo()
            item.provider = "wavespeed"
            item.url = output
            item.duration = duration
            item.source_info = {
                "provider": "wavespeed",
                "search_term": search_term,
                "asset_id": prediction_id,
                "rendition": {
                    "id": None,
                    "width": video_width,
                    "height": video_height,
                },
            }
            video_items.append(item)
        if not video_items:
            logger.error(
                "wavespeed prediction completed without downloadable outputs: "
                f"id={prediction_id}"
            )
        return video_items
    except Exception as e:
        # 产物已经生成并计费，这里的异常只可能来自本地解析。记录后按空结果
        # 返回，让上层跳过该片段，但任务状态本身是确定的，可以继续后续片段。
        logger.error(
            "wavespeed output parsing failed: "
            f"id={prediction_id}, error={type(e).__name__}, "
            f"detail={_redact_request_error(e, api_key)}"
        )

    return []


def _wait_for_wavespeed_prediction(
    *,
    prediction_id: str,
    headers: dict,
    api_key: str,
) -> dict | None:
    """
    轮询同一个 prediction id 直到出现确定结果。

    返回 ``completed`` 的 data；远端明确失败（failed / cancelled / timeout）
    时返回 None，表示该任务已经结束、可以安全地继续后续片段。临时故障按
    线性退避重试同一个 ID，绝不重新提交任务；状态始终无法确认时抛出
    :class:`WaveSpeedUnconfirmedTaskError`，由调用方终止整个生成流程。
    """
    deadline = time.monotonic() + WAVESPEED_RUN_TIMEOUT_SECONDS
    consecutive_failures = 0
    while True:
        try:
            response = requests.get(
                f"{WAVESPEED_API_BASE_URL}/predictions/{prediction_id}/result",
                headers=headers,
                proxies=config.proxy,
                verify=_get_tls_verify(),
                timeout=(30, 60),
            )
            status_code = _wavespeed_status_code(response)
            if status_code in WAVESPEED_RETRYABLE_STATUS_CODES:
                raise requests.exceptions.HTTPError(
                    f"HTTP {status_code}", response=response
                )
            result_body = response.json()
            result_data = (
                result_body.get("data") if isinstance(result_body, dict) else None
            )
            if not isinstance(result_body, dict) or result_body.get("code") != 200:
                # 轮询被明确拒绝（如 4xx）时任务状态仍然未知：任务已经提交，
                # 只是本地查不到结果，同样不能继续提交新的付费任务。
                raise WaveSpeedUnconfirmedTaskError(
                    "wavespeed prediction status is unknown: "
                    f"http_status={status_code}, "
                    f"code={result_body.get('code') if isinstance(result_body, dict) else None}, "
                    f"detail={_redact_secret(str((result_body or {}).get('message') or ''), api_key)}",
                    prediction_id=prediction_id,
                )
            if not isinstance(result_data, dict):
                raise WaveSpeedUnconfirmedTaskError(
                    "wavespeed prediction result payload is malformed",
                    prediction_id=prediction_id,
                )
        except WaveSpeedUnconfirmedTaskError:
            raise
        except Exception as e:
            if not _is_wavespeed_retryable_error(e):
                raise WaveSpeedUnconfirmedTaskError(
                    "wavespeed prediction polling failed and the task state is "
                    f"unknown: error={type(e).__name__}, "
                    f"detail={_redact_request_error(e, api_key)}",
                    prediction_id=prediction_id,
                ) from e
            consecutive_failures += 1
            if consecutive_failures > WAVESPEED_MAX_POLL_RETRIES:
                raise WaveSpeedUnconfirmedTaskError(
                    "wavespeed prediction polling failed after "
                    f"{WAVESPEED_MAX_POLL_RETRIES + 1} attempts, the task may "
                    "still be running remotely: "
                    f"error={type(e).__name__}, "
                    f"detail={_redact_request_error(e, api_key)}",
                    prediction_id=prediction_id,
                ) from e
            delay = WAVESPEED_RETRY_BASE_SECONDS * consecutive_failures
            logger.warning(
                "wavespeed prediction polling hit a transient error, retry the "
                f"same task: id={prediction_id}, "
                f"attempt={consecutive_failures}/{WAVESPEED_MAX_POLL_RETRIES}, "
                f"error={type(e).__name__}, retry_in={delay:.1f}s"
            )
            time.sleep(delay)
            continue

        # 拿到一次有效响应就重置计数，只有连续失败才消耗重试额度。
        consecutive_failures = 0
        status = str(result_data.get("status") or "")
        if status == "completed":
            return result_data
        if status in WAVESPEED_FAILURE_STATUSES:
            logger.error(
                "wavespeed prediction did not produce a video: "
                f"id={prediction_id}, status={status}, "
                f"detail={_redact_secret(str(result_data.get('error') or ''), api_key)}"
            )
            return None
        if time.monotonic() > deadline:
            # 远端任务仍在执行，本地无法确认最终状态，必须停止继续下单。
            raise WaveSpeedUnconfirmedTaskError(
                f"wavespeed prediction is still {status or 'pending'} after "
                f"{WAVESPEED_RUN_TIMEOUT_SECONDS:.0f}s of local waiting",
                prediction_id=prediction_id,
            )
        time.sleep(WAVESPEED_POLL_INTERVAL_SECONDS)


def _save_generated_video_with_retry(
    video_url: str, save_dir: str, provider: str
) -> str:
    """
    下载已经付费生成的产物，失败时优先重试同一个地址。

    重新生成一次远端任务的代价是再付一次费，所以下载抖动必须先在原地址上
    做有限次退避重试，重试耗尽才放弃该片段。
    """
    for attempt in range(WAVESPEED_MAX_DOWNLOAD_RETRIES + 1):
        try:
            saved_video_path = save_video(video_url=video_url, save_dir=save_dir)
            if saved_video_path:
                return saved_video_path
            failure_detail = "empty result"
        except Exception as e:
            failure_detail = (
                f"error={type(e).__name__}, "
                f"detail={_redact_request_error(e, video_url)}"
            )
        if attempt >= WAVESPEED_MAX_DOWNLOAD_RETRIES:
            break
        delay = WAVESPEED_RETRY_BASE_SECONDS * (attempt + 1)
        logger.warning(
            "failed to download generated video, retry the same url: "
            f"provider={provider}, "
            f"attempt={attempt + 1}/{WAVESPEED_MAX_DOWNLOAD_RETRIES}, "
            f"{failure_detail}, retry_in={delay:.1f}s"
        )
        time.sleep(delay)
    logger.error(
        "failed to download generated video after "
        f"{WAVESPEED_MAX_DOWNLOAD_RETRIES + 1} attempts: "
        f"provider={provider}, {failure_detail}"
    )
    return ""


def save_video(video_url: str, save_dir: str = "") -> str:
    if not save_dir:
        save_dir = utils.storage_dir("cache_videos")

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    url_without_query = video_url.split("?")[0]
    url_hash = utils.md5(url_without_query)
    video_id = f"vid-{url_hash}"
    video_path = f"{save_dir}/{video_id}.mp4"

    # if video already exists, return the path
    if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        logger.info(f"video already exists: {video_path}")
        return video_path

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    # if video does not exist, download it
    with open(video_path, "wb") as f:
        f.write(
            requests.get(
                video_url,
                headers=headers,
                proxies=config.proxy,
                verify=_get_tls_verify(),
                timeout=(60, 240),
            ).content
        )

    if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        clip = None
        try:
            clip = VideoFileClip(video_path)
            duration = clip.duration
            fps = clip.fps
            if duration > 0 and fps > 0:
                return video_path
        except Exception as e:
            logger.warning(f"invalid video file: {video_path} => {str(e)}")
            try:
                os.remove(video_path)
            except Exception as remove_error:
                logger.warning(
                    f"failed to remove invalid video file: {video_path}, error: {str(remove_error)}"
                )
        finally:
            if clip is not None:
                try:
                    clip.close()
                except Exception as close_error:
                    logger.warning(
                        f"failed to close video clip: {video_path}, error: {str(close_error)}"
                    )
    return ""


# OpenAI 兼容文生图（Issue #1274）通过 /images/generations 协议为脚本关键词
# 生成图片素材，既可指向本地 ComfyUI/SD 网关，也可用于各类 OpenAI 协议中转
# 服务。生成的图片立即渲染成与 local 素材同款"缓慢放大"mp4 片段，对下游
# 剪辑流程完全透明。
OPENAI_IMAGE_ENDPOINT_PATH = "images/generations"
# OpenAI 官方图片接口只接受模型规定的尺寸，不能直接传视频分辨率（如 1080x1920）。
# 留空 openai_image_size 时按画幅取以下兼容默认值；本地网关可显式配置覆盖。
OPENAI_IMAGE_DEFAULT_SIZES = {
    VideoAspect.portrait: "1024x1536",
    VideoAspect.landscape: "1536x1024",
    VideoAspect.square: "1024x1024",
}
# 与 WaveSpeed 保持同一重试口径：429 与 5xx 属于临时故障，做有限次退避重试。
OPENAI_IMAGE_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
# 401/403 是当前 key 被明确拒绝。get_api_key 每次调用轮换 key，配置了多个
# key 时重试会自动换 key；只有一个 key 时快速失败，不做无意义重试。
OPENAI_IMAGE_KEY_ERROR_STATUS_CODES = frozenset({401, 403})
OPENAI_IMAGE_MAX_ATTEMPTS = 3
# 串行出图 + 线性退避，兼容中转服务普遍的限流恢复窗口。
OPENAI_IMAGE_RETRY_BACKOFF_SECONDS = (5, 15, 30)
# 同步生成接口可能需要数十秒才返回图片，读超时给足余量。
OPENAI_IMAGE_REQUEST_TIMEOUT = (30, 300)
# 图片已按张计费后的下载重试：优先重试原地址，而不是重新生成同一张图。
OPENAI_IMAGE_MAX_DOWNLOAD_ATTEMPTS = 3
OPENAI_IMAGE_DOWNLOAD_BACKOFF_SECONDS = 2


def is_openai_image_enabled(app_config: dict | None = None) -> bool:
    """
    判断 OpenAI 兼容文生图素材源是否已完成最小配置。

    API Key 允许为空：完全本地的 ComfyUI/SD 网关通常不需要鉴权，为空时
    请求不带 Authorization 头。供任务预检和 WebUI 在消耗 LLM、TTS 额度
    前拦截缺失配置的任务。
    """
    app_config = config.app if app_config is None else app_config
    return bool(
        str(app_config.get("openai_image_base_url", "") or "").strip()
        and str(app_config.get("openai_image_model", "") or "").strip()
    )


def _openai_image_endpoint(model_override: str = "") -> tuple[str, str]:
    """Read the OpenAI-compatible image endpoint and select the requested workflow model."""
    base_url = (
        str(config.app.get("openai_image_base_url", "") or "").strip().rstrip("/")
    )
    model = str(model_override or "").strip() or str(
        config.app.get("openai_image_model", "") or ""
    ).strip()
    if not base_url:
        raise ValueError(
            "\n\n##### openai_image_base_url is not set #####\n\n"
            f"Please set it in the config.toml file: {config.config_file}\n"
        )
    if not model:
        raise ValueError(
            "\n\n##### openai_image_model is not set #####\n\n"
            f"Please set it in the config.toml file: {config.config_file}\n"
        )
    return f"{base_url}/{OPENAI_IMAGE_ENDPOINT_PATH}", model


def _normalize_openai_image_route(route: str | None) -> str:
    value = str(route or "standard").strip().lower()
    return "precision" if value == "precision" else "standard"


def _openai_image_model_for_route(route: str | None) -> tuple[str, bool]:
    """Resolve a per-scene model. The precision model is optional and falls back safely."""
    route = _normalize_openai_image_route(route)
    default_model = str(config.app.get("openai_image_model", "") or "").strip()
    if route != "precision":
        return default_model, False

    precision_model = str(
        config.app.get("openai_image_precision_model", "") or ""
    ).strip()
    if precision_model:
        return precision_model, False
    return default_model, True


def _openai_image_performance_profile() -> str:
    value = str(config.app.get("openai_image_performance_profile", "balanced") or "balanced").strip().lower()
    return value if value in {"fast", "balanced", "quality"} else "balanced"


def _openai_image_profile_default(profile: str, key: str):
    defaults = {
        "fast": {
            "precision_size": "736x1312",
            "qwen_steps": 18,
            "precision_candidates": 1,
        },
        "balanced": {
            "precision_size": "768x1376",
            "qwen_steps": 20,
            "precision_candidates": 1,
        },
        "quality": {
            "precision_size": "864x1536",
            "qwen_steps": 25,
            "precision_candidates": 2,
        },
    }
    return defaults.get(profile, defaults["balanced"])[key]


def _oriented_profile_size(size_text: str, video_aspect: VideoAspect) -> str:
    try:
        left, right = str(size_text).lower().split("x", 1)
        width, height = int(left), int(right)
    except (TypeError, ValueError):
        return str(size_text)
    short, long = min(width, height), max(width, height)
    aspect = VideoAspect(video_aspect)
    if aspect == VideoAspect.landscape:
        return f"{long}x{short}"
    if aspect == VideoAspect.square:
        # Keep square work reasonably detailed without exceeding the profile's long edge.
        square = min(max(short, 768), 1024)
        return f"{square}x{square}"
    return f"{short}x{long}"


def _openai_image_size(
    video_aspect: VideoAspect,
    route: str = "standard",
    model: str = "",
) -> str:
    """Resolve request size. Qwen precision uses performance-profile presets."""
    route = _normalize_openai_image_route(route)
    if route == "precision" and _is_qwen_image_21_model(model):
        profile = _openai_image_performance_profile()
        configured = str(
            config.app.get(
                f"openai_image_{profile}_precision_size",
                _openai_image_profile_default(profile, "precision_size"),
            )
            or ""
        ).strip()
        if configured:
            return _oriented_profile_size(configured, video_aspect)

    if route == "precision":
        precision_size = str(
            config.app.get("openai_image_precision_size", "") or ""
        ).strip()
        if precision_size:
            return _oriented_profile_size(precision_size, video_aspect)

    configured = str(config.app.get("openai_image_size", "") or "").strip()
    if configured:
        return configured
    return OPENAI_IMAGE_DEFAULT_SIZES.get(VideoAspect(video_aspect), "1024x1024")


def _openai_image_generation_steps(route: str, model: str) -> int | None:
    """Return profile-aware Qwen steps; other workflows keep their own defaults."""
    if _normalize_openai_image_route(route) != "precision" or not _is_qwen_image_21_model(model):
        return None
    profile = _openai_image_performance_profile()
    try:
        value = int(
            config.app.get(
                f"openai_image_{profile}_qwen_steps",
                _openai_image_profile_default(profile, "qwen_steps"),
            )
            or _openai_image_profile_default(profile, "qwen_steps")
        )
    except (TypeError, ValueError):
        value = int(_openai_image_profile_default(profile, "qwen_steps"))
    return max(8, min(value, 60))

def _openai_image_prompt(search_term: str, route: str = "standard") -> str:
    """
    把脚本关键词包装成最终提示词。

    可选配置 ``openai_image_prompt_template`` 支持 ``{term}`` 占位符，
    用于统一附加风格修饰（如画质、构图、镜头语言），提升图文匹配度：

    .. code-block:: toml

        openai_image_prompt_template = "cinematic photo of {term}, photorealistic"

    留空或不含占位符时退回关键词原文，行为与旧版本完全一致。占位符
    替换失败（如模板误写了格式化语法）也回退原文，不让配置错误中断
    整个生成任务。
    """
    route = _normalize_openai_image_route(route)
    template = ""
    if route == "precision":
        template = str(
            config.app.get("openai_image_precision_prompt_template", "") or ""
        ).strip()
    if not template:
        template = str(config.app.get("openai_image_prompt_template", "") or "").strip()
    if not template or "{term}" not in template:
        return search_term
    try:
        return template.replace("{term}", search_term)
    except Exception:
        return search_term


def _response_json_safely(response: Any) -> Any:
    """读取响应 JSON；测试替身或异常响应解析失败时返回 None。"""
    try:
        return response.json()
    except Exception:
        return None


def _openai_image_response_message(body: Any) -> str:
    """
    从 OpenAI 兼容响应中提取可读错误描述。

    标准格式是 ``{"error": {"message": ...}}``，中转服务常退化为
    ``{"message": ...}`` 或直接给一个字符串。都取不到时返回空串，由调用方
    决定是否回退到响应正文。
    """
    if not isinstance(body, dict):
        return str(body or "")[:300]
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or "")[:300]
    if error is not None:
        return str(error)[:300]
    return str(body.get("message") or "")[:300]


def _openai_image_http_failure(response: Any, status: int, api_key: str) -> str:
    """把 HTTP 错误响应整理成一条脱敏后的日志可读描述。"""
    message = _openai_image_response_message(_response_json_safely(response))
    if not message:
        message = str(getattr(response, "text", "") or "")[:300]
    return f"HTTP {status}: {_redact_secret(message, api_key)}"


def _openai_image_download_bytes(
    image_url: str,
    api_key: str,
) -> tuple[bytes | None, str]:
    """
    下载已生成图片的临时 URL。

    图片已经按张计费，下载失败时优先重试原地址，而不是回退到重新生成，
    避免为同一张图重复付费。
    """
    failure_detail = "no download attempt was made"
    for attempt in range(1, OPENAI_IMAGE_MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            response = requests.get(
                image_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/115.0.0.0 Safari/537.36"
                },
                proxies=config.proxy,
                verify=_get_tls_verify(),
                timeout=(30, 120),
            )
            if response.status_code == 200 and response.content:
                return response.content, ""
            failure_detail = f"HTTP {response.status_code} while downloading image"
        except Exception as e:
            failure_detail = (
                f"error={type(e).__name__}, detail={_redact_request_error(e, api_key)}"
            )
        if attempt < OPENAI_IMAGE_MAX_DOWNLOAD_ATTEMPTS:
            logger.warning(
                "generated image download failed, retrying the same url: "
                f"attempt={attempt}/{OPENAI_IMAGE_MAX_DOWNLOAD_ATTEMPTS}, "
                f"{failure_detail}"
            )
            time.sleep(OPENAI_IMAGE_DOWNLOAD_BACKOFF_SECONDS)
    return None, failure_detail


def _parse_openai_image_response(
    response: Any,
    api_key: str,
) -> tuple[bytes | None, str]:
    """
    解析 /images/generations 响应，取回 url 或 b64_json 图片数据。

    解析失败属于明确的业务拒绝（如内容策略）或异常响应格式，直接返回
    错误描述，不做退避重试——重发同样的请求只会得到同样的结果。
    """
    body = _response_json_safely(response)
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list) or not data:
        return None, _redact_secret(_openai_image_response_message(body), api_key)

    entry = data[0]
    if not isinstance(entry, dict):
        return None, "invalid image data entry"

    b64_payload = entry.get("b64_json")
    if b64_payload:
        try:
            return base64.b64decode(b64_payload), ""
        except Exception as e:
            return None, f"invalid b64_json payload: {type(e).__name__}"

    image_url = entry.get("url")
    if isinstance(image_url, str) and image_url.startswith(("http://", "https://")):
        return _openai_image_download_bytes(image_url, api_key)

    return None, "image response has neither url nor b64_json"


def _request_openai_image(endpoint: str, payload: dict) -> tuple[bytes | None, str]:
    """
    调用 OpenAI 兼容 /images/generations 接口，带退避重试与 key 轮换。

    429/5xx 按临时故障退避重试；401/403 只有在配置了多个 key 时才重试
    （借助 get_api_key 的轮换机制换 key）；其余 4xx 是明确拒绝，快速失败
    交给上层跳过该关键词。

    计费安全：POST 的读超时与连接中断视为"未确认"状态——服务端可能已经
    生成并扣费，只是响应没有返回，自动重新提交可能造成重复生成和重复
    计费，因此不做重试。只有连接阶段超时（ConnectTimeout，请求确定没有
    送达服务端）才确认没有创建生成任务，可以安全重试。

    API Key 允许为空：完全本地的 ComfyUI/SD 网关通常不需要鉴权，为空时
    不发送 Authorization 头。
    """
    api_keys = config.app.get("openai_image_api_keys")
    if isinstance(api_keys, (list, tuple)):
        configured_keys = [k for k in api_keys if str(k or "").strip()]
    elif str(api_keys or "").strip():
        configured_keys = [api_keys]
    else:
        configured_keys = []

    failure_detail = "no request attempt was made"
    for attempt in range(1, OPENAI_IMAGE_MAX_ATTEMPTS + 1):
        api_key = get_api_key("openai_image_api_keys") if configured_keys else ""
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        retryable = False
        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                proxies=config.proxy,
                verify=_get_tls_verify(),
                timeout=OPENAI_IMAGE_REQUEST_TIMEOUT,
            )
        except requests.exceptions.ConnectTimeout as e:
            # 连接阶段超时：请求确定没有送达服务端，没有创建生成任务，
            # 可以安全重试。
            failure_detail = (
                f"connect timeout: detail={_redact_request_error(e, api_key)}"
            )
            retryable = True
        except Exception as e:
            # 读超时/连接中断等属于"未确认"状态：服务端可能已经受理并扣费，
            # 自动重新提交可能重复生成、重复计费，交由上层跳过该关键词。
            failure_detail = (
                f"unconfirmed request error (no retry to avoid double billing): "
                f"{type(e).__name__}, detail={_redact_request_error(e, api_key)}"
            )
        else:
            status = int(getattr(response, "status_code", 200) or 200)
            if status in OPENAI_IMAGE_KEY_ERROR_STATUS_CODES:
                failure_detail = _openai_image_http_failure(response, status, api_key)
                # 只有多 key 配置下，重试才可能轮换到可用 key。
                retryable = len(configured_keys) > 1
            elif status in OPENAI_IMAGE_RETRYABLE_STATUS_CODES:
                failure_detail = _openai_image_http_failure(response, status, api_key)
                retryable = True
            elif status >= 400:
                return None, _openai_image_http_failure(response, status, api_key)
            else:
                image_bytes, parse_error = _parse_openai_image_response(
                    response, api_key
                )
                if image_bytes is not None:
                    return image_bytes, ""
                failure_detail = parse_error

        if retryable and attempt < OPENAI_IMAGE_MAX_ATTEMPTS:
            backoff_seconds = OPENAI_IMAGE_RETRY_BACKOFF_SECONDS[
                min(attempt - 1, len(OPENAI_IMAGE_RETRY_BACKOFF_SECONDS) - 1)
            ]
            logger.warning(
                "openai image request failed, retrying: "
                f"attempt={attempt}/{OPENAI_IMAGE_MAX_ATTEMPTS}, "
                f"next_retry_in={backoff_seconds}s, detail={failure_detail}"
            )
            time.sleep(backoff_seconds)
            continue
        return None, failure_detail

    return None, failure_detail


def _save_openai_image_file(
    image_bytes: bytes,
    save_dir: str,
) -> tuple[str, int, int]:
    """
    把生成结果规范成 PNG 落盘，返回 (路径, 宽, 高)。

    统一转成 PNG 可以规避两类问题：中转服务返回 WebP/JPEG 却没有可靠
    扩展名，以及携带异常元数据的图片让 MoviePy 解析失败（与 local 素材
    的净化逻辑呼应，这里在落盘阶段就完成规范化）。
    """
    if not save_dir:
        save_dir = utils.storage_dir("cache_images", create=True)
    elif not os.path.isdir(save_dir):
        os.makedirs(save_dir, exist_ok=True)

    image_path = os.path.join(save_dir, f"openai-image-{uuid.uuid4().hex[:12]}.png")

    # 图片解码失败可以降级为“跳过当前关键词”，但目录权限、磁盘空间和文件
    # 写入失败必须继续抛出，否则按需生成循环会在本地无法保存文件时继续创建
    # 后续付费任务。Image.open 只读取内存字节，因此这里的 OSError 属于格式
    # 识别失败；image.load 的 OSError 则对应截断或损坏的图片数据。
    try:
        image = Image.open(io.BytesIO(image_bytes))
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise _OpenAIImageDecodeError(f"{type(exc).__name__}: {exc}") from exc

    with image:
        try:
            image.load()
        except (OSError, SyntaxError, ValueError) as exc:
            raise _OpenAIImageDecodeError(f"{type(exc).__name__}: {exc}") from exc
        if image.mode not in ("RGB", "RGBA", "L", "LA", "P"):
            image = image.convert("RGB")
        # save 不放进解码异常保护区：写入错误表示运行环境持续不可用，应立即
        # 终止整个任务，避免后续关键词继续产生无法落盘的付费图片。
        image.save(image_path, format="PNG")
        width, height = image.size
    return image_path, width, height



_WIKIMEDIA_COMMONS_API = "https://commons.wikimedia.org/w/api.php"
_OPENVERSE_IMAGES_API = "https://api.openverse.org/v1/images/"
_INATURALIST_TAXA_API = "https://api.inaturalist.org/v1/taxa/autocomplete"
_INATURALIST_OBSERVATIONS_API = "https://api.inaturalist.org/v1/observations"
_PEXELS_PHOTO_SEARCH_API = "https://api.pexels.com/v1/search"
_DEFAULT_COMFYUI_REFERENCE_UPLOAD_URL = "http://127.0.0.1:8188/upload/image"
_REFERENCE_USER_AGENT = "MoneyPrinterTurbo-PrecisionReference/2.0"




def _precision_related_subject_cache_enabled() -> bool:
    value = config.app.get("openai_image_reference_related_subject_cache_enabled", True)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _precision_reference_cache_lookup(
    cache: dict[str, tuple[str, dict[str, Any]]],
    subject: str,
) -> tuple[str, dict[str, Any]] | None:
    """Reuse a factual reference for detail/profile variants of the same subject.

    Exact match remains first. For related scenes, only a strict token-prefix
    relationship is accepted (e.g. "marine tardigrade" -> "marine tardigrade legs").
    This is deliberately conservative to avoid crossing into a different species/object.
    """
    key = _normalized_reference_subject(subject).lower()
    if not key:
        return None

    exact = cache.get(key)
    if exact:
        return exact

    if not _precision_related_subject_cache_enabled():
        return None

    key_tokens = key.split()
    best_key = ""
    for cached_key in cache:
        cached_tokens = cached_key.split()
        if not cached_tokens:
            continue

        current_extends_cached = (
            len(key_tokens) > len(cached_tokens)
            and key_tokens[: len(cached_tokens)] == cached_tokens
        )
        cached_extends_current = (
            len(cached_tokens) > len(key_tokens)
            and cached_tokens[: len(key_tokens)] == key_tokens
        )
        if current_extends_cached or cached_extends_current:
            if len(cached_key) > len(best_key):
                best_key = cached_key

    if not best_key:
        return None

    value = cache.get(best_key)
    if value:
        # Alias the current scene key so later lookups are exact and cheap.
        cache[key] = value
        logger.info(
            "reusing precision reference across related scene subjects: "
            f"subject={subject!r}, cached_subject={best_key!r}, "
            f"image={value[0]!r}"
        )
    return value


def _precision_release_models_between_candidates() -> bool:
    value = config.app.get(
        "openai_image_precision_release_models_between_candidates",
        True,
    )
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _precision_reference_early_accept_enabled() -> bool:
    value = config.app.get("openai_image_reference_early_accept_enabled", True)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _precision_reference_early_accept_min_visibility() -> float:
    try:
        return max(
            0.0,
            min(
                float(
                    config.app.get(
                        "openai_image_reference_early_accept_min_visibility",
                        0.42,
                    )
                ),
                1.0,
            ),
        )
    except (TypeError, ValueError):
        return 0.42


def _precision_reference_early_accept_min_suitability() -> float:
    try:
        return max(
            0.0,
            min(
                float(
                    config.app.get(
                        "openai_image_reference_early_accept_min_suitability",
                        0.42,
                    )
                ),
                1.0,
            ),
        )
    except (TypeError, ValueError):
        return 0.42


def _precision_reference_can_early_accept(
    evaluation: dict[str, Any],
    *,
    semantic_score: float | None,
    rescue_ok: bool,
) -> bool:
    """Provider-agnostic early accept for already-good factual references."""
    if not _precision_reference_early_accept_enabled():
        return False
    judgment = evaluation.get("judgment")
    if not isinstance(judgment, dict) or not judgment.get("available"):
        return False
    if str(judgment.get("verdict") or "").lower() == "reject":
        return False

    visibility = float(judgment.get("structural_visibility", 0.0) or 0.0)
    suitability = float(judgment.get("reference_suitability", 0.0) or 0.0)
    if visibility < _precision_reference_early_accept_min_visibility():
        return False
    if suitability < _precision_reference_early_accept_min_suitability():
        return False

    if semantic_score is not None and float(semantic_score) >= _reference_min_semantic_score():
        return True

    # Authority rescue remains valid, but only when the reference is also
    # structurally visible/useful. This prevents "correct identity, useless view".
    return bool(rescue_ok)



def _precision_standard_fallback_enabled() -> bool:
    value = config.app.get("openai_image_precision_standard_fallback_enabled", False)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)



def _precision_reference_enabled() -> bool:
    value = config.app.get("openai_image_precision_reference_enabled", True)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _precision_reference_crop_enabled() -> bool:
    value = config.app.get("openai_image_reference_crop_enabled", True)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _precision_reference_crop_padding() -> float:
    try:
        value = float(config.app.get("openai_image_reference_crop_padding", 0.18))
    except (TypeError, ValueError):
        value = 0.18
    if not math.isfinite(value):
        value = 0.18
    return max(0.05, min(value, 0.50))


def _precision_reference_crop_min_bbox_area_ratio() -> float:
    """Below this area the segmentation/reference is too weak to trust for cropping."""
    try:
        value = float(
            config.app.get("openai_image_reference_crop_min_bbox_area_ratio", 0.01)
        )
    except (TypeError, ValueError):
        value = 0.01
    if not math.isfinite(value):
        value = 0.01
    return max(0.001, min(value, 0.25))


def _precision_reference_crop_skip_above_bbox_area_ratio() -> float:
    """If the subject already dominates the source, preserve the original framing."""
    try:
        value = float(
            config.app.get(
                "openai_image_reference_crop_skip_above_bbox_area_ratio",
                0.60,
            )
        )
    except (TypeError, ValueError):
        value = 0.60
    if not math.isfinite(value):
        value = 0.60
    return max(0.20, min(value, 0.95))


def _precision_reference_crop_min_short_side() -> int:
    try:
        value = int(
            config.app.get("openai_image_reference_crop_min_short_side", 320)
            or 320
        )
    except (TypeError, ValueError):
        value = 320
    return max(128, min(value, 1024))


def _precision_reference_crop_max_dimension() -> int:
    try:
        value = int(
            config.app.get("openai_image_reference_crop_max_dimension", 1600)
            or 1600
        )
    except (TypeError, ValueError):
        value = 1600
    return max(512, min(value, 4096))


def _normalized_reference_subject(subject: str) -> str:
    value = " ".join(str(subject or "").split()).strip()
    # Keep Commons searches short and concrete. Long scene descriptions produce
    # much worse results than the structured subject emitted by llm.py.
    return value[:160]


def _reference_timeout_seconds() -> float:
    try:
        return max(
            5.0,
            float(config.app.get("openai_image_reference_timeout_seconds", 20) or 20),
        )
    except (TypeError, ValueError):
        return 20.0


def _openverse_timeout_seconds() -> float:
    try:
        value = float(
            config.app.get("openai_image_openverse_timeout_seconds", 8) or 8
        )
    except (TypeError, ValueError):
        value = 8.0
    if not math.isfinite(value):
        value = 8.0
    return max(3.0, min(value, 20.0))


def _wikimedia_429_retries() -> int:
    try:
        value = int(config.app.get("openai_image_wikimedia_429_retries", 1) or 1)
    except (TypeError, ValueError):
        value = 1
    return max(0, min(value, 3))


def _wikimedia_429_backoff_seconds() -> float:
    try:
        value = float(
            config.app.get("openai_image_wikimedia_429_backoff_seconds", 2) or 2
        )
    except (TypeError, ValueError):
        value = 2.0
    if not math.isfinite(value):
        value = 2.0
    return max(0.5, min(value, 15.0))


def _wikimedia_get_with_backoff(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> requests.Response:
    """GET Wikimedia with one small, bounded 429 retry by default."""
    retries = _wikimedia_429_retries()
    attempts = retries + 1
    last_response = None

    for attempt in range(attempts):
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": _REFERENCE_USER_AGENT},
            timeout=timeout or _reference_timeout_seconds(),
        )
        last_response = response

        if response.status_code != 429 or attempt >= retries:
            return response

        retry_after = response.headers.get("Retry-After")
        try:
            wait_seconds = float(retry_after) if retry_after else _wikimedia_429_backoff_seconds()
        except (TypeError, ValueError):
            wait_seconds = _wikimedia_429_backoff_seconds()

        wait_seconds = max(0.5, min(wait_seconds, 15.0))
        logger.warning(
            "Wikimedia returned HTTP 429; bounded retry scheduled: "
            f"attempt={attempt + 1}/{attempts}, wait={wait_seconds:.1f}s"
        )
        time.sleep(wait_seconds)

    return last_response


def _reference_search_providers() -> list[str]:
    raw = config.app.get(
        "openai_image_reference_providers",
        ["wikimedia", "openverse", "inaturalist", "pexels"],
    )
    if isinstance(raw, str):
        values = [item.strip().lower() for item in raw.split(",")]
    elif isinstance(raw, (list, tuple)):
        values = [str(item or "").strip().lower() for item in raw]
    else:
        values = []
    allowed = {"wikimedia", "openverse", "inaturalist", "pexels"}
    result = []
    for value in values:
        if value in allowed and value not in result:
            result.append(value)
    return result or ["wikimedia", "openverse"]


def _reference_candidates_per_provider() -> int:
    try:
        value = int(config.app.get("openai_image_reference_candidates_per_provider", 6) or 6)
    except (TypeError, ValueError):
        value = 6
    return max(2, min(value, 20))


def _reference_rank_pool_size() -> int:
    try:
        value = int(config.app.get("openai_image_reference_rank_pool_size", 4) or 4)
    except (TypeError, ValueError):
        value = 4
    return max(2, min(value, 16))


def _reference_min_semantic_score() -> float:
    try:
        value = float(config.app.get("openai_image_reference_min_semantic_score", 0.48))
    except (TypeError, ValueError):
        value = 0.48
    if not math.isfinite(value):
        value = 0.48
    return max(0.0, min(value, 1.0))



def _manual_precision_reference_mode_default() -> str:
    value = str(
        config.app.get("openai_image_manual_reference_mode", "user_first")
        or "user_first"
    ).strip().lower()
    if value not in {"auto_only", "user_first", "user_only"}:
        return "user_first"
    return value


def _manual_precision_reference_max_images() -> int:
    try:
        value = int(config.app.get("openai_image_manual_reference_max_images", 8) or 8)
    except (TypeError, ValueError):
        value = 8
    return max(1, min(value, 8))


def _manual_precision_reference_manifest(save_dir: str) -> Path:
    return Path(str(save_dir or "")).resolve() / "user_references" / "manifest.json"


def _load_manual_precision_reference_manifest(
    save_dir: str,
) -> tuple[str, list[dict[str, str]]]:
    """Read the task-scoped reference manifest without changing upload order."""
    mode = _manual_precision_reference_mode_default()
    manifest_path = _manual_precision_reference_manifest(save_dir)
    entries: list[dict[str, str]] = []
    if not manifest_path.is_file():
        return mode, entries

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning(
            "failed to read manual precision reference manifest: "
            f"path={manifest_path.name!r}, error={type(exc).__name__}, detail={exc}"
        )
        return mode, entries

    manifest_mode = str(manifest.get("mode") or mode).strip().lower()
    if manifest_mode in {"auto_only", "user_first", "user_only"}:
        mode = manifest_mode

    raw_files = manifest.get("files") or []
    if not isinstance(raw_files, list):
        return mode, entries

    for raw in raw_files[: _manual_precision_reference_max_images()]:
        if isinstance(raw, dict):
            stored = str(raw.get("stored") or raw.get("file") or "").strip()
            original = str(raw.get("original") or "").strip()
            role = str(raw.get("role") or "identity").strip().lower()
            description = str(raw.get("description") or "").strip()
        else:
            stored = str(raw or "").strip()
            original = ""
            role = "identity"
            description = ""
        if not stored:
            continue
        if role not in {"identity", "detail", "internal", "context", "other"}:
            role = "identity"
        entries.append({"stored": stored, "original": original, "role": role, "description": description})
    return mode, entries


def _prepare_manual_precision_reference_pack(
    subject: str,
    save_dir: str,
) -> tuple[list[str], dict[str, Any]]:
    """Upload the user's stable identity pack to ComfyUI once, preserving order."""
    subject = _normalized_reference_subject(subject)
    mode, entries = _load_manual_precision_reference_manifest(save_dir)
    if mode == "auto_only" or not entries:
        return [], {"manual_reference_mode": mode}

    references_dir = _manual_precision_reference_manifest(save_dir).parent
    comfyui_inputs: list[str] = []
    pack_meta: list[dict[str, Any]] = []
    primary_local_path = ""

    for slot, entry in enumerate(entries, start=1):
        local_path = references_dir / entry["stored"]
        if not local_path.is_file():
            logger.warning(
                "manual precision reference is missing: "
                f"slot={slot}, file={local_path.name!r}"
            )
            continue

        try:
            with Image.open(local_path) as source:
                source.verify()
            with Image.open(local_path) as source:
                width, height = source.size
        except Exception as exc:
            logger.warning(
                "manual precision reference is not a usable image: "
                f"slot={slot}, file={local_path.name!r}, "
                f"error={type(exc).__name__}, detail={exc}"
            )
            continue

        comfyui_name = _upload_reference_to_comfyui(str(local_path))
        if not comfyui_name:
            logger.warning(
                "manual precision reference could not be uploaded to ComfyUI: "
                f"slot={slot}, file={local_path.name!r}"
            )
            continue

        if not primary_local_path:
            primary_local_path = str(local_path)
        comfyui_inputs.append(comfyui_name)
        pack_meta.append(
            {
                "slot": len(comfyui_inputs),
                "local_file": local_path.name,
                "original_file": entry.get("original") or None,
                "role": entry.get("role") or "identity",
                "description": entry.get("description") or None,
                "comfyui_input": comfyui_name,
                "width": int(width or 0),
                "height": int(height or 0),
            }
        )

    if not comfyui_inputs:
        return [], {"manual_reference_mode": mode}

    info: dict[str, Any] = {
        "provider": "user_upload",
        "subject": subject,
        "title": "user identity pack",
        "license": "user-provided",
        "query": subject,
        "manual_reference_mode": mode,
        "comfyui_input": comfyui_inputs[0],
        "local_path": primary_local_path,
        "original_local_path": primary_local_path,
        "reference_pack": pack_meta,
        "reference_selection": {
            "status": "user_identity_pack",
            "count": len(comfyui_inputs),
            "stable_across_precision_scenes": True,
        },
    }
    logger.info(
        "manual precision reference library ready for Qwen: "
        f"count={len(comfyui_inputs)}, subject={subject!r}, "
        f"files={[item['local_file'] for item in pack_meta]!r}"
    )
    return comfyui_inputs, info


def _select_manual_references_for_scene(
    all_inputs: list[str],
    reference_info: dict[str, Any] | None,
    reference_need: str,
    reference_query: str,
    max_refs: int = 3,
) -> tuple[list[str], dict[str, Any]]:
    """Choose a small theme-agnostic reference pack for one scene."""
    info = dict(reference_info or {})
    pack = [dict(item) for item in (info.get("reference_pack") or []) if isinstance(item, dict)]
    if not pack:
        return list(all_inputs or [])[:max_refs], info
    need = str(reference_need or "identity").strip().lower()
    query_tokens = {tok for tok in re.findall(r"[a-z0-9]+", str(reference_query or "").lower()) if len(tok) >= 3}

    def score(item: dict) -> tuple[float, int]:
        role = str(item.get("role") or "identity").strip().lower()
        role_score = 0.0
        if role == "identity": role_score += 3.0
        if role == need: role_score += 6.0
        if need == "detail" and role == "internal": role_score += 1.0
        if need == "internal" and role == "detail": role_score += 1.5
        if need == "context" and role == "context": role_score += 4.0
        desc_tokens = {tok for tok in re.findall(r"[a-z0-9]+", str(item.get("description") or "").lower()) if len(tok) >= 3}
        semantic = len(query_tokens & desc_tokens) * 0.75
        return (role_score + semantic, -int(item.get("slot") or 999))

    identity = [item for item in pack if str(item.get("role") or "identity") == "identity"]
    selected: list[dict] = []
    if identity:
        selected.append(max(identity, key=score))
    for item in sorted(pack, key=score, reverse=True):
        if item not in selected:
            selected.append(item)
        if len(selected) >= max(1, min(max_refs, 3)):
            break
    selected_inputs = [str(item.get("comfyui_input") or "").strip() for item in selected]
    selected_inputs = [value for value in selected_inputs if value]
    info["reference_pack_all"] = pack
    info["reference_pack"] = selected
    info["reference_selection"] = {
        "status": "scene_adaptive_manual_pack",
        "requested_need": need,
        "reference_query": str(reference_query or "").strip(),
        "selected_count": len(selected_inputs),
        "available_count": len(pack),
        "stable_identity_across_precision_scenes": bool(identity),
    }
    return selected_inputs, info


def _qwen_negative_prompt(forbidden_features: list[str] | None = None) -> str:
    base = [
        "garbled text", "fake labels", "invented branding", "watermark", "stock-site text",
        "duplicated subject parts", "malformed geometry", "impossible anatomy", "impossible construction",
        "floating disconnected parts", "collage", "split screen", "presentation card", "artificial border",
        "cutout halo", "inconsistent lighting", "inconsistent reflections",
    ]
    seen = {item.lower() for item in base}
    for value in forbidden_features or []:
        value = str(value or "").strip()
        if value and value.lower() not in seen:
            base.append(value)
            seen.add(value.lower())
    return ", ".join(base[:24])


def _validate_generated_image_basic(path: str, expected_size: str = "") -> tuple[bool, str]:
    """Very cheap technical QA; no vision model and no semantic quality penalty."""
    try:
        target_w = target_h = 0
        if "x" in str(expected_size).lower():
            a, b = str(expected_size).lower().split("x", 1)
            target_w, target_h = int(a), int(b)
        with Image.open(path) as img:
            img = img.convert("RGB")
            width, height = img.size
            if width < 256 or height < 256:
                return False, f"image too small ({width}x{height})"
            if target_w and target_h:
                got = width / max(height, 1)
                expected = target_w / max(target_h, 1)
                if abs(got - expected) / max(expected, 1e-6) > 0.08:
                    return False, f"unexpected aspect ratio ({width}x{height}, expected {target_w}x{target_h})"
            stat = ImageStat.Stat(img.resize((128, 128)))
            mean_std = sum(stat.stddev) / max(len(stat.stddev), 1)
            extrema = img.getextrema()
            dynamic_range = max((hi - lo) for lo, hi in extrema)
            if mean_std < 2.0 or dynamic_range < 12:
                return False, "near-blank/flat image"
        if Path(path).stat().st_size < 12_000:
            return False, "unexpectedly tiny image file"
        return True, "ok"
    except Exception as exc:
        return False, f"image validation error: {type(exc).__name__}: {exc}"


def _is_qwen_image_21_model(model: str) -> bool:
    value = str(model or "").strip().lower().replace("_", "-")
    return "qwen-image-2.1" in value or "qwenimage2.1" in value



def _qwen_direct_accept_enabled(
    model: str,
    reference_images: list[str] | None,
) -> bool:
    """Fast/Balanced: one Qwen edit, no selector/judge pass afterwards."""
    return bool(
        _openai_image_performance_profile() in {"fast", "balanced"}
        and _is_qwen_image_21_model(model)
        and list(reference_images or [])
    )


def _precision_retry_on_true_failure_enabled() -> bool:
    value = config.app.get("openai_image_precision_retry_on_true_failure_enabled", True)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _precision_keep_judges_loaded_between_scenes() -> bool:
    value = config.app.get(
        "openai_image_precision_keep_judges_loaded_between_scenes",
        True,
    )
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _precision_fallback_model() -> str:
    return str(
        config.app.get("openai_image_precision_fallback_model", "flux-klein-precision")
        or ""
    ).strip()


def _reference_provider_priority(provider: str, domain: str) -> float:
    provider = str(provider or "").lower()
    if domain == "biological":
        table = {
            "inaturalist": 1.00,
            "wikimedia": 0.92,
            "openverse": 0.84,
            "pexels": 0.58,
        }
    else:
        table = {
            "wikimedia": 1.00,
            "openverse": 0.94,
            "pexels": 0.84,
            "inaturalist": 0.40,
        }
    return table.get(provider, 0.5)


def _reference_token_overlap(text: str, query: str) -> float:
    left = {
        token for token in re.findall(r"[a-z0-9]+", str(text or "").lower())
        if len(token) >= 3
    }
    right = {
        token for token in re.findall(r"[a-z0-9]+", str(query or "").lower())
        if len(token) >= 3
    }
    if not right:
        return 0.0
    return len(left & right) / max(1, len(right))


def _reference_common_heuristic(candidate: dict[str, Any], subject: str, domain: str) -> float:
    title = str(candidate.get("title") or "")
    query = str(candidate.get("query") or subject)
    width = int(candidate.get("width") or 0)
    height = int(candidate.get("height") or 0)
    pixels = width * height
    resolution = min(pixels / 2_000_000.0, 1.0) if pixels > 0 else 0.25
    overlap = max(
        _reference_token_overlap(title, subject),
        _reference_token_overlap(title, query),
    )
    license_text = str(candidate.get("license") or "").lower()
    open_license_bonus = 1.0 if license_text else 0.5
    provider_priority = _reference_provider_priority(
        str(candidate.get("provider") or ""),
        domain,
    )
    return (
        0.38 * overlap
        + 0.24 * resolution
        + 0.23 * provider_priority
        + 0.15 * open_license_bonus
    )


def _reference_candidate_key(candidate: dict[str, Any]) -> str:
    image_url = str(candidate.get("image_url") or "").strip()
    if image_url:
        return re.sub(r"[?#].*$", "", image_url).lower()
    return (
        str(candidate.get("provider") or "").lower()
        + "|"
        + str(candidate.get("source_page") or candidate.get("title") or "").lower()
    )


def _wikimedia_reference_candidates(query: str, subject: str) -> list[dict[str, Any]]:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": _reference_candidates_per_provider(),
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": 1600,
        "format": "json",
        "formatversion": 2,
        "origin": "*",
    }
    try:
        response = _wikimedia_get_with_backoff(
            _WIKIMEDIA_COMMONS_API,
            params=params,
            timeout=_reference_timeout_seconds(),
        )
        response.raise_for_status()
        pages = ((response.json() or {}).get("query") or {}).get("pages") or []
    except Exception as exc:
        logger.warning(
            "Wikimedia reference search failed: "
            f"query={query!r}, error={type(exc).__name__}, detail={exc}"
        )
        return []

    candidates = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        imageinfo = (page.get("imageinfo") or [{}])[0]
        mime = str(imageinfo.get("mime") or "").lower()
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        width = int(imageinfo.get("width") or 0)
        height = int(imageinfo.get("height") or 0)
        if width < 256 or height < 256:
            continue
        title = str(page.get("title") or "").strip()
        if any(
            word in title.lower()
            for word in ("logo", "icon", "map", "diagram", "drawing", "illustration")
        ):
            presentation_penalty = 0.18
        else:
            presentation_penalty = 0.0
        extmetadata = imageinfo.get("extmetadata") or {}
        license_name = str(
            (extmetadata.get("LicenseShortName") or {}).get("value") or ""
        ).strip()
        image_url = str(
            imageinfo.get("thumburl") or imageinfo.get("url") or ""
        ).strip()
        if not image_url:
            continue
        item = {
            "provider": "wikimedia",
            "query": query,
            "title": title,
            "image_url": image_url,
            "source_page": _safe_public_url(imageinfo.get("descriptionurl")),
            "license": license_name or "Wikimedia Commons",
            "creator": str(
                (extmetadata.get("Artist") or {}).get("value") or ""
            ).strip(),
            "width": width,
            "height": height,
            "presentation_penalty": presentation_penalty,
        }
        item["heuristic_score"] = (
            _reference_common_heuristic(item, subject, "general")
            - presentation_penalty
        )
        candidates.append(item)
    return candidates


def _openverse_reference_candidates(query: str, subject: str) -> list[dict[str, Any]] | None:
    params = {
        "q": query,
        "page_size": _reference_candidates_per_provider(),
        # Openverse indexes openly licensed media. We additionally ask for mature
        # content to be excluded because factual reference search never needs it.
        "mature": "false",
    }
    try:
        response = requests.get(
            _OPENVERSE_IMAGES_API,
            params=params,
            headers={"User-Agent": _REFERENCE_USER_AGENT},
            timeout=_openverse_timeout_seconds(),
        )
        response.raise_for_status()
        results = (response.json() or {}).get("results") or []
    except (requests.Timeout, requests.ConnectionError) as exc:
        logger.warning(
            "Openverse reference search timed out/unreachable; "
            "circuit-break provider for this scene: "
            f"query={query!r}, error={type(exc).__name__}, detail={exc}"
        )
        return None
    except Exception as exc:
        logger.warning(
            "Openverse reference search failed: "
            f"query={query!r}, error={type(exc).__name__}, detail={exc}"
        )
        return []

    candidates = []
    for result in results:
        if not isinstance(result, dict):
            continue
        image_url = str(result.get("url") or result.get("thumbnail") or "").strip()
        if not image_url.startswith(("http://", "https://")):
            continue
        license_name = str(result.get("license") or "").strip()
        license_version = str(result.get("license_version") or "").strip()
        if license_version:
            license_name = f"{license_name} {license_version}".strip()
        item = {
            "provider": "openverse",
            "query": query,
            "title": str(result.get("title") or "").strip(),
            "image_url": image_url,
            "source_page": _safe_public_url(result.get("foreign_landing_url")),
            "license": license_name or "Openverse open license",
            "creator": str(result.get("creator") or "").strip(),
            "width": int(result.get("width") or 0),
            "height": int(result.get("height") or 0),
            "openverse_source": str(result.get("source") or "").strip(),
            "openverse_provider": str(result.get("provider") or "").strip(),
        }
        item["heuristic_score"] = _reference_common_heuristic(item, subject, "general")
        candidates.append(item)
    return candidates



def _inaturalist_large_photo_url(url: str) -> str:
    """Normalize an iNaturalist photo URL to the large rendition.

    The observations API commonly returns .../square.jpg. The old regex used
    a double-escaped dot and therefore never replaced 'square', leaving a tiny
    thumbnail that was later rejected for being <160 px.
    """
    url = str(url or "").strip()
    if not url:
        return ""

    # Preserve extension, strip query/fragment from the rewritten rendition.
    match = re.search(
        r"/(?:square|small|medium|large)\.([A-Za-z0-9]+)(?:[?#].*)?$",
        url,
        flags=re.IGNORECASE,
    )
    if match:
        extension = match.group(1)
        return re.sub(
            r"/(?:square|small|medium|large)\.[A-Za-z0-9]+(?:[?#].*)?$",
            f"/large.{extension}",
            url,
            count=1,
            flags=re.IGNORECASE,
        )

    # If it is a standard iNaturalist/OpenData photo URL but the size token is
    # unusual, leave it unchanged rather than inventing a path.
    return url



def _inaturalist_open_photo_license(value: str) -> bool:
    value = str(value or "").strip().lower().replace("_", "-")
    # Keep the default automatic source conservative for possible commercial use.
    return value in {"cc0", "cc-by", "cc-by-sa"}


def _inaturalist_reference_candidates(
    query: str,
    subject: str,
) -> list[dict[str, Any]]:
    try:
        taxa_response = requests.get(
            _INATURALIST_TAXA_API,
            params={"q": query, "per_page": 5},
            headers={"User-Agent": _REFERENCE_USER_AGENT},
            timeout=_reference_timeout_seconds(),
        )
        taxa_response.raise_for_status()
        taxa = (taxa_response.json() or {}).get("results") or []
    except Exception as exc:
        logger.warning(
            "iNaturalist taxon search failed: "
            f"query={query!r}, error={type(exc).__name__}, detail={exc}"
        )
        return []

    if not taxa:
        return []

    # Favor lexical correspondence to the query over blindly taking autocomplete #1.
    def taxon_score(taxon: dict[str, Any]) -> float:
        names = " ".join(
            [
                str(taxon.get("name") or ""),
                str(taxon.get("preferred_common_name") or ""),
                str(taxon.get("matched_term") or ""),
            ]
        )
        return max(
            _reference_token_overlap(names, query),
            _reference_token_overlap(names, subject),
        )

    taxon = max(
        [item for item in taxa if isinstance(item, dict) and item.get("id")],
        key=taxon_score,
        default=None,
    )
    if not taxon:
        return []

    taxon_id = taxon.get("id")
    try:
        # Ask iNaturalist for observations that actually contain a photo
        # with one of our commercial-safe/open licenses. Previously we fetched
        # only a handful of newest observations of any photo license and then
        # discarded CC-BY-NC photos locally; that could easily yield zero
        # candidates even when CC0/CC-BY/CC-BY-SA photos existed deeper in the
        # result set.
        observation_page_size = max(
            20,
            min(50, _reference_candidates_per_provider() * 5),
        )
        observations_response = requests.get(
            _INATURALIST_OBSERVATIONS_API,
            params=[
                ("taxon_id", str(taxon_id)),
                ("quality_grade", "research"),
                ("has[]", "photos"),
                ("photo_license", "cc0,cc-by,cc-by-sa"),
                ("per_page", str(observation_page_size)),
                ("order", "desc"),
                ("order_by", "created_at"),
            ],
            headers={"User-Agent": _REFERENCE_USER_AGENT},
            timeout=_reference_timeout_seconds(),
        )
        observations_response.raise_for_status()
        observations = (observations_response.json() or {}).get("results") or []
    except Exception as exc:
        logger.warning(
            "iNaturalist observation search failed: "
            f"query={query!r}, taxon_id={taxon_id!r}, "
            f"error={type(exc).__name__}, detail={exc}"
        )
        return []

    logger.info(
        "iNaturalist licensed observation search: "
        f"query={query!r}, taxon_id={taxon_id!r}, "
        f"taxon_name={taxon.get('name')!r}, observations={len(observations)}, "
        "photo_license='cc0,cc-by,cc-by-sa'"
    )

    candidates = []
    rejected_license_counts: dict[str, int] = {}
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        photos = observation.get("photos") or []
        # Inspect every photo in a matched observation. The acceptable licensed
        # photo is not guaranteed to be one of the first two photos.
        for photo in photos:
            if not isinstance(photo, dict):
                continue
            license_code = str(photo.get("license_code") or "").strip()
            if not _inaturalist_open_photo_license(license_code):
                normalized_license = (
                    license_code.lower().replace("_", "-") if license_code else "none"
                )
                rejected_license_counts[normalized_license] = (
                    rejected_license_counts.get(normalized_license, 0) + 1
                )
                continue
            image_url = str(photo.get("url") or "").strip()
            if not image_url:
                continue
            # iNaturalist photo URLs commonly expose named sizes.
            # Normalize to the large rendition so the candidate is not rejected
            # as a tiny square thumbnail before Florence sees it.
            image_url = _inaturalist_large_photo_url(image_url)
            dimensions = photo.get("original_dimensions") or {}
            obs_taxon = observation.get("taxon") or taxon
            taxon_name = str(obs_taxon.get("name") or "").strip()
            common_name = str(obs_taxon.get("preferred_common_name") or "").strip()
            title = common_name or taxon_name or str(observation.get("species_guess") or "")
            item = {
                "provider": "inaturalist",
                "query": query,
                "title": title,
                "image_url": image_url,
                "source_page": _safe_public_url(
                    observation.get("uri")
                    or f"https://www.inaturalist.org/observations/{observation.get('id')}"
                ),
                "license": license_code,
                "creator": str(photo.get("attribution") or "").strip(),
                "width": int(dimensions.get("width") or 0),
                "height": int(dimensions.get("height") or 0),
                "taxon_id": str(obs_taxon.get("id") or taxon_id),
                "taxon_name": taxon_name,
                "taxon_common_name": common_name,
                "quality_grade": str(observation.get("quality_grade") or ""),
                "photo_id": str(photo.get("id") or ""),
            }
            item["heuristic_score"] = (
                _reference_common_heuristic(item, subject, "biological") + 0.12
            )
            candidates.append(item)
            if len(candidates) >= _reference_candidates_per_provider():
                logger.info(
                    "iNaturalist reference candidates accepted: "
                    f"query={query!r}, accepted={len(candidates)}, "
                    f"rejected_licenses={rejected_license_counts}"
                )
                return candidates

    logger.info(
        "iNaturalist reference candidates accepted: "
        f"query={query!r}, accepted={len(candidates)}, "
        f"rejected_licenses={rejected_license_counts}"
    )
    return candidates


def _pexels_reference_candidates(query: str, subject: str) -> list[dict[str, Any]]:
    raw_keys = config.app.get("pexels_api_keys")
    if isinstance(raw_keys, str):
        keys = [raw_keys] if raw_keys.strip() else []
    elif isinstance(raw_keys, (list, tuple)):
        keys = [str(key) for key in raw_keys if str(key or "").strip()]
    else:
        keys = []
    if not keys:
        return []

    try:
        api_key = get_api_key("pexels_api_keys")
        response = requests.get(
            _PEXELS_PHOTO_SEARCH_API,
            params={
                "query": query,
                "per_page": _reference_candidates_per_provider(),
            },
            headers={
                "Authorization": api_key,
                "User-Agent": _REFERENCE_USER_AGENT,
            },
            proxies=config.proxy,
            verify=_get_tls_verify(),
            timeout=(20, _reference_timeout_seconds()),
        )
        response.raise_for_status()
        photos = (response.json() or {}).get("photos") or []
    except Exception as exc:
        logger.warning(
            "Pexels reference search failed: "
            f"query={query!r}, error={type(exc).__name__}, "
            f"detail={_redact_request_error(exc, keys[0] if keys else '')}"
        )
        return []

    candidates = []
    for photo in photos:
        if not isinstance(photo, dict):
            continue
        src = photo.get("src") or {}
        image_url = str(
            src.get("large2x") or src.get("large") or src.get("original") or ""
        ).strip()
        if not image_url:
            continue
        item = {
            "provider": "pexels",
            "query": query,
            "title": str(photo.get("alt") or "").strip(),
            "image_url": image_url,
            "source_page": _safe_public_url(photo.get("url")),
            "license": "Pexels License",
            "creator": str(photo.get("photographer") or "").strip(),
            "width": int(photo.get("width") or 0),
            "height": int(photo.get("height") or 0),
        }
        item["heuristic_score"] = _reference_common_heuristic(item, subject, "general")
        candidates.append(item)
    return candidates



_REFERENCE_GENERIC_BIO_MODIFIERS = {
    "marine", "ocean", "oceanic", "sea", "aquatic", "microscopic", "micro",
    "freshwater", "common", "wild", "animal", "organism", "species", "adult",
}


def _reference_tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", str(text or "").lower())
        if len(token) >= 3
    ]


def _reference_fuzzy_related(left: str, right: str) -> bool:
    """Cheap lexical relation test tolerant of singular/taxonomic endings."""
    left_tokens = _reference_tokens(left)
    right_tokens = _reference_tokens(right)
    for a in left_tokens:
        for b in right_tokens:
            if a == b:
                return True
            common = 0
            for x, y in zip(a, b):
                if x != y:
                    break
                common += 1
            if common >= 7:
                return True
            if len(a) >= 7 and a in b:
                return True
            if len(b) >= 7 and b in a:
                return True
    return False


def _biological_query_anchor(subject: str) -> str:
    tokens = [
        token for token in _reference_tokens(subject)
        if token not in _REFERENCE_GENERIC_BIO_MODIFIERS
    ]
    if not tokens:
        tokens = _reference_tokens(subject)
    return tokens[-1] if tokens else str(subject or "").strip()


def _sanitize_biological_reference_queries(
    subject: str,
    queries: list[str],
) -> list[str]:
    """Never let an ambiguous common nickname become an unanchored web query."""
    anchor = _biological_query_anchor(subject)
    result: list[str] = []
    for raw in queries:
        query = _normalized_reference_subject(raw)
        if not query:
            continue
        if not _reference_fuzzy_related(query, subject) and anchor:
            # Quote short aliases to keep them together, then anchor with the
            # actual subject noun. Example: "water bear" tardigrade.
            if len(query.split()) <= 3:
                query = f'"{query}" {anchor}'
            else:
                query = f"{query} {anchor}"
        if query.lower() not in {item.lower() for item in result}:
            result.append(query)
    return result[:4]


def _reference_identity_trust(
    candidate: dict[str, Any],
    subject: str,
) -> tuple[bool, str]:
    """Trust Research Grade iNaturalist taxonomy when it maps to the subject."""
    if str(candidate.get("provider") or "").lower() != "inaturalist":
        return False, ""
    if str(candidate.get("quality_grade") or "").lower() != "research":
        return False, ""

    taxon_name = str(candidate.get("taxon_name") or "").strip()
    common_name = str(candidate.get("taxon_common_name") or "").strip()
    title = str(candidate.get("title") or "").strip()
    identity_label = common_name or taxon_name or title
    if not identity_label:
        return False, ""

    if any(
        _reference_fuzzy_related(value, subject)
        for value in (taxon_name, common_name, title)
        if value
    ):
        return True, identity_label

    # The observation came from the iNaturalist taxon endpoint selected for one
    # of our subject-anchored queries. Preserve this as weaker but still useful
    # taxonomic provenance instead of throwing it away.
    query = str(candidate.get("query") or "")
    if query and _reference_fuzzy_related(query, subject):
        return True, identity_label
    return False, identity_label



def _reference_metadata_values(candidate: dict[str, Any]) -> list[str]:
    values = [
        str(candidate.get("title") or ""),
        str(candidate.get("query") or ""),
        str(candidate.get("taxon_name") or ""),
        str(candidate.get("taxon_common_name") or ""),
        str(candidate.get("subject") or ""),
    ]
    return [value.strip() for value in values if str(value or "").strip()]


def _reference_metadata_match_strength(
    candidate: dict[str, Any],
    subject: str,
) -> float:
    subject = str(subject or "").strip()
    if not subject:
        return 0.0
    anchor = _biological_query_anchor(subject)
    best = 0.0
    for value in _reference_metadata_values(candidate):
        if not value:
            continue
        if _reference_fuzzy_related(value, subject):
            best = max(best, 1.0)
        elif anchor and _reference_fuzzy_related(value, anchor):
            best = max(best, 0.8)
        else:
            value_l = value.lower()
            subject_l = subject.lower()
            anchor_l = anchor.lower() if anchor else ""
            if subject_l and subject_l in value_l:
                best = max(best, 1.0)
            elif anchor_l and anchor_l in value_l:
                best = max(best, 0.7)
    return best


def _reference_authority_rescue_enabled() -> bool:
    value = config.app.get("openai_image_reference_authority_rescue_enabled", True)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _reference_trusted_min_semantic_score() -> float:
    try:
        value = float(config.app.get("openai_image_reference_trusted_min_semantic_score", 0.18))
    except Exception:
        value = 0.18
    return max(0.0, min(value, 1.0))


def _reference_trusted_min_visibility() -> float:
    try:
        value = float(config.app.get("openai_image_reference_trusted_min_visibility", 0.16))
    except Exception:
        value = 0.16
    return max(0.0, min(value, 1.0))


def _reference_trusted_min_suitability() -> float:
    try:
        value = float(config.app.get("openai_image_reference_trusted_min_suitability", 0.16))
    except Exception:
        value = 0.16
    return max(0.0, min(value, 1.0))


def _reference_wikimedia_rescue_min_semantic_score() -> float:
    try:
        value = float(config.app.get("openai_image_reference_wikimedia_rescue_min_semantic_score", 0.22))
    except Exception:
        value = 0.22
    return max(0.0, min(value, 1.0))


def _reference_rescue_decision(
    *,
    candidate: dict[str, Any],
    evaluation: dict[str, Any],
    subject: str,
) -> tuple[bool, str]:
    if not _reference_authority_rescue_enabled():
        return False, ""
    if not evaluation.get("available"):
        return False, ""

    judgment = evaluation.get("judgment") or {}
    verdict = str(judgment.get("verdict") or "").strip().lower()
    if verdict == "reject":
        return False, ""

    semantic = float(evaluation.get("semantic_score") or 0.0)
    visibility = float(judgment.get("structural_visibility") or 0.0)
    suitability = float(judgment.get("reference_suitability") or 0.0)
    provider = str(candidate.get("provider") or "").lower()
    metadata_strength = _reference_metadata_match_strength(candidate, subject)
    trusted_identity = bool(evaluation.get("source_identity_trusted"))

    min_visibility = _reference_trusted_min_visibility()
    min_suitability = _reference_trusted_min_suitability()

    if (
        trusted_identity
        and semantic >= _reference_trusted_min_semantic_score()
        and visibility >= min_visibility
        and suitability >= min_suitability
    ):
        return True, "trusted_identity_rescue"

    if (
        provider == "wikimedia"
        and metadata_strength >= 0.8
        and semantic >= _reference_wikimedia_rescue_min_semantic_score()
        and visibility >= min_visibility
        and suitability >= min_suitability
    ):
        return True, "wikimedia_metadata_rescue"

    return False, ""


def _balanced_reference_shortlist(
    pool: list[dict[str, Any]],
    *,
    domain: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Keep biological authority from being crowded out by title/resolution score."""
    limit = max(1, int(limit))
    if not pool:
        return []

    groups: dict[str, list[dict[str, Any]]] = {}
    for item in pool:
        provider = str(item.get("provider") or "").lower()
        groups.setdefault(provider, []).append(item)

    for values in groups.values():
        values.sort(
            key=lambda item: float(item.get("heuristic_score") or 0.0),
            reverse=True,
        )

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    if domain == "biological":
        quotas = [
            ("inaturalist", 2),
            ("wikimedia", 2),
            ("openverse", 1),
        ]
    else:
        quotas = [
            ("wikimedia", 2),
            ("openverse", 1),
            ("pexels", 1),
        ]

    for provider, quota in quotas:
        for item in groups.get(provider, [])[:quota]:
            key = _reference_candidate_key(item)
            if key in seen:
                continue
            selected.append(item)
            seen.add(key)
            if len(selected) >= limit:
                return selected

    # Fill remaining slots globally by heuristic score.
    for item in pool:
        key = _reference_candidate_key(item)
        if key in seen:
            continue
        selected.append(item)
        seen.add(key)
        if len(selected) >= limit:
            break
    return selected



def _precision_reference_search_plan(subject: str) -> dict[str, Any]:
    fallback = {
        "domain": "general",
        "canonical_subject": _normalized_reference_subject(subject),
        "queries": [_normalized_reference_subject(subject)] if subject else [],
    }
    try:
        from app.services import llm as llm_service

        plan = llm_service.generate_precision_reference_search_plan(subject=subject)
        if not isinstance(plan, dict):
            return fallback
        domain = str(plan.get("domain") or "general").lower()
        if domain not in {"biological", "general"}:
            domain = "general"
        canonical_subject = _normalized_reference_subject(
            plan.get("canonical_subject") or subject
        )
        if not canonical_subject:
            canonical_subject = fallback["canonical_subject"]

        queries = []
        # Keep the exact scene/reference identity first, then the stable canonical
        # entity, then LLM aliases. This is domain-agnostic and gives specialized
        # providers a broader factual fallback without hardcoding any topic.
        for value in [subject, canonical_subject, *(plan.get("queries") or [])]:
            query = _normalized_reference_subject(value)
            if query and query.lower() not in {item.lower() for item in queries}:
                queries.append(query)

        if not queries:
            queries = fallback["queries"]
        if domain == "biological":
            queries = _sanitize_biological_reference_queries(
                canonical_subject or subject,
                queries,
            )
        return {
            "domain": domain,
            "canonical_subject": canonical_subject,
            "queries": queries[:5],
        }
    except BaseException as exc:
        logger.warning(
            "precision reference search-plan generation failed; using exact subject: "
            f"error={type(exc).__name__}, detail={exc}"
        )
        return fallback


def _search_precision_reference_pool(
    subject: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    plan = _precision_reference_search_plan(subject)
    domain = str(plan.get("domain") or "general")
    queries = list(plan.get("queries") or [subject])
    enabled = _reference_search_providers()

    # Biological image databases are useful only for biological subjects. We still
    # search the general open sources for broader coverage.
    if domain == "biological":
        provider_order = ["inaturalist", "wikimedia", "openverse"]
    else:
        provider_order = ["wikimedia", "openverse", "pexels"]

    provider_order = [provider for provider in provider_order if provider in enabled]

    pooled: list[dict[str, Any]] = []
    provider_counts: dict[str, int] = {}

    for provider in provider_order:
        provider_results: list[dict[str, Any]] = []
        for query in queries:
            if provider == "wikimedia":
                found = _wikimedia_reference_candidates(query, subject)
            elif provider == "openverse":
                found = _openverse_reference_candidates(query, subject)
            elif provider == "inaturalist":
                found = _inaturalist_reference_candidates(query, subject)
            elif provider == "pexels":
                found = _pexels_reference_candidates(query, subject)
            else:
                found = []

            # None is a transient Openverse circuit-break signal: stop trying
            # alternate queries for this provider during the current scene.
            if found is None:
                logger.warning(
                    "precision reference provider circuit opened for this scene: "
                    f"provider={provider}, subject={subject!r}"
                )
                break

            provider_results.extend(found)

            # Avoid multiplying calls once this provider already has enough diversity.
            if len(provider_results) >= _reference_candidates_per_provider():
                break

        # Re-score with the actual search-plan domain and retain a provider-level cap.
        dedup_provider = {}
        for item in provider_results:
            item["heuristic_score"] = (
                _reference_common_heuristic(item, subject, domain)
                - float(item.get("presentation_penalty") or 0.0)
                + (0.10 if provider == "inaturalist" and domain == "biological" else 0.0)
            )
            key = _reference_candidate_key(item)
            previous = dedup_provider.get(key)
            if previous is None or float(item["heuristic_score"]) > float(previous["heuristic_score"]):
                dedup_provider[key] = item

        selected_provider = sorted(
            dedup_provider.values(),
            key=lambda item: float(item.get("heuristic_score") or 0.0),
            reverse=True,
        )[: _reference_candidates_per_provider()]

        provider_counts[provider] = len(selected_provider)
        pooled.extend(selected_provider)
        logger.info(
            "precision reference provider search: "
            f"provider={provider}, subject={subject!r}, "
            f"queries={queries!r}, candidates={len(selected_provider)}"
        )

    deduped = {}
    for item in pooled:
        key = _reference_candidate_key(item)
        previous = deduped.get(key)
        if previous is None or float(item.get("heuristic_score") or 0.0) > float(
            previous.get("heuristic_score") or 0.0
        ):
            deduped[key] = item

    candidates = sorted(
        deduped.values(),
        key=lambda item: float(item.get("heuristic_score") or 0.0),
        reverse=True,
    )
    return candidates, {
        "domain": domain,
        "canonical_subject": plan.get("canonical_subject") or subject,
        "queries": queries,
        "provider_counts": provider_counts,
    }


def _download_reference_candidate(
    candidate: dict[str, Any],
    save_dir: str,
) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    image_url = str(candidate.get("image_url") or "").strip()
    if not image_url:
        return None, None

    os.makedirs(save_dir, exist_ok=True)
    local_path = os.path.join(
        save_dir,
        f"precision-reference-candidate-{uuid.uuid4().hex}.png",
    )
    try:
        if str(candidate.get("provider") or "").lower() == "wikimedia":
            response = _wikimedia_get_with_backoff(
                image_url,
                timeout=_reference_timeout_seconds(),
            )
        else:
            response = requests.get(
                image_url,
                headers={"User-Agent": _REFERENCE_USER_AGENT},
                timeout=_reference_timeout_seconds(),
            )
        response.raise_for_status()
        with Image.open(io.BytesIO(response.content)) as source:
            image = source.convert("RGB")
            if image.width < 160 or image.height < 160:
                logger.warning(
                    "precision reference candidate rejected before analysis: "
                    f"provider={candidate.get('provider')!r}, "
                    f"title={candidate.get('title')!r}, "
                    f"downloaded_size={image.width}x{image.height}, "
                    f"url={image_url!r}"
                )
                return None, None
            original_size = image.size
            image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            image.save(local_path, format="PNG", optimize=True)
            normalized_size = image.size

        info = dict(candidate)
        info["original_download_size"] = list(original_size)
        info["normalized_size"] = list(normalized_size)
        return local_path, info
    except Exception as exc:
        logger.warning(
            "failed to download/decode precision reference candidate: "
            f"provider={candidate.get('provider')!r}, title={candidate.get('title')!r}, "
            f"error={type(exc).__name__}, detail={exc}"
        )
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
        except OSError:
            pass
        return None, None



def _precompute_reference_analysis(
    downloaded: list[tuple[str, dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """Run all BiRefNet work first, then release the ONNX session.

    This keeps BiRefNet and Florence from being resident at the same time inside
    the Streamlit/MoneyPrinterTurbo process.
    """
    results: dict[str, dict[str, Any]] = {}
    if not downloaded:
        return results

    session = None
    try:
        session = _get_precision_rembg_session()
        if session is None:
            return results

        for local_path, candidate in downloaded:
            try:
                features = _precision_candidate_features(local_path, session)
                bbox = None
                area_ratio = None
                if features:
                    raw_bbox = features.get("bbox")
                    if raw_bbox:
                        bbox = tuple(int(v) for v in raw_bbox)
                    if features.get("bbox_area_ratio") is not None:
                        area_ratio = float(features.get("bbox_area_ratio"))
                results[local_path] = {
                    "bbox": bbox,
                    "bbox_area_ratio": area_ratio,
                }
                logger.info(
                    "precision reference BiRefNet preanalysis: "
                    f"provider={candidate.get('provider')}, "
                    f"title={candidate.get('title')!r}, "
                    f"bbox={list(bbox) if bbox else None}, "
                    f"bbox_area_ratio={area_ratio if area_ratio is not None else 'n/a'}"
                )
            except BaseException as exc:
                logger.warning(
                    "reference pre-analysis segmentation failed; "
                    "Florence will use full image: "
                    f"title={candidate.get('title')!r}, "
                    f"error={type(exc).__name__}, detail={exc}"
                )
                results[local_path] = {
                    "bbox": None,
                    "bbox_area_ratio": None,
                }
    finally:
        # Critical memory boundary: Florence is loaded only after this release.
        _release_precision_rembg_session()
        logger.info(
            "precision reference memory boundary: BiRefNet released before Florence"
        )

    return results



def _evaluate_reference_candidate(
    *,
    local_path: str,
    candidate: dict[str, Any],
    subject: str,
    required_features: list[str],
    forbidden_features: list[str],
    analysis_bbox: tuple[int, int, int, int] | None = None,
    analysis_bbox_area_ratio: float | None = None,
) -> dict[str, Any]:
    # BiRefNet analysis is intentionally done in a separate phase before this
    # function. By the time Florence loads, the ONNX segmentation session has
    # already been released, avoiding a large RAM/commit overlap.
    caption, florence_info = _precision_florence_caption(
        local_path,
        bbox=analysis_bbox,
    )
    if not caption:
        return {
            "available": False,
            "caption": "",
            "florence": florence_info,
            "semantic_score": None,
            "analysis_bbox": list(analysis_bbox) if analysis_bbox else None,
        }

    source_identity_trusted, source_identity_label = _reference_identity_trust(
        candidate,
        subject,
    )

    try:
        from app.services import llm as llm_service

        judgment = llm_service.evaluate_precision_reference_caption(
            subject=subject,
            required_features=required_features,
            forbidden_features=forbidden_features,
            visual_caption=caption,
            candidate_title=str(candidate.get("title") or ""),
            candidate_provider=str(candidate.get("provider") or ""),
            source_identity_trusted=source_identity_trusted,
            source_identity_label=source_identity_label,
        )
    except BaseException as exc:
        judgment = {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    semantic_score = (
        float(judgment.get("semantic_score", 0.0))
        if isinstance(judgment, dict) and judgment.get("available")
        else None
    )
    return {
        "available": semantic_score is not None,
        "caption": caption,
        "florence": florence_info,
        "judgment": judgment,
        "semantic_score": semantic_score,
        "source_identity_trusted": source_identity_trusted,
        "source_identity_label": source_identity_label,
        "analysis_bbox": list(analysis_bbox) if analysis_bbox else None,
        "analysis_bbox_area_ratio": (
            round(float(analysis_bbox_area_ratio), 5)
            if analysis_bbox_area_ratio is not None
            else None
        ),
    }


def _select_multisource_precision_reference(
    subject: str,
    save_dir: str,
    *,
    required_features: list[str] | None = None,
    forbidden_features: list[str] | None = None,
) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    """Search several open/reference-friendly providers and select the best image."""
    subject = _normalized_reference_subject(subject)
    if not subject:
        return None, None

    required_features = list(required_features or [])
    forbidden_features = list(forbidden_features or [])

    pool, search_info = _search_precision_reference_pool(subject)
    if not pool:
        logger.warning(
            "no precision reference found across configured providers: "
            f"subject={subject!r}, providers={_reference_search_providers()!r}"
        )
        return None, None

    logger.info(
        "precision reference candidate pool: "
        f"subject={subject!r}, provider_counts={search_info.get('provider_counts')!r}, "
        f"queries={search_info.get('queries')!r}"
    )

    # Keep authoritative biological sources from being crowded out by a high
    # title/resolution score from a less useful provider.
    shortlist = _balanced_reference_shortlist(
        pool,
        domain=str(search_info.get("domain") or "general"),
        limit=_reference_rank_pool_size(),
    )
    downloaded: list[tuple[str, dict[str, Any]]] = []
    for candidate in shortlist:
        local_path, info = _download_reference_candidate(candidate, save_dir)
        if local_path and info:
            downloaded.append((local_path, info))

    if not downloaded:
        return None, None

    # Phase A: BiRefNet only.
    reference_analysis = _precompute_reference_analysis(downloaded)

    # Phase B: Florence only. BiRefNet has already been released.
    evaluated = []
    rescue_best = None
    try:
        for index, (local_path, candidate) in enumerate(downloaded):
            preanalysis = reference_analysis.get(local_path) or {}
            evaluation = _evaluate_reference_candidate(
                local_path=local_path,
                candidate=candidate,
                subject=subject,
                required_features=required_features,
                forbidden_features=forbidden_features,
                analysis_bbox=preanalysis.get("bbox"),
                analysis_bbox_area_ratio=preanalysis.get("bbox_area_ratio"),
            )
            semantic_score = evaluation.get("semantic_score")
            heuristic = float(candidate.get("heuristic_score") or 0.0)

            # Rank-based heuristic normalization avoids depending on provider-specific
            # raw score scales. Semantic visual evidence remains dominant.
            heuristic_rank = 1.0 - (
                index / max(1, len(downloaded) - 1)
            ) if len(downloaded) > 1 else 1.0

            if semantic_score is None:
                combined = 0.25 * heuristic_rank
            else:
                authority_boost = 0.12 if evaluation.get("source_identity_trusted") else 0.0
                combined = 0.90 * float(semantic_score) + 0.10 * heuristic_rank + authority_boost

            rescue_ok, rescue_reason = _reference_rescue_decision(
                candidate=candidate,
                evaluation=evaluation,
                subject=subject,
            )

            row = {
                "path": local_path,
                "candidate": candidate,
                "evaluation": evaluation,
                "combined_score": float(combined),
                "heuristic_rank": float(heuristic_rank),
                "heuristic_score": heuristic,
                "rescue_ok": rescue_ok,
                "rescue_reason": rescue_reason,
            }
            evaluated.append(row)

            if rescue_ok and (
                rescue_best is None or float(row["combined_score"]) > float(rescue_best["combined_score"])
            ):
                rescue_best = row

            logger.info(
                "precision reference candidate evaluation: "
                f"provider={candidate.get('provider')}, "
                f"title={candidate.get('title')!r}, "
                f"trusted_identity={evaluation.get('source_identity_trusted', False)}, "
                f"analysis_bbox={evaluation.get('analysis_bbox')!r}, "
                f"semantic={semantic_score if semantic_score is not None else 'n/a'}, "
                f"combined={combined:.4f}, rescue={rescue_reason or 'no'}"
            )

            # Any provider can finish reference selection early when the image is
            # already semantically good AND structurally useful. Provider authority
            # may support identity, but no provider gets a free pass on morphology.
            if _precision_reference_can_early_accept(
                evaluation,
                semantic_score=semantic_score,
                rescue_ok=rescue_ok,
            ):
                logger.info(
                    "precision reference early accept: "
                    f"provider={candidate.get('provider')!r}, "
                    f"title={candidate.get('title')!r}, "
                    f"semantic={semantic_score}, rescue={rescue_reason or 'no'}, "
                    f"trusted_identity={evaluation.get('source_identity_trusted', False)}"
                )
                break
    finally:
        # Florence is the only analysis model that should still be resident here.
        # BiRefNet was released at the explicit memory boundary before this phase.
        _release_precision_semantic_model()

    semantic_rows = [
        row for row in evaluated
        if row["evaluation"].get("semantic_score") is not None
    ]

    if semantic_rows:
        best = max(semantic_rows, key=lambda row: row["combined_score"])
        best_semantic = float(best["evaluation"]["semantic_score"])
        if best_semantic < _reference_min_semantic_score():
            if rescue_best is not None:
                best = rescue_best
                selection_status = str(best.get("rescue_reason") or "authority_rescue")
                logger.info(
                    "precision reference authority rescue accepted: "
                    f"subject={subject!r}, provider={best['candidate'].get('provider')!r}, "
                    f"title={best['candidate'].get('title')!r}, "
                    f"semantic={float(best['evaluation'].get('semantic_score') or 0.0):.4f}, "
                    f"combined={float(best.get('combined_score') or 0.0):.4f}, "
                    f"mode={selection_status}"
                )
            else:
                logger.warning(
                    "best multisource precision reference did not reach semantic minimum: "
                    f"subject={subject!r}, score={best_semantic:.4f}, "
                    f"minimum={_reference_min_semantic_score():.4f}"
                )
                for row in evaluated:
                    try:
                        os.remove(row["path"])
                    except OSError:
                        pass
                return None, None
        else:
            selection_status = "semantic"
    else:
        # Florence/Qwen unavailable: multisource search is still better than the old
        # Wikimedia-only path, so use the highest heuristic result and record fallback.
        best = max(evaluated, key=lambda row: row["heuristic_score"])
        selection_status = "heuristic_fallback"

    selected_path = best["path"]
    selected = best["candidate"]
    selected_eval = best["evaluation"]

    for row in evaluated:
        if row["path"] == selected_path:
            continue
        try:
            os.remove(row["path"])
        except OSError:
            pass

    reference_info: dict[str, Any] = {
        "provider": str(selected.get("provider") or ""),
        "subject": subject,
        "title": str(selected.get("title") or ""),
        "source_page": selected.get("source_page"),
        "image_url": _safe_public_url(selected.get("image_url")),
        "license": str(selected.get("license") or ""),
        "artist": str(selected.get("creator") or ""),
        "width": selected.get("width"),
        "height": selected.get("height"),
        "query": selected.get("query"),
        "reference_selection": {
            "status": selection_status,
            "domain": search_info.get("domain"),
            "canonical_subject": search_info.get("canonical_subject"),
            "queries": search_info.get("queries"),
            "provider_counts": search_info.get("provider_counts"),
            "shortlist_count": len(downloaded),
            "selected_combined_score": round(float(best["combined_score"]), 4),
            "selected_semantic_score": (
                round(float(selected_eval["semantic_score"]), 4)
                if selected_eval.get("semantic_score") is not None
                else None
            ),
            "selected_caption": str(selected_eval.get("caption") or "")[:1500],
            "selected_judgment": selected_eval.get("judgment"),
            "selected_source_identity_trusted": bool(
                selected_eval.get("source_identity_trusted")
            ),
            "selected_source_identity_label": selected_eval.get(
                "source_identity_label"
            ),
            "selected_analysis_bbox": selected_eval.get("analysis_bbox"),
            "selected_rescue_reason": best.get("rescue_reason"),
        },
    }
    reference_info = {
        key: value
        for key, value in reference_info.items()
        if value not in (None, "", [], {})
    }

    logger.info(
        "multisource precision reference selected: "
        f"subject={subject!r}, provider={selected.get('provider')!r}, "
        f"title={selected.get('title')!r}, "
        f"status={selection_status}, "
        f"license={selected.get('license')!r}"
    )
    return selected_path, reference_info


def _upload_reference_to_comfyui(
    image_path: str,
) -> str:
    upload_url = str(
        config.app.get(
            "openai_image_reference_upload_url",
            _DEFAULT_COMFYUI_REFERENCE_UPLOAD_URL,
        )
        or _DEFAULT_COMFYUI_REFERENCE_UPLOAD_URL
    ).strip()
    if not upload_url:
        return ""

    try:
        timeout_seconds = max(
            5.0,
            float(config.app.get("openai_image_reference_timeout_seconds", 20) or 20),
        )
    except (TypeError, ValueError):
        timeout_seconds = 20.0

    try:
        mime = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
        if image_path.lower().endswith(".webp"):
            mime = "image/webp"
        with open(image_path, "rb") as file_handle:
            response = requests.post(
                upload_url,
                files={
                    "image": (os.path.basename(image_path), file_handle, mime),
                },
                data={"type": "input", "overwrite": "true"},
                timeout=timeout_seconds,
            )
        response.raise_for_status()
        payload = response.json()
        image_name = str(payload.get("name") or "").strip()
        subfolder = str(payload.get("subfolder") or "").strip().strip("/\\")
        if not image_name:
            raise ValueError(f"ComfyUI upload response has no image name: {payload!r}")
        if subfolder:
            image_name = f"{subfolder}/{image_name}"
        logger.info(f"precision reference uploaded to ComfyUI input: {image_name}")
        return image_name
    except Exception as exc:
        logger.warning(
            "failed to upload precision reference to ComfyUI: "
            f"file={image_path!r}, error={type(exc).__name__}, detail={exc}"
        )
        return ""



def _prepare_precision_reference_crop(
    image_path: str,
) -> tuple[str, dict[str, Any]]:
    """Optionally crop only the *reference input* around its segmented subject.

    This never edits a generated FLUX result. BiRefNet is used only to find a
    conservative bounding box. If segmentation/crop quality is questionable, the
    original reference is returned unchanged.
    """
    source_path = Path(image_path)
    metadata: dict[str, Any] = {
        "enabled": _precision_reference_crop_enabled(),
        "used_crop": False,
        "original_file": source_path.name,
        "prepared_file": source_path.name,
        "reason": "",
    }

    if not _precision_reference_crop_enabled():
        metadata["reason"] = "disabled"
        return image_path, metadata

    if not source_path.is_file():
        metadata["reason"] = "source_missing"
        return image_path, metadata

    session = _get_precision_rembg_session()
    if session is None:
        metadata["reason"] = "segmentation_unavailable"
        return image_path, metadata

    try:
        features = _precision_candidate_features(image_path, session)
        if not features:
            metadata["reason"] = "segmentation_failed"
            return image_path, metadata

        bbox = features.get("bbox")
        if (
            not isinstance(bbox, (list, tuple))
            or len(bbox) != 4
        ):
            metadata["reason"] = "bbox_unavailable"
            return image_path, metadata

        left, top, right, bottom = [int(value) for value in bbox]
        bbox_w = max(1, right - left)
        bbox_h = max(1, bottom - top)
        bbox_area_ratio = float(features.get("bbox_area_ratio") or 0.0)

        with Image.open(image_path) as source:
            rgb = source.convert("RGB")
            width, height = rgb.size

            metadata["original_size"] = [width, height]
            metadata["subject_bbox"] = [left, top, right, bottom]
            metadata["subject_bbox_area_ratio_before"] = round(
                bbox_area_ratio,
                5,
            )

            min_ratio = _precision_reference_crop_min_bbox_area_ratio()
            max_ratio = _precision_reference_crop_skip_above_bbox_area_ratio()

            if bbox_area_ratio < min_ratio:
                metadata["reason"] = "subject_too_small_or_uncertain"
                return image_path, metadata

            if bbox_area_ratio >= max_ratio:
                metadata["reason"] = "subject_already_prominent"
                return image_path, metadata

            # If the detected subject already touches the source border, the source
            # itself may be clipped. Cropping cannot recover missing anatomy and may
            # make the problem worse, so preserve the original reference.
            edge_tolerance_x = max(2, round(width * 0.01))
            edge_tolerance_y = max(2, round(height * 0.01))
            if (
                left <= edge_tolerance_x
                or top <= edge_tolerance_y
                or right >= width - edge_tolerance_x
                or bottom >= height - edge_tolerance_y
            ):
                metadata["reason"] = "subject_touches_source_edge"
                return image_path, metadata

            padding = _precision_reference_crop_padding()
            pad_x = max(8, round(bbox_w * padding))
            pad_y = max(8, round(bbox_h * padding))

            crop_left = max(0, left - pad_x)
            crop_top = max(0, top - pad_y)
            crop_right = min(width, right + pad_x)
            crop_bottom = min(height, bottom + pad_y)

            crop_w = max(1, crop_right - crop_left)
            crop_h = max(1, crop_bottom - crop_top)
            crop_area = crop_w * crop_h
            original_area = max(1, width * height)

            metadata["crop_box"] = [
                crop_left,
                crop_top,
                crop_right,
                crop_bottom,
            ]
            metadata["crop_area_ratio_of_original"] = round(
                crop_area / original_area,
                5,
            )

            # If the crop would remove almost nothing, keep the pristine original.
            if crop_area / original_area >= 0.92:
                metadata["reason"] = "crop_not_meaningful"
                return image_path, metadata

            if min(crop_w, crop_h) < _precision_reference_crop_min_short_side():
                metadata["reason"] = "crop_resolution_too_low"
                return image_path, metadata

            prepared = rgb.crop(
                (crop_left, crop_top, crop_right, crop_bottom)
            )

            max_dimension = _precision_reference_crop_max_dimension()
            if max(prepared.size) > max_dimension:
                prepared.thumbnail(
                    (max_dimension, max_dimension),
                    Image.Resampling.LANCZOS,
                )

            # The bbox itself is unchanged relative to the cropped coordinate system.
            bbox_ratio_after = (bbox_w * bbox_h) / max(1, crop_area)
            metadata["subject_bbox_area_ratio_after"] = round(
                bbox_ratio_after,
                5,
            )
            metadata["prepared_size"] = list(prepared.size)

            prepared_path = source_path.with_name(
                f"{source_path.stem}-prepared.png"
            )
            prepared.save(prepared_path, format="PNG", optimize=True)

        metadata["used_crop"] = True
        metadata["prepared_file"] = prepared_path.name
        metadata["reason"] = "subject_focused_crop"
        metadata["padding_ratio"] = round(
            _precision_reference_crop_padding(),
            4,
        )

        logger.info(
            "precision reference crop prepared: "
            f"source={source_path.name!r}, prepared={prepared_path.name!r}, "
            f"bbox_ratio_before={bbox_area_ratio:.4f}, "
            f"bbox_ratio_after={bbox_ratio_after:.4f}, "
            f"crop_box={metadata['crop_box']}"
        )
        return str(prepared_path), metadata
    except BaseException as exc:
        metadata["reason"] = f"crop_exception:{type(exc).__name__}"
        logger.warning(
            "precision reference crop failed; keeping original reference: "
            f"image={image_path!r}, error={type(exc).__name__}, detail={exc}"
        )
        return image_path, metadata
    finally:
        # Reference preparation happens before FLUX. Release BiRefNet so ComfyUI has
        # predictable RAM/VRAM headroom during generation.
        _release_precision_rembg_session()



def _prepare_precision_reference(
    subject: str,
    save_dir: str,
    *,
    required_features: list[str] | None = None,
    forbidden_features: list[str] | None = None,
) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    if not _precision_reference_enabled():
        return None, None

    original_path, reference_info = _select_multisource_precision_reference(
        subject,
        save_dir,
        required_features=required_features,
        forbidden_features=forbidden_features,
    )
    if not original_path:
        return None, None

    prepared_path, preparation_info = _prepare_precision_reference_crop(
        original_path
    )

    comfyui_name = _upload_reference_to_comfyui(prepared_path)
    if not comfyui_name:
        return None, None

    if reference_info is None:
        reference_info = {}

    # Downstream candidate scoring should compare against the same prepared identity
    # reference that FLUX actually received. Keep the source path separately for
    # diagnostics/rollback.
    reference_info["comfyui_input"] = comfyui_name
    reference_info["local_path"] = prepared_path
    reference_info["original_local_path"] = original_path
    reference_info["reference_preparation"] = preparation_info

    logger.info(
        "precision reference ready for FLUX: "
        f"subject={subject!r}, original={Path(original_path).name!r}, "
        f"prepared={Path(prepared_path).name!r}, "
        f"used_crop={bool(preparation_info.get('used_crop'))}, "
        f"reason={preparation_info.get('reason')!r}"
    )
    return comfyui_name, reference_info


def _precision_prompt_with_reference(prompt: str, subject: str) -> str:
    """Legacy single-reference prompt used by FLUX/Klein fallback."""
    subject = _normalized_reference_subject(subject) or "the factual subject"
    return (
        f"Create the requested final scene from scratch. Figure 1 is a factual identity/morphology "
        f"reference ONLY for {subject}; it is not a composition, background, style or camera reference. "
        "Preserve subject-defining anatomy, structure, silhouette, proportions and distinctive physical features. "
        "For every non-identity property, follow the scene direction instead of Figure 1. Do not reproduce the "
        "source photograph's background, crop, border, circular/oval viewing field, microscope eyepiece, specimen "
        "plate, presentation layout, camera angle, magnification, lighting, color cast, depth of field, grain, "
        "noise or exposure unless the scene direction explicitly asks for that exact property. "
        "The final result must be one coherent edge-to-edge image, not a near-copy of the source and not an "
        "isolated cutout. Scene direction: "
        f"{prompt}"
    )


def _qwen_precision_prompt_with_references(
    prompt: str,
    subject: str,
    reference_count: int,
    reference_info: dict[str, Any] | None = None,
) -> str:
    """Give Qwen explicit per-reference roles without assuming every image is the same view."""
    subject = _normalized_reference_subject(subject) or "the factual subject"
    reference_count = max(1, min(int(reference_count or 1), 10))
    pack = [dict(item) for item in ((reference_info or {}).get("reference_pack") or []) if isinstance(item, dict)]
    role_lines = []
    for index in range(1, reference_count + 1):
        item = pack[index - 1] if index - 1 < len(pack) else {}
        role = str(item.get("role") or "identity").strip().lower()
        description = str(item.get("description") or "").strip()
        if role == "identity":
            purpose = f"identity/whole-subject evidence for {subject}"
        elif role == "detail":
            purpose = f"detail evidence for a visible feature of {subject}"
        elif role == "internal":
            purpose = f"internal/anatomical/mechanical evidence related to {subject}"
        elif role == "context":
            purpose = "context/environment evidence only; do not treat it as subject identity"
        else:
            purpose = f"supporting factual evidence related to {subject}"
        if description:
            purpose += f" ({description})"
        role_lines.append(f"<image{index}> is {purpose}")
    role_text = "; ".join(role_lines)
    return (
        f"Reference evidence: {role_text}. "
        f"The target factual subject is {subject}. Preserve identity from identity references and use specialized references only for the factual detail they actually show. "
        "Never force a detail/context reference to redefine the whole subject. Do not inherit any reference background, crop, camera angle, pose, "
        "lighting, color cast, watermark, stock-site text, captions, labels, borders or presentation layout unless the scene explicitly asks for that property. "
        "Do not invent accessories, modifications, anatomy or structures merely because one reference contains an incidental element. "
        "Create a completely new coherent edge-to-edge scene and follow the scene direction for composition, environment, camera and lighting. Scene direction: "
        f"{prompt}"
    )


def generate_images_openai(
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect = VideoAspect.portrait,
    save_dir: str = "",
    route: str = "standard",
    model_override: str = "",
    reference_image: str = "",
    reference_images: list[str] | None = None,
    reference_info: dict[str, Any] | None = None,
    reference_subject: str = "",
    forbidden_features: list[str] | None = None,
) -> List[MaterialInfo]:
    """Generate one image through the OpenAI-compatible bridge.

    Precision requests may carry an ordered Qwen Image 2.1 identity pack. The first
    reference remains the selector's primary comparison image for backwards-compatible
    diagnostics, while every supplied reference is sent to the bridge as
    reference_image, reference_image_2, ...
    """
    aspect = VideoAspect(video_aspect)
    clip_duration = max(int(minimum_duration), 1)
    route = _normalize_openai_image_route(route)
    endpoint, requested_model = _openai_image_endpoint(model_override=model_override)
    image_size = _openai_image_size(aspect, route=route, model=requested_model)
    base_prompt = _openai_image_prompt(search_term, route=route)

    references: list[str] = []
    for value in list(reference_images or []):
        value = str(value or "").strip()
        if value and value not in references:
            references.append(value)
    primary_reference = str(reference_image or "").strip()
    if primary_reference and primary_reference not in references:
        references.insert(0, primary_reference)
    references = references[:10]

    effective_model = requested_model
    fallback_from_model = ""
    used_reference_count = len(references)
    if references and _is_qwen_image_21_model(requested_model):
        final_prompt = _qwen_precision_prompt_with_references(
            base_prompt,
            reference_subject or search_term,
            len(references),
            reference_info=reference_info,
        )
    elif references:
        final_prompt = _precision_prompt_with_reference(
            base_prompt, reference_subject or search_term
        )
    else:
        final_prompt = base_prompt

    payload = {
        "model": requested_model,
        "prompt": final_prompt,
        "n": 1,
        "size": image_size,
    }
    generation_steps = _openai_image_generation_steps(route, requested_model)
    if generation_steps is not None:
        payload["steps"] = generation_steps
    if references and _is_qwen_image_21_model(requested_model):
        payload["negative_prompt"] = _qwen_negative_prompt(forbidden_features)
    for index, reference in enumerate(references, start=1):
        field = "reference_image" if index == 1 else f"reference_image_{index}"
        payload[field] = reference

    logger.info(
        "generating image via openai-compatible endpoint: "
        f"model={requested_model}, route={route}, refs={len(references)}, "
        f"term={search_term!r}, size={image_size}, steps={generation_steps or 'workflow-default'}"
    )
    image_bytes, failure_detail = _request_openai_image(endpoint, payload)

    fallback_model = _precision_fallback_model() if route == "precision" else ""
    can_fallback = bool(
        image_bytes is None
        and references
        and fallback_model
        and fallback_model != requested_model
        and "unconfirmed request error" not in str(failure_detail or "").lower()
    )
    if can_fallback:
        logger.warning(
            "precision primary model failed; trying configured fallback workflow: "
            f"primary={requested_model!r}, fallback={fallback_model!r}, "
            f"detail={failure_detail}"
        )
        fallback_payload = {
            "model": fallback_model,
            "prompt": _precision_prompt_with_reference(
                base_prompt, reference_subject or search_term
            ),
            "n": 1,
            "size": image_size,
            "reference_image": references[0],
        }
        image_bytes, fallback_detail = _request_openai_image(
            endpoint, fallback_payload
        )
        if image_bytes is not None:
            fallback_from_model = requested_model
            effective_model = fallback_model
            used_reference_count = 1
            failure_detail = ""
        else:
            failure_detail = (
                f"primary={failure_detail}; fallback={fallback_detail}"
            )

    if image_bytes is None:
        logger.error(
            f"openai image generation failed: term={search_term!r}, "
            f"detail={failure_detail}"
        )
        return []

    try:
        image_path, width, height = _save_openai_image_file(image_bytes, save_dir)
    except _OpenAIImageDecodeError as e:
        logger.error(
            "openai image response is not a decodable image, skipping term: "
            f"term={search_term!r}, error={type(e).__name__}, detail={e}"
        )
        return []

    item = MaterialInfo()
    item.provider = "openai_image"
    item.url = image_path
    item.duration = clip_duration
    item.source_info = {
        "provider": "openai_image",
        "search_term": search_term,
        "route": route,
        "model": effective_model,
        "requested_model": requested_model,
        "reference_count": used_reference_count,
        "reference": reference_info if references else None,
        "rendition": {
            "id": None,
            "width": width,
            "height": height,
        },
    }
    if fallback_from_model:
        item.source_info["fallback_from_model"] = fallback_from_model
    if item.source_info.get("reference") is None:
        item.source_info.pop("reference", None)
    return [item]




# -----------------------------------------------------------------------------
# Precision candidate analysis helpers
# -----------------------------------------------------------------------------

def _precision_selector_model() -> str:
    """Segmentation model used only to score precision candidates, never to composite."""
    return str(
        config.app.get("openai_image_precision_selector_model", "birefnet-general-lite")
        or "birefnet-general-lite"
    ).strip()


def _get_precision_rembg_session():
    """Create/reuse the optional rembg session used only for candidate analysis."""
    global _precision_rembg_session, _precision_rembg_session_model

    model_name = _precision_selector_model()
    with _precision_rembg_session_lock:
        if (
            _precision_rembg_session is not None
            and _precision_rembg_session_model == model_name
        ):
            return _precision_rembg_session

        try:
            from rembg import new_session
        except BaseException as exc:
            logger.warning(
                "precision candidate selection disabled because rembg is unavailable: "
                f"error={type(exc).__name__}, detail={exc}. "
                "Install it in the MoneyPrinterTurbo Python environment with "
                'python -m pip install "rembg[cpu]"'
            )
            return None

        try:
            logger.info(
                "initializing precision candidate segmentation model: "
                f"model={model_name!r}. The first run may download the ONNX model."
            )
            _precision_rembg_session = new_session(model_name)
            _precision_rembg_session_model = model_name
            return _precision_rembg_session
        except BaseException as exc:
            logger.warning(
                "failed to initialize precision candidate segmentation model: "
                f"model={model_name!r}, error={type(exc).__name__}, detail={exc}"
            )
            _precision_rembg_session = None
            _precision_rembg_session_model = ""
            return None


def _release_precision_rembg_session() -> None:
    """Release ONNX session memory before MoviePy starts rendering frames."""
    global _precision_rembg_session, _precision_rembg_session_model

    with _precision_rembg_session_lock:
        _precision_rembg_session = None
        _precision_rembg_session_model = ""

    gc.collect()


# -----------------------------------------------------------------------------
# Precision full-scene multi-candidate selection
# -----------------------------------------------------------------------------

def _precision_candidate_count() -> int:
    """Profile-aware independent candidate count for strict precision review."""
    profile = _openai_image_performance_profile()
    default_value = int(_openai_image_profile_default(profile, "precision_candidates"))
    try:
        value = int(
            config.app.get(
                f"openai_image_{profile}_precision_candidates",
                default_value,
            )
            or default_value
        )
    except (TypeError, ValueError):
        value = default_value
    return max(1, min(value, 4))

def _precision_adaptive_generation_enabled() -> bool:
    # Fast/Balanced intentionally trust the Qwen edit result and retry only on an
    # actual generation failure. Quality keeps the legacy strict multi-candidate path.
    if _openai_image_performance_profile() != "quality":
        return False
    value = config.app.get("openai_image_precision_adaptive_generation_enabled", True)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)

def _precision_adaptive_max_candidates() -> int:
    """Maximum independent precision attempts for one precision scene."""
    try:
        value = int(config.app.get("openai_image_precision_max_candidates", 4) or 4)
    except (TypeError, ValueError):
        value = 4
    return max(1, min(value, 8))


def _precision_retry_prompt_reinforcement_enabled() -> bool:
    value = config.app.get(
        "openai_image_precision_retry_prompt_reinforcement_enabled",
        True,
    )
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _precision_selection_metadata(item: MaterialInfo | None) -> dict[str, Any]:
    if item is None or not isinstance(item.source_info, dict):
        return {}
    value = item.source_info.get("precision_candidate_selection")
    return value if isinstance(value, dict) else {}


def _precision_retry_prompt(
    base_prompt: str,
    *,
    required_features: list[str],
    previous_selection: dict[str, Any] | None,
) -> str:
    """Reinforce only positive factual traits on retries.

    The base precision renderer deliberately avoids dumping long negative lists into
    FLUX. Adaptive retries keep that rule: they repeat the same scene and strengthen
    only the defining features that must be visible.
    """
    if not _precision_retry_prompt_reinforcement_enabled():
        return base_prompt

    required = [
        str(item or "").strip()
        for item in (required_features or [])
        if str(item or "").strip()
    ]
    if not required:
        return base_prompt

    priority = "; ".join(required[:7])
    suffix = (
        " Retry correction priority: preserve the same subject, environment, camera "
        "and overall scene, but make the factual identity unmistakable. Clearly and "
        f"accurately render these defining visible traits: {priority}. "
        "Do not simplify, substitute or stylize the subject into a different physical form."
    )

    # If the semantic judge supplied a short reason, keep it in logs/metadata rather
    # than feeding free-form negative language back into FLUX.
    return base_prompt.rstrip() + suffix


def _annotate_precision_adaptive_result(
    item: MaterialInfo,
    *,
    generated_count: int,
    max_candidates: int,
    stop_reason: str,
) -> None:
    if not isinstance(item.source_info, dict):
        item.source_info = {}
    selection = item.source_info.get("precision_candidate_selection")
    if not isinstance(selection, dict):
        selection = {}
        item.source_info["precision_candidate_selection"] = selection
    selection["adaptive_generation"] = {
        "enabled": True,
        "generated_count": int(generated_count),
        "max_candidates": int(max_candidates),
        "stop_reason": str(stop_reason),
    }


def _precision_candidate_selection_enabled() -> bool:
    value = config.app.get("openai_image_precision_candidate_selection_enabled", True)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _precision_geometry_first_batch_enabled() -> bool:
    value = config.app.get("openai_image_precision_geometry_first_batch_enabled", True)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _precision_semantic_finalists() -> int:
    try:
        value = int(config.app.get("openai_image_precision_semantic_finalists", 1) or 1)
    except (TypeError, ValueError):
        value = 1
    return max(0, min(value, 2))


def _precision_batch_semantic_enabled() -> bool:
    value = config.app.get("openai_image_precision_batch_semantic_enabled", True)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _precision_forbidden_veto_threshold() -> float:
    try:
        value = float(
            config.app.get(
                "openai_image_precision_forbidden_veto_threshold",
                0.45,
            )
        )
    except (TypeError, ValueError):
        value = 0.45
    return max(0.0, min(value, 1.0))


def _precision_final_semantic_weight() -> float:
    try:
        value = float(
            config.app.get(
                "openai_image_precision_final_semantic_weight",
                0.70,
            )
        )
    except (TypeError, ValueError):
        value = 0.70
    return max(0.0, min(value, 1.0))


def _precision_final_candidate_score(
    geometric_score: float,
    semantic: dict[str, Any] | None,
) -> tuple[float, bool, dict[str, Any]]:
    geometric = max(0.0, min(float(geometric_score), 1.0))
    semantic = semantic if isinstance(semantic, dict) else {}
    judgment = semantic.get("judgment")
    judgment = judgment if isinstance(judgment, dict) else {}

    available = bool(semantic.get("available") and judgment.get("available"))
    if not available:
        return geometric, False, {
            "semantic_available": False,
            "semantic_score": None,
            "forbidden_violation": None,
            "forbidden_veto": False,
            "final_score": round(geometric, 4),
        }

    try:
        semantic_score = float(judgment.get("semantic_score", 0.0) or 0.0)
    except (TypeError, ValueError):
        semantic_score = 0.0
    try:
        violation = float(judgment.get("forbidden_feature_violation", 0.0) or 0.0)
    except (TypeError, ValueError):
        violation = 0.0

    semantic_score = max(0.0, min(semantic_score, 1.0))
    violation = max(0.0, min(violation, 1.0))
    semantic_weight = _precision_final_semantic_weight()
    final_score = (
        semantic_weight * semantic_score
        + (1.0 - semantic_weight) * geometric
    )

    observed_forbidden = judgment.get("observed_forbidden")
    observed_forbidden = (
        [str(item).strip() for item in observed_forbidden if str(item or "").strip()]
        if isinstance(observed_forbidden, list)
        else []
    )
    verdict = str(judgment.get("verdict") or "").strip().lower()

    # Hard veto is intentionally evidence-based: high violation score must also
    # have either an explicit observed forbidden feature or an explicit reject.
    forbidden_veto = bool(
        violation >= _precision_forbidden_veto_threshold()
        and (observed_forbidden or verdict == "reject")
    )

    return float(final_score), forbidden_veto, {
        "semantic_available": True,
        "semantic_score": round(semantic_score, 4),
        "forbidden_violation": round(violation, 4),
        "observed_forbidden": observed_forbidden,
        "verdict": verdict,
        "forbidden_veto": forbidden_veto,
        "semantic_weight": round(semantic_weight, 4),
        "final_score": round(float(final_score), 4),
    }


def _precision_selector_optional_float(key: str) -> float | None:
    """Read an optional selector calibration value.

    Missing/blank values intentionally mean "not calibrated yet". This lets us
    collect real scores from the user's own FLUX/reference pipeline before inventing
    an arbitrary acceptance threshold.
    """
    raw = config.app.get(key)
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning(
            f"invalid precision selector calibration value ignored: {key}={raw!r}"
        )
        return None
    if not math.isfinite(value):
        logger.warning(
            f"non-finite precision selector calibration value ignored: {key}={raw!r}"
        )
        return None
    return value


def _precision_selector_thresholds() -> tuple[float | None, float | None]:
    """Return (minimum absolute score, minimum winner margin).

    Thresholds are deliberately optional. Until we have observed several real
    good/bad candidates, the selector runs in OBSERVE mode instead of pretending an
    uncalibrated number is a reliable quality gate.
    """
    min_score = _precision_selector_optional_float(
        "openai_image_precision_selector_min_score"
    )
    min_margin = _precision_selector_optional_float(
        "openai_image_precision_selector_min_margin"
    )
    return min_score, min_margin


def _precision_selection_status(
    *,
    best_score: float,
    second_score: float | None,
) -> tuple[str, str, float | None, float | None]:
    """Classify selector confidence without changing the chosen image yet.

    Before thresholds are calibrated the status is OBSERVE. Once both values are
    configured:
      PASS      = absolute score is high enough and winner is clearly ahead.
      UNCERTAIN = score passes but the top candidates are too close.
      REJECT    = even the best candidate is below the minimum score.

    The current point-4 implementation is diagnostic only: it still returns the
    best geometric candidate so the video pipeline remains backward compatible.
    Point 5 can use this status to trigger semantic anatomy validation/retries.
    """
    min_score, min_margin = _precision_selector_thresholds()
    if min_score is None or min_margin is None:
        return (
            "observe",
            "selector thresholds are not calibrated yet",
            min_score,
            min_margin,
        )

    if best_score < min_score:
        return (
            "reject",
            f"best score {best_score:.4f} is below minimum {min_score:.4f}",
            min_score,
            min_margin,
        )

    if second_score is not None:
        margin = best_score - second_score
        if margin < min_margin:
            return (
                "uncertain",
                f"winner margin {margin:.4f} is below minimum {min_margin:.4f}",
                min_score,
                min_margin,
            )

    return (
        "pass",
        "geometric selector confidence passed configured thresholds",
        min_score,
        min_margin,
    )


def _record_precision_selection(
    item: MaterialInfo,
    metadata: dict[str, Any],
) -> None:
    """Attach explicit selector state instead of silently calling a fallback a win."""
    if not isinstance(item.source_info, dict):
        item.source_info = {}
    item.source_info["precision_candidate_selection"] = metadata



def _precision_semantic_enabled() -> bool:
    value = config.app.get("openai_image_precision_semantic_enabled", True)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _precision_semantic_model_name() -> str:
    return str(
        config.app.get(
            "openai_image_precision_semantic_model",
            "florence-community/Florence-2-base-ft",
        )
        or "florence-community/Florence-2-base-ft"
    ).strip()


def _precision_semantic_device_requested() -> str:
    value = str(
        config.app.get("openai_image_precision_semantic_device", "cpu") or "cpu"
    ).strip().lower()
    return value if value in {"cpu", "cuda", "auto"} else "cpu"


def _precision_semantic_max_new_tokens() -> int:
    try:
        value = int(
            config.app.get("openai_image_precision_semantic_max_new_tokens", 256)
            or 256
        )
    except (TypeError, ValueError):
        value = 256
    return max(64, min(value, 768))


def _precision_semantic_num_beams() -> int:
    try:
        value = int(config.app.get("openai_image_precision_semantic_num_beams", 3) or 3)
    except (TypeError, ValueError):
        value = 3
    return max(1, min(value, 5))


def _precision_semantic_thresholds() -> tuple[float, float, float]:
    def read_float(key: str, fallback: float) -> float:
        try:
            value = float(config.app.get(key, fallback))
        except (TypeError, ValueError):
            value = fallback
        if not math.isfinite(value):
            value = fallback
        return max(0.0, min(value, 1.0))

    return (
        read_float("openai_image_precision_semantic_min_score", 0.60),
        read_float("openai_image_precision_semantic_min_identity", 0.52),
        read_float(
            "openai_image_precision_semantic_max_forbidden_violation",
            0.60,
        ),
    )


def _precision_semantic_weight() -> float:
    try:
        value = float(config.app.get("openai_image_precision_semantic_weight", 0.80))
    except (TypeError, ValueError):
        value = 0.80
    if not math.isfinite(value):
        value = 0.80
    return max(0.0, min(value, 1.0))


def _get_precision_semantic_model():
    """Load Florence-2 lazily and return (model, processor, torch, device, dtype).

    CPU is the default even when CUDA is available. FLUX is already using the GPU
    through ComfyUI, so keeping this small vision judge on CPU avoids VRAM contention.
    """
    global _precision_semantic_model
    global _precision_semantic_processor
    global _precision_semantic_model_name_loaded
    global _precision_semantic_device_loaded

    if not _precision_semantic_enabled():
        return None

    model_name = _precision_semantic_model_name()
    requested_device = _precision_semantic_device_requested()

    with _precision_semantic_lock:
        try:
            import torch
            from transformers import AutoProcessor
            try:
                from transformers import Florence2ForConditionalGeneration
                florence_model_class = Florence2ForConditionalGeneration
            except ImportError:
                # Compatibility fallback for Transformers builds exposing Florence
                # through the generic multimodal auto-class.
                from transformers import AutoModelForMultimodalLM
                florence_model_class = AutoModelForMultimodalLM
        except BaseException as exc:
            logger.warning(
                "precision semantic judge unavailable because Florence dependencies "
                "are not installed: "
                f"error={type(exc).__name__}, detail={exc}. "
                "Run install_precision_vision.ps1 from the patch package."
            )
            return None

        if requested_device == "cuda":
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        elif requested_device == "auto":
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        else:
            device = "cpu"

        if (
            _precision_semantic_model is not None
            and _precision_semantic_processor is not None
            and _precision_semantic_model_name_loaded == model_name
            and _precision_semantic_device_loaded == device
        ):
            dtype = torch.float16 if device.startswith("cuda") else torch.float32
            return (
                _precision_semantic_model,
                _precision_semantic_processor,
                torch,
                device,
                dtype,
            )

        # A configuration/model/device change must not leave the old model resident.
        _release_precision_semantic_model()

        dtype = torch.float16 if device.startswith("cuda") else torch.float32
        try:
            logger.info(
                "loading native Florence-2 precision semantic judge: "
                f"model={model_name!r}, device={device!r}. "
                "The first run will download the smaller Base FT checkpoint."
            )
            # florence-community checkpoints are converted to the native
            # Transformers Florence implementation, avoiding Microsoft's older
            # trust_remote_code loader that triggered _supports_sdpa failures.
            processor = AutoProcessor.from_pretrained(model_name)
            model = florence_model_class.from_pretrained(
                model_name,
                torch_dtype=dtype,
            )
            model = model.to(device)
            model.eval()
        except BaseException as exc:
            logger.warning(
                "failed to load Florence-2 precision semantic judge: "
                f"model={model_name!r}, device={device!r}, "
                f"error={type(exc).__name__}, detail={exc}"
            )
            _precision_semantic_model = None
            _precision_semantic_processor = None
            _precision_semantic_model_name_loaded = ""
            _precision_semantic_device_loaded = ""
            gc.collect()
            return None

        _precision_semantic_model = model
        _precision_semantic_processor = processor
        _precision_semantic_model_name_loaded = model_name
        _precision_semantic_device_loaded = device
        return model, processor, torch, device, dtype


def _release_precision_semantic_model() -> None:
    """Release Florence-2 after each precision scene to keep local memory predictable."""
    global _precision_semantic_model
    global _precision_semantic_processor
    global _precision_semantic_model_name_loaded
    global _precision_semantic_device_loaded

    model = _precision_semantic_model
    _precision_semantic_model = None
    _precision_semantic_processor = None
    _precision_semantic_model_name_loaded = ""
    device = _precision_semantic_device_loaded
    _precision_semantic_device_loaded = ""

    try:
        if model is not None:
            del model
        import torch
        if device.startswith("cuda") and torch.cuda.is_available():
            torch.cuda.empty_cache()
    except BaseException:
        pass
    gc.collect()


def _precision_florence_caption(
    image_path: str,
    *,
    bbox: tuple[int, int, int, int] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Describe the main generated subject with Florence-2.

    The crop is only analysis input. The candidate image is never modified.
    """
    runtime = _get_precision_semantic_model()
    if runtime is None:
        return "", {"available": False, "error": "Florence-2 unavailable"}

    model, processor, torch, device, dtype = runtime
    task_prompt = "<MORE_DETAILED_CAPTION>"

    try:
        with Image.open(image_path) as source:
            image = source.convert("RGB")
            original_size = image.size

            if bbox:
                left, top, right, bottom = [int(v) for v in bbox]
                bw = max(1, right - left)
                bh = max(1, bottom - top)
                pad_x = max(4, round(bw * 0.10))
                pad_y = max(4, round(bh * 0.10))
                crop_box = (
                    max(0, left - pad_x),
                    max(0, top - pad_y),
                    min(image.width, right + pad_x),
                    min(image.height, bottom + pad_y),
                )
                if crop_box[2] > crop_box[0] and crop_box[3] > crop_box[1]:
                    image = image.crop(crop_box)
                else:
                    crop_box = None
            else:
                crop_box = None

            inputs = processor(
                text=task_prompt,
                images=image,
                return_tensors="pt",
            )

            prepared = {}
            for key, value in inputs.items():
                if not hasattr(value, "to"):
                    prepared[key] = value
                    continue
                value = value.to(device)
                if key == "pixel_values" and device.startswith("cuda"):
                    value = value.to(dtype=dtype)
                prepared[key] = value

            with torch.inference_mode():
                generated_ids = model.generate(
                    input_ids=prepared.get("input_ids"),
                    pixel_values=prepared.get("pixel_values"),
                    attention_mask=prepared.get("attention_mask"),
                    max_new_tokens=_precision_semantic_max_new_tokens(),
                    num_beams=_precision_semantic_num_beams(),
                    do_sample=False,
                )

            generated_text = processor.batch_decode(
                generated_ids,
                skip_special_tokens=False,
            )[0]

            parsed = processor.post_process_generation(
                generated_text,
                task=task_prompt,
                image_size=(image.width, image.height),
            )
            if isinstance(parsed, dict):
                caption = str(parsed.get(task_prompt) or "").strip()
                if not caption and parsed:
                    caption = str(next(iter(parsed.values())) or "").strip()
            else:
                caption = str(parsed or "").strip()

            if not caption:
                caption = processor.batch_decode(
                    generated_ids,
                    skip_special_tokens=True,
                )[0].strip()

        return caption, {
            "available": bool(caption),
            "model": _precision_semantic_model_name(),
            "device": device,
            "task": task_prompt,
            "original_size": list(original_size),
            "analysis_crop": list(crop_box) if crop_box else None,
        }
    except BaseException as exc:
        logger.warning(
            "Florence-2 precision caption failed: "
            f"image={image_path!r}, error={type(exc).__name__}, detail={exc}"
        )
        return "", {
            "available": False,
            "model": _precision_semantic_model_name(),
            "device": device,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _precision_semantic_evaluation(
    *,
    candidate: MaterialInfo,
    candidate_features: dict[str, Any],
    subject: str,
    required_features: list[str],
    forbidden_features: list[str],
) -> dict[str, Any]:
    """Caption a candidate with Florence-2, then judge it with the configured text LLM."""
    if not _precision_semantic_enabled():
        return {"available": False, "reason": "semantic judge disabled"}

    caption, florence_info = _precision_florence_caption(
        candidate.url,
        bbox=candidate_features.get("bbox"),
    )
    if not caption:
        return {
            "available": False,
            "reason": "Florence-2 could not produce a caption",
            "florence": florence_info,
        }

    try:
        # Lazy import avoids a service-layer cycle during application startup.
        from app.services import llm as llm_service

        judgment = llm_service.evaluate_precision_visual_caption(
            subject=subject,
            required_features=required_features,
            forbidden_features=forbidden_features,
            visual_caption=caption,
        )
    except BaseException as exc:
        judgment = {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    return {
        "available": bool(judgment.get("available")),
        "caption": caption,
        "florence": florence_info,
        "judgment": judgment,
    }


def _precision_combined_candidate_score(
    geometric_score: float,
    semantic_evaluation: dict[str, Any] | None,
) -> tuple[float, dict[str, Any]]:
    """Let semantic identity dominate geometry while keeping geometry as a useful prior."""
    geometric_01 = max(0.0, min(float(geometric_score), 1.0))
    if not semantic_evaluation or not semantic_evaluation.get("available"):
        return geometric_01, {
            "semantic_available": False,
            "geometric_component": round(geometric_01, 4),
            "semantic_component": None,
            "semantic_weight": 0.0,
        }

    judgment = semantic_evaluation.get("judgment")
    judgment = judgment if isinstance(judgment, dict) else {}
    try:
        semantic_score = float(judgment.get("semantic_score", 0.0))
    except (TypeError, ValueError):
        semantic_score = 0.0
    semantic_score = max(0.0, min(semantic_score, 1.0))

    semantic_weight = _precision_semantic_weight()
    combined = (
        semantic_weight * semantic_score
        + (1.0 - semantic_weight) * geometric_01
    )
    return float(combined), {
        "semantic_available": True,
        "geometric_component": round(geometric_01, 4),
        "semantic_component": round(semantic_score, 4),
        "semantic_weight": round(semantic_weight, 4),
    }


def _precision_semantic_gate(
    semantic_evaluation: dict[str, Any] | None,
) -> tuple[bool | None, str]:
    """Return True/False for semantic acceptance, or None when semantic evidence is unavailable."""
    if not semantic_evaluation or not semantic_evaluation.get("available"):
        return None, "semantic evidence unavailable"

    judgment = semantic_evaluation.get("judgment")
    if not isinstance(judgment, dict) or not judgment.get("available"):
        return None, "text semantic judgment unavailable"

    min_score, min_identity, max_violation = _precision_semantic_thresholds()

    semantic_score = float(judgment.get("semantic_score", 0.0) or 0.0)
    identity = float(judgment.get("identity_confidence", 0.0) or 0.0)
    violation = float(judgment.get("forbidden_feature_violation", 0.0) or 0.0)

    if semantic_score < min_score:
        return False, (
            f"semantic score {semantic_score:.4f} < minimum {min_score:.4f}"
        )
    if identity < min_identity:
        return False, (
            f"identity confidence {identity:.4f} < minimum {min_identity:.4f}"
        )
    if violation > max_violation:
        return False, (
            f"forbidden-feature violation {violation:.4f} > maximum {max_violation:.4f}"
        )
    return True, "semantic identity/structure gate passed"


def _dct_basis(size: int) -> np.ndarray:
    """Small orthonormal DCT-II basis used by our dependency-free pHash."""
    x = np.arange(size, dtype=np.float32)
    k = np.arange(size, dtype=np.float32)[:, None]
    basis = np.cos(np.pi * (2.0 * x + 1.0) * k / (2.0 * size))
    basis[0, :] *= 1.0 / np.sqrt(2.0)
    basis *= np.sqrt(2.0 / size)
    return basis.astype(np.float32, copy=False)


def _image_phash_bits(image: Image.Image, hash_size: int = 8) -> np.ndarray:
    """Return a compact perceptual hash without adding a new ML dependency."""
    side = hash_size * 4
    gray = image.convert("L").resize((side, side), Image.Resampling.LANCZOS)
    arr = np.asarray(gray, dtype=np.float32)
    basis = _dct_basis(side)
    dct = basis @ arr @ basis.T
    low = dct[:hash_size, :hash_size].copy()
    flattened = low.reshape(-1)
    # Ignore the DC term when calculating the median threshold.
    threshold = float(np.median(flattened[1:])) if flattened.size > 1 else 0.0
    return flattened > threshold


def _hash_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape or a.size == 0:
        return 0.0
    return float(1.0 - np.mean(a != b))


def _normalized_mask_canvas(mask_crop: Image.Image, canvas_size: int = 96) -> np.ndarray:
    """Normalize silhouette position/scale while preserving its aspect ratio."""
    mask_crop = mask_crop.convert("L")
    width, height = mask_crop.size
    if width <= 0 or height <= 0:
        return np.zeros((canvas_size, canvas_size), dtype=bool)

    max_subject = int(round(canvas_size * 0.86))
    scale = min(max_subject / width, max_subject / height)
    new_w = max(1, int(round(width * scale)))
    new_h = max(1, int(round(height * scale)))
    resized = mask_crop.resize((new_w, new_h), Image.Resampling.BILINEAR)

    canvas = Image.new("L", (canvas_size, canvas_size), 0)
    canvas.paste(
        resized,
        ((canvas_size - new_w) // 2, (canvas_size - new_h) // 2),
    )
    return np.asarray(canvas, dtype=np.uint8) >= 96


def _mask_iou(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        return 0.0
    union = np.logical_or(a, b).sum()
    if union <= 0:
        return 0.0
    return float(np.logical_and(a, b).sum() / union)


def _precision_candidate_features(
    image_path: str,
    session,
) -> dict[str, Any] | None:
    """Extract foreground-aware visual features for reference matching.

    This does NOT modify the generated image. BiRefNet is used only to estimate
    the main-subject silhouette/crop for scoring.
    """
    try:
        from rembg import remove

        with Image.open(image_path) as source:
            rgb = source.convert("RGB")
            full_hash = _image_phash_bits(rgb)

            mask = remove(
                rgb,
                session=session,
                only_mask=True,
                post_process_mask=True,
            )
            if not isinstance(mask, Image.Image):
                mask = Image.open(io.BytesIO(mask))
            mask = mask.convert("L")

            binary = mask.point(lambda p: 255 if p >= 64 else 0)
            bbox = binary.getbbox()
            if not bbox:
                return None

            left, top, right, bottom = bbox
            bbox_w = max(1, right - left)
            bbox_h = max(1, bottom - top)
            bbox_area_ratio = (bbox_w * bbox_h) / max(1, rgb.width * rgb.height)

            # Reject obvious segmentation failures (almost nothing / whole frame).
            if bbox_area_ratio < 0.003 or bbox_area_ratio > 0.97:
                return None

            pad_x = max(2, int(round(bbox_w * 0.04)))
            pad_y = max(2, int(round(bbox_h * 0.04)))
            crop_box = (
                max(0, left - pad_x),
                max(0, top - pad_y),
                min(rgb.width, right + pad_x),
                min(rgb.height, bottom + pad_y),
            )
            subject_crop = rgb.crop(crop_box)
            subject_hash = _image_phash_bits(subject_crop)

            mask_crop = mask.crop((left, top, right, bottom))
            normalized_mask = _normalized_mask_canvas(mask_crop)
            fill_ratio = float(np.mean(normalized_mask))
            aspect_ratio = bbox_w / max(1.0, float(bbox_h))

            # Compare presentation/background separately from the subject. Fill the
            # segmented foreground with the median unmasked background color before
            # hashing; this lets the selector penalize copied reference framing even
            # when the candidate subject itself is accurate.
            rgb_array = np.asarray(rgb, dtype=np.uint8)
            mask_array = np.asarray(mask, dtype=np.uint8)
            background_pixels = rgb_array[mask_array < 64]
            if background_pixels.size:
                neutral_rgb = tuple(
                    int(value) for value in np.median(background_pixels, axis=0)
                )
            else:
                neutral_rgb = (127, 127, 127)
            neutral = Image.new("RGB", rgb.size, neutral_rgb)
            background_only = Image.composite(neutral, rgb, mask)
            background_hash = _image_phash_bits(background_only)

            return {
                "full_hash": full_hash,
                "subject_hash": subject_hash,
                "background_hash": background_hash,
                "mask": normalized_mask,
                "fill_ratio": fill_ratio,
                "aspect_ratio": aspect_ratio,
                "bbox_area_ratio": float(bbox_area_ratio),
                "bbox": (left, top, right, bottom),
            }
    except BaseException as exc:
        logger.warning(
            "precision candidate feature extraction failed: "
            f"image={image_path!r}, error={type(exc).__name__}, detail={exc}"
        )
        return None


def _precision_reference_match_score(
    reference_features: dict[str, Any],
    candidate_features: dict[str, Any],
) -> tuple[float, dict[str, float]]:
    """Prefer factual subject similarity while penalizing near-copy framing.

    The selector intentionally does not try to judge artistic beauty. It answers a
    narrower question: among several full-scene FLUX renders of the same prompt,
    which one preserves the reference subject's structure most plausibly without
    simply recreating the whole source photograph?
    """
    reference_subject_hash = reference_features["subject_hash"]
    candidate_subject_hash = candidate_features["subject_hash"]

    subject_hash_similarity = max(
        _hash_similarity(reference_subject_hash, candidate_subject_hash),
        _hash_similarity(reference_subject_hash, candidate_subject_hash[::-1]),
    )

    reference_mask = reference_features["mask"]
    candidate_mask = candidate_features["mask"]
    silhouette_iou = max(
        _mask_iou(reference_mask, candidate_mask),
        _mask_iou(reference_mask, np.fliplr(candidate_mask)),
    )

    ref_aspect = max(1e-4, float(reference_features["aspect_ratio"]))
    cand_aspect = max(1e-4, float(candidate_features["aspect_ratio"]))
    aspect_similarity = float(
        math.exp(-abs(math.log(cand_aspect / ref_aspect)))
    )

    ref_fill = max(0.05, float(reference_features["fill_ratio"]))
    cand_fill = float(candidate_features["fill_ratio"])
    fill_similarity = max(
        0.0,
        1.0 - abs(cand_fill - ref_fill) / max(ref_fill, 1.0 - ref_fill, 0.15),
    )

    # Identity similarity is desirable; presentation similarity is not. Penalize
    # both the whole reference photograph and, more strongly, its subject-masked
    # background/framing. This stays topic-agnostic and catches copied viewports,
    # studio backdrops, plates, borders or other source-photo presentation choices.
    full_image_similarity = _hash_similarity(
        reference_features["full_hash"],
        candidate_features["full_hash"],
    )
    background_similarity = _hash_similarity(
        reference_features["background_hash"],
        candidate_features["background_hash"],
    )

    score = (
        0.48 * subject_hash_similarity
        + 0.27 * silhouette_iou
        + 0.15 * aspect_similarity
        + 0.10 * fill_similarity
        - 0.06 * full_image_similarity
        - 0.18 * background_similarity
    )

    details = {
        "subject_hash": round(subject_hash_similarity, 4),
        "silhouette_iou": round(silhouette_iou, 4),
        "aspect": round(aspect_similarity, 4),
        "fill": round(fill_similarity, 4),
        "reference_full_image_similarity_penalty": round(full_image_similarity, 4),
        "reference_background_similarity_penalty": round(background_similarity, 4),
        "score": round(float(score), 4),
    }
    return float(score), details



def _select_precision_candidate_geometry_first(
    candidates: list[MaterialInfo],
    reference_info: dict[str, Any] | None,
    *,
    subject: str,
    required_features: list[str],
    forbidden_features: list[str],
    release_models: bool = True,
) -> MaterialInfo:
    """Cheap geometry pre-pass + semantic comparison of the complete small batch.

    V5 keeps the stable V4 order:
      FLUX batch first -> MPT vision models afterwards.

    Unlike V4, geometry does not decide by itself. Both candidates can be captioned
    and judged together in one Qwen call. Clear forbidden/wrong-lookalike evidence
    vetoes a candidate when another non-vetoed option exists.
    """
    if not candidates:
        raise ValueError("precision geometry-first selector received no candidates")

    reference_path = ""
    if isinstance(reference_info, dict):
        reference_path = str(reference_info.get("local_path") or "").strip()

    if not reference_path or not Path(reference_path).is_file():
        winner = candidates[0]
        _record_precision_selection(
            winner,
            {
                "status": "unavailable",
                "mode": "semantic_veto_batch",
                "reason": "selector has no usable local reference file",
                "candidate_count": len(candidates),
                "selected_index": 1,
                "scores": [],
            },
        )
        return winner

    session = _get_precision_rembg_session()
    if session is None:
        winner = candidates[0]
        _record_precision_selection(
            winner,
            {
                "status": "unavailable",
                "mode": "semantic_veto_batch",
                "reason": "segmentation model could not be initialized",
                "candidate_count": len(candidates),
                "selected_index": 1,
                "scores": [],
            },
        )
        return winner

    rows: list[dict[str, Any]] = []
    try:
        reference_features = _precision_candidate_features(reference_path, session)
        if reference_features is None:
            winner = candidates[0]
            _record_precision_selection(
                winner,
                {
                    "status": "unavailable",
                    "mode": "semantic_veto_batch",
                    "reason": "reference image could not be segmented/scored",
                    "candidate_count": len(candidates),
                    "selected_index": 1,
                    "scores": [],
                },
            )
            return winner

        # Phase A: cheap reference/shape scoring for all generated candidates.
        for index, candidate in enumerate(candidates):
            features = _precision_candidate_features(candidate.url, session)
            if features is None:
                rows.append(
                    {
                        "index": index,
                        "candidate": candidate,
                        "features": None,
                        "geometric_score": -999.0,
                        "geometric_details": {"score": -999.0},
                    }
                )
                continue

            geometric_score, geometric_details = _precision_reference_match_score(
                reference_features,
                features,
            )
            rows.append(
                {
                    "index": index,
                    "candidate": candidate,
                    "features": features,
                    "geometric_score": float(geometric_score),
                    "geometric_details": geometric_details,
                }
            )

        valid = [row for row in rows if row["geometric_score"] > -900.0]
        if not valid:
            winner = candidates[0]
            _record_precision_selection(
                winner,
                {
                    "status": "unavailable",
                    "mode": "semantic_veto_batch",
                    "reason": "all candidates failed geometric scoring",
                    "candidate_count": len(candidates),
                    "selected_index": 1,
                    "scores": [],
                },
            )
            return winner

        # With the current 2-candidate cap we inspect both. The config remains
        # bounded to at most two to avoid turning this into an expensive N-way judge.
        ordered = sorted(valid, key=lambda row: row["geometric_score"], reverse=True)
        semantic_limit = min(_precision_semantic_finalists(), len(ordered))
        semantic_rows = ordered[:semantic_limit]

        # Caption finalists with one resident Florence instance.
        caption_payload = []
        for row in semantic_rows:
            caption, florence_info = _precision_florence_caption(
                row["candidate"].url,
                bbox=(row["features"] or {}).get("bbox"),
            )
            row["florence_info"] = florence_info
            row["caption"] = caption
            if caption:
                caption_payload.append(
                    {
                        "index": int(row["index"]) + 1,
                        "caption": caption,
                    }
                )

        batch_results = {}
        batch_error = ""
        if caption_payload and _precision_batch_semantic_enabled():
            try:
                from app.services import llm as llm_service

                response = llm_service.evaluate_precision_visual_captions_batch(
                    subject=subject,
                    required_features=required_features,
                    forbidden_features=forbidden_features,
                    candidates=caption_payload,
                )
                if response.get("available"):
                    batch_results = response.get("candidates") or {}
                else:
                    batch_error = str(response.get("error") or "batch semantic unavailable")
            except BaseException as exc:
                batch_error = f"{type(exc).__name__}: {exc}"

        # Fallback keeps the selector functional if the new batch judge fails.
        for row in semantic_rows:
            candidate_index = int(row["index"]) + 1
            judgment = batch_results.get(candidate_index) or batch_results.get(str(candidate_index))
            if isinstance(judgment, dict) and judgment.get("available"):
                semantic = {
                    "available": True,
                    "caption": row.get("caption") or "",
                    "florence": row.get("florence_info") or {},
                    "judgment": judgment,
                }
            elif row.get("caption"):
                semantic = _precision_semantic_evaluation(
                    candidate=row["candidate"],
                    candidate_features=row["features"],
                    subject=subject,
                    required_features=required_features,
                    forbidden_features=forbidden_features,
                )
            else:
                semantic = {
                    "available": False,
                    "reason": batch_error or "Florence caption unavailable",
                }

            row["semantic"] = semantic
            gate, gate_reason = _precision_semantic_gate(semantic)
            row["semantic_gate"] = gate
            row["semantic_gate_reason"] = gate_reason

            final_score, forbidden_veto, final_details = _precision_final_candidate_score(
                row["geometric_score"],
                semantic,
            )
            row["final_score"] = final_score
            row["forbidden_veto"] = forbidden_veto
            row["final_details"] = final_details

        for row in ordered[semantic_limit:]:
            row["semantic"] = {
                "available": False,
                "reason": "outside bounded semantic finalist set",
            }
            row["semantic_gate"] = None
            row["semantic_gate_reason"] = "semantic judge skipped"
            row["final_score"] = float(row["geometric_score"])
            row["forbidden_veto"] = False
            row["final_details"] = {
                "semantic_available": False,
                "final_score": round(float(row["geometric_score"]), 4),
                "forbidden_veto": False,
            }

        # Prefer candidates without explicit forbidden structural evidence.
        eligible = [row for row in ordered if not row.get("forbidden_veto")]
        if eligible:
            ranked = sorted(
                eligible,
                key=lambda row: row.get("final_score", -999.0),
                reverse=True,
            )
            all_vetoed = False
        else:
            # If every candidate has bad evidence, do not arbitrarily fall back to
            # geometry. Pick the least-forbidden option, then use final score.
            ranked = sorted(
                ordered,
                key=lambda row: (
                    float(
                        (row.get("final_details") or {}).get(
                            "forbidden_violation",
                            1.0,
                        )
                        if (row.get("final_details") or {}).get("forbidden_violation") is not None
                        else 1.0
                    ),
                    -float(row.get("final_score", -999.0)),
                ),
            )
            all_vetoed = True

        best = ranked[0]
        winner = best["candidate"]
        best_index = int(best["index"])
        best_final = float(best.get("final_score", best["geometric_score"]))
        best_geometry = float(best["geometric_score"])
        semantic = best.get("semantic") or {}
        judgment = semantic.get("judgment")
        judgment = judgment if isinstance(judgment, dict) else {}
        semantic_gate = best.get("semantic_gate")
        semantic_reason = str(best.get("semantic_gate_reason") or "")

        if all_vetoed:
            status = "all_candidates_forbidden_warning"
            reason = (
                "all generated candidates showed forbidden/wrong-lookalike evidence; "
                "selected the least-forbidden available candidate"
            )
        elif semantic_gate is True:
            status = "pass"
            reason = "best factual candidate passed semantic gate"
        elif semantic.get("available"):
            status = "best_available_semantic_warning"
            reason = (
                "selected by semantic+reference score without forbidden veto; "
                f"semantic gate warning: {semantic_reason}"
            )
        else:
            status = "geometry_fallback"
            reason = "semantic evidence unavailable; selected by reference geometry"

        score_records = []
        for row in rows:
            sem = row.get("semantic")
            sem = sem if isinstance(sem, dict) else {}
            judge = sem.get("judgment")
            judge = judge if isinstance(judge, dict) else {}
            score_records.append(
                {
                    "index": int(row["index"]) + 1,
                    "image": Path(row["candidate"].url).name,
                    "geometric": row.get("geometric_details"),
                    "final": row.get("final_details"),
                    "semantic": {
                        "available": bool(sem.get("available")),
                        "caption": str(sem.get("caption") or "")[:1500],
                        "judgment": judge,
                    },
                    "semantic_gate": row.get("semantic_gate"),
                    "semantic_gate_reason": row.get("semantic_gate_reason"),
                    "forbidden_veto": bool(row.get("forbidden_veto")),
                }
            )

        metadata = {
            "status": status,
            "mode": "semantic_veto_batch",
            "reason": reason,
            "subject": subject,
            "required_features": required_features,
            "forbidden_features": forbidden_features,
            "candidate_count": len(candidates),
            "semantic_finalists": semantic_limit,
            "selected_index": best_index + 1,
            "selected_score": round(best_final, 4),
            "selected_geometry": round(best_geometry, 4),
            "selected_semantic": judgment.get("semantic_score"),
            "selected_forbidden_violation": judgment.get("forbidden_feature_violation"),
            "all_candidates_vetoed": all_vetoed,
            "scores": score_records,
        }
        _record_precision_selection(winner, metadata)

        logger.info(
            "precision semantic-veto decision: "
            f"status={status.upper()}, selected={best_index + 1}/{len(candidates)}, "
            f"final={best_final:.4f}, geometry={best_geometry:.4f}, "
            f"semantic={judgment.get('semantic_score')}, "
            f"forbidden={judgment.get('forbidden_feature_violation')}, "
            f"veto={bool(best.get('forbidden_veto'))}"
        )
        if all_vetoed:
            logger.warning(
                "precision semantic-veto: every candidate carried forbidden evidence; "
                f"selected least-forbidden candidate {best_index + 1}"
            )
        elif semantic_gate is False:
            logger.warning(
                "precision semantic-veto semantic warning: "
                f"selected={best_index + 1}, reason={semantic_reason}"
            )
        return winner
    finally:
        if release_models:
            _release_precision_semantic_model()
            _release_precision_rembg_session()



def _select_precision_candidate(
    candidates: list[MaterialInfo],
    reference_info: dict[str, Any] | None,
    *,
    subject: str = "",
    required_features: list[str] | None = None,
    forbidden_features: list[str] | None = None,
    release_models: bool = True,
) -> MaterialInfo:
    """Choose the best precision candidate using geometry + semantic identity.

    Geometry remains useful for reference-faithful shape/presentation scoring, but
    semantic identity now dominates the final ranking when Florence-2 + the local
    text LLM are available. A bad lookalike can therefore lose even if its silhouette
    happens to resemble the reference.
    """
    if not candidates:
        raise ValueError("precision candidate selector received no candidates")

    required_features = list(required_features or [])
    forbidden_features = list(forbidden_features or [])

    if (
        _precision_geometry_first_batch_enabled()
        and _precision_candidate_selection_enabled()
    ):
        return _select_precision_candidate_geometry_first(
            candidates,
            reference_info,
            subject=subject,
            required_features=required_features,
            forbidden_features=forbidden_features,
            release_models=release_models,
        )

    if not _precision_candidate_selection_enabled():
        winner = candidates[0]
        _record_precision_selection(
            winner,
            {
                "status": "disabled",
                "reason": "precision candidate selection is disabled in config",
                "candidate_count": len(candidates),
                "selected_index": 1,
                "selected_score": None,
                "scores": [],
            },
        )
        return winner

    reference_path = ""
    if isinstance(reference_info, dict):
        reference_path = str(reference_info.get("local_path") or "").strip()

    if not reference_path or not Path(reference_path).is_file():
        winner = candidates[0]
        _record_precision_selection(
            winner,
            {
                "status": "unavailable",
                "reason": "selector has no usable local reference file",
                "candidate_count": len(candidates),
                "selected_index": 1,
                "selected_score": None,
                "scores": [],
            },
        )
        logger.warning(
            "precision candidate decision: status=UNAVAILABLE; "
            "no local reference file, temporarily using candidate 1"
        )
        return winner

    runtime_cache_key = repr(
        (
            reference_path,
            str(subject or "").strip(),
            tuple(str(x or "").strip() for x in required_features),
            tuple(str(x or "").strip() for x in forbidden_features),
        )
    )

    session = _get_precision_rembg_session()
    if session is None:
        winner = candidates[0]
        _record_precision_selection(
            winner,
            {
                "status": "unavailable",
                "reason": "segmentation model could not be initialized",
                "candidate_count": len(candidates),
                "selected_index": 1,
                "selected_score": None,
                "scores": [],
            },
        )
        logger.warning(
            "precision candidate decision: status=UNAVAILABLE; "
            "segmentation unavailable, temporarily using candidate 1"
        )
        return winner

    try:
        reference_features = _precision_candidate_features(reference_path, session)
        if reference_features is None:
            winner = candidates[0]
            _record_precision_selection(
                winner,
                {
                    "status": "unavailable",
                    "reason": "reference image could not be segmented/scored",
                    "candidate_count": len(candidates),
                    "selected_index": 1,
                    "selected_score": None,
                    "scores": [],
                },
            )
            return winner

        rows: list[dict[str, Any]] = []
        for index, candidate in enumerate(candidates):
            cached = None
            if isinstance(candidate.source_info, dict):
                runtime_cache = candidate.source_info.get("_precision_runtime_evaluation_v1")
                if (
                    isinstance(runtime_cache, dict)
                    and runtime_cache.get("cache_key") == runtime_cache_key
                    and isinstance(runtime_cache.get("evaluation"), dict)
                ):
                    cached = dict(runtime_cache["evaluation"])

            if cached is not None:
                row = {
                    "index": index,
                    "candidate": candidate,
                    **cached,
                }
                rows.append(row)
                logger.debug(
                    f"reusing cached precision evaluation {index + 1}/{len(candidates)}: "
                    f"image={Path(candidate.url).name!r}"
                )
                continue

            features = _precision_candidate_features(candidate.url, session)
            if features is None:
                evaluation = {
                    "geometric_score": -999.0,
                    "geometric_details": {"score": -999.0},
                    "semantic": {"available": False, "reason": "segmentation failed"},
                    "combined_score": -999.0,
                    "combined_details": {
                        "semantic_available": False,
                        "geometric_component": None,
                        "semantic_component": None,
                        "semantic_weight": 0.0,
                    },
                    "semantic_gate": None,
                    "semantic_gate_reason": "segmentation failed",
                }
                row = {"index": index, "candidate": candidate, **evaluation}
                rows.append(row)
                if not isinstance(candidate.source_info, dict):
                    candidate.source_info = {}
                candidate.source_info["_precision_runtime_evaluation_v1"] = {
                    "cache_key": runtime_cache_key,
                    "evaluation": evaluation,
                }
                logger.warning(
                    f"precision candidate {index + 1}/{len(candidates)} could not be scored"
                )
                continue

            geometric_score, geometric_details = _precision_reference_match_score(
                reference_features,
                features,
            )
            semantic = _precision_semantic_evaluation(
                candidate=candidate,
                candidate_features=features,
                subject=subject,
                required_features=required_features,
                forbidden_features=forbidden_features,
            )
            combined_score, combined_details = _precision_combined_candidate_score(
                geometric_score,
                semantic,
            )
            semantic_gate, semantic_gate_reason = _precision_semantic_gate(semantic)

            evaluation = {
                "geometric_score": geometric_score,
                "geometric_details": geometric_details,
                "semantic": semantic,
                "combined_score": combined_score,
                "combined_details": combined_details,
                "semantic_gate": semantic_gate,
                "semantic_gate_reason": semantic_gate_reason,
            }
            row = {"index": index, "candidate": candidate, **evaluation}
            rows.append(row)

            if not isinstance(candidate.source_info, dict):
                candidate.source_info = {}
            candidate.source_info["_precision_runtime_evaluation_v1"] = {
                "cache_key": runtime_cache_key,
                "evaluation": evaluation,
            }

            semantic_judgment = (
                semantic.get("judgment")
                if isinstance(semantic, dict)
                else None
            )
            semantic_score = (
                semantic_judgment.get("semantic_score")
                if isinstance(semantic_judgment, dict)
                else None
            )
            logger.info(
                f"precision candidate evaluation {index + 1}/{len(candidates)}: "
                f"geometric={geometric_score:.4f}, "
                f"semantic={semantic_score if semantic_score is not None else 'n/a'}, "
                f"combined={combined_score:.4f}, "
                f"semantic_gate={semantic_gate}, "
                f"image={Path(candidate.url).name!r}"
            )

        valid = [row for row in rows if row["combined_score"] > -900.0]
        if not valid:
            winner = candidates[0]
            _record_precision_selection(
                winner,
                {
                    "status": "unavailable",
                    "reason": "all candidates failed scoring",
                    "candidate_count": len(candidates),
                    "selected_index": 1,
                    "selected_score": None,
                    "scores": [],
                },
            )
            return winner

        # Prefer candidates that explicitly pass semantic validation. If no candidate
        # passes, keep the best available one for now and mark the scene rejected.
        # Point 6 will use that status to regenerate instead of accepting it.
        semantic_pass_rows = [row for row in valid if row["semantic_gate"] is True]
        ranking_pool = semantic_pass_rows or valid
        ordered = sorted(
            ranking_pool,
            key=lambda row: row["combined_score"],
            reverse=True,
        )
        best = ordered[0]
        winner = best["candidate"]
        best_index = int(best["index"])
        best_score = float(best["combined_score"])

        all_ordered = sorted(valid, key=lambda row: row["combined_score"], reverse=True)
        second_score = (
            float(all_ordered[1]["combined_score"])
            if len(all_ordered) > 1
            else None
        )
        margin = best_score - second_score if second_score is not None else None

        if best["semantic_gate"] is True:
            status = "pass"
            reason = best["semantic_gate_reason"]
        elif any(row["semantic_gate"] is not None for row in valid):
            status = "reject"
            reason = (
                "no generated candidate passed the semantic identity/structure gate; "
                f"best candidate: {best['semantic_gate_reason']}"
            )
        else:
            # Florence/Qwen unavailable: retain point-4 geometry diagnostics.
            geometry_ordered = sorted(
                valid,
                key=lambda row: row["geometric_score"],
                reverse=True,
            )
            geometry_best = geometry_ordered[0]
            geometry_second = (
                geometry_ordered[1]["geometric_score"]
                if len(geometry_ordered) > 1
                else None
            )
            status, reason, _, _ = _precision_selection_status(
                best_score=float(geometry_best["geometric_score"]),
                second_score=(
                    float(geometry_second) if geometry_second is not None else None
                ),
            )

        score_records = []
        for row in rows:
            semantic = row.get("semantic")
            semantic = semantic if isinstance(semantic, dict) else {}
            judgment = semantic.get("judgment")
            judgment = judgment if isinstance(judgment, dict) else {}
            score_records.append(
                {
                    "index": int(row["index"]) + 1,
                    "image": Path(row["candidate"].url).name,
                    "geometric": row["geometric_details"],
                    "semantic": {
                        "available": bool(semantic.get("available")),
                        "caption": str(semantic.get("caption") or "")[:1500],
                        "judgment": judgment,
                    },
                    "combined": {
                        "score": (
                            round(float(row["combined_score"]), 4)
                            if row["combined_score"] > -900.0
                            else None
                        ),
                        **row["combined_details"],
                    },
                    "semantic_gate": row["semantic_gate"],
                    "semantic_gate_reason": row["semantic_gate_reason"],
                }
            )

        metadata = {
            "status": status,
            "reason": reason,
            "subject": subject,
            "required_features": required_features,
            "forbidden_features": forbidden_features,
            "candidate_count": len(candidates),
            "selected_index": best_index + 1,
            "selected_score": round(best_score, 4),
            "second_score": (
                round(second_score, 4) if second_score is not None else None
            ),
            "score_margin": round(margin, 4) if margin is not None else None,
            "semantic_thresholds": {
                "min_score": _precision_semantic_thresholds()[0],
                "min_identity": _precision_semantic_thresholds()[1],
                "max_forbidden_violation": _precision_semantic_thresholds()[2],
                "semantic_weight": _precision_semantic_weight(),
            },
            "scores": score_records,
        }
        _record_precision_selection(winner, metadata)

        log_message = (
            "precision candidate decision: "
            f"status={status.upper()}, selected={best_index + 1}/{len(candidates)}, "
            f"combined={best_score:.4f}, "
            f"margin={margin:.4f}" if margin is not None else
            "precision candidate decision: "
            f"status={status.upper()}, selected={best_index + 1}/{len(candidates)}, "
            f"combined={best_score:.4f}, margin=n/a"
        )
        log_message += f", reason={reason}, image={Path(winner.url).name!r}"
        if status == "reject":
            logger.warning(
                log_message
                + ". Point 6 will convert this rejection into adaptive regeneration."
            )
        else:
            logger.info(log_message)

        return winner
    except BaseException as exc:
        winner = candidates[0]
        _record_precision_selection(
            winner,
            {
                "status": "unavailable",
                "reason": f"selector exception: {type(exc).__name__}",
                "candidate_count": len(candidates),
                "selected_index": 1,
                "selected_score": None,
                "scores": [],
            },
        )
        logger.warning(
            "precision candidate decision: status=UNAVAILABLE; "
            "selector failed, temporarily using candidate 1: "
            f"error={type(exc).__name__}, detail={exc}"
        )
        return winner
    finally:
        # Fixed-count callers keep the old short-lived behavior. Adaptive generation
        # can keep both analysis models alive across retries and release them once at
        # scene end, which avoids repeatedly loading Florence from disk.
        if release_models:
            _release_precision_semantic_model()
            _release_precision_rembg_session()


# -----------------------------------------------------------------------------
# Deterministic visual harmonization for precision-reference scenes
# -----------------------------------------------------------------------------

def _openai_image_color_grading_enabled() -> bool:
    value = config.app.get("openai_image_color_grading_enabled", True)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _openai_image_color_grading_strength() -> float:
    try:
        value = float(config.app.get("openai_image_color_grading_strength", 0.62) or 0.62)
    except (TypeError, ValueError):
        value = 0.62
    return max(0.0, min(value, 1.0))


def _image_lab_style_profile(image_path: str) -> dict[str, tuple[float, float, float]] | None:
    """Return lightweight LAB statistics without changing image structure.

    The profile is intentionally low-dimensional: per-channel mean and standard
    deviation. It is enough to pull a precision image toward the most recent
    standard scene's exposure/color language while leaving anatomy and edges intact.
    """
    try:
        with Image.open(image_path) as image:
            sample = image.convert("RGB")
            sample.thumbnail((320, 320), Image.Resampling.LANCZOS)
            lab = sample.convert("LAB")
            stats = ImageStat.Stat(lab)
            return {
                "mean": tuple(float(v) for v in stats.mean[:3]),
                "stddev": tuple(float(v) for v in stats.stddev[:3]),
            }
    except Exception as exc:
        logger.warning(
            "failed to measure OpenAI image style profile: "
            f"image={image_path!r}, error={type(exc).__name__}, detail={exc}"
        )
        return None


def _openai_image_color_grading_limits() -> tuple[float, float, float]:
    try:
        luma_shift = float(config.app.get("openai_image_color_grading_luma_shift_limit", 95) or 95)
    except (TypeError, ValueError):
        luma_shift = 95.0
    try:
        chroma_shift = float(config.app.get("openai_image_color_grading_chroma_shift_limit", 28) or 28)
    except (TypeError, ValueError):
        chroma_shift = 28.0
    try:
        vignette = float(config.app.get("openai_image_color_grading_vignette", 0.16) or 0.16)
    except (TypeError, ValueError):
        vignette = 0.16
    return (
        max(0.0, min(luma_shift, 140.0)),
        max(0.0, min(chroma_shift, 48.0)),
        max(0.0, min(vignette, 0.45)),
    )


def _apply_soft_vignette(image: Image.Image, strength: float) -> Image.Image:
    """Darken only the outer frame; never reshape or regenerate the subject."""
    if strength <= 0:
        return image
    width, height = image.size
    if width < 8 or height < 8:
        return image

    # Build at reduced resolution for speed, then upscale smoothly. The centre stays
    # almost untouched while bright reference-photo borders are made less jarring.
    mask_w = min(384, width)
    mask_h = max(1, round(mask_w * height / width))
    mask = Image.new("L", (mask_w, mask_h), 255)
    draw = ImageDraw.Draw(mask)
    layers = 48
    for index in range(layers):
        t = index / max(layers - 1, 1)
        inset_x = round(mask_w * 0.42 * t)
        inset_y = round(mask_h * 0.42 * t)
        edge = round(255 * (1.0 - strength * (1.0 - t) ** 1.6))
        draw.ellipse(
            (inset_x, inset_y, mask_w - inset_x, mask_h - inset_y),
            fill=max(0, min(255, edge)),
        )
    mask = mask.resize((width, height), Image.Resampling.LANCZOS)
    darkened = Image.new("RGB", image.size, (0, 0, 0))
    return Image.composite(image, darkened, mask)


def _color_grade_precision_image(
    image_path: str,
    target_profile: dict[str, tuple[float, float, float]] | None,
) -> tuple[str, dict[str, Any] | None]:
    """Conservatively match a precision image to the latest standard scene.

    Only monotonic LAB lookup tables plus a soft vignette are used. No inpainting,
    segmentation, generative editing or geometry changes are performed, so the
    factual anatomy supplied by the precision reference is preserved.
    """
    if not target_profile or not _openai_image_color_grading_enabled():
        return image_path, None

    source_profile = _image_lab_style_profile(image_path)
    if not source_profile:
        return image_path, None

    strength = _openai_image_color_grading_strength()
    if strength <= 0:
        return image_path, None
    luma_shift_limit, chroma_shift_limit, vignette_strength = (
        _openai_image_color_grading_limits()
    )

    try:
        with Image.open(image_path) as source_image:
            rgb = source_image.convert("RGB")
            lab = rgb.convert("LAB")
            graded_channels = []
            source_means = source_profile["mean"]
            source_stddev = source_profile["stddev"]
            target_means = target_profile["mean"]
            target_stddev = target_profile["stddev"]

            for channel_index, channel in enumerate(lab.split()[:3]):
                source_mean = float(source_means[channel_index])
                source_std = max(float(source_stddev[channel_index]), 1.0)
                target_mean = float(target_means[channel_index])
                target_std = max(float(target_stddev[channel_index]), 1.0)

                if channel_index == 0:
                    shift_limit = luma_shift_limit
                    scale_min, scale_max = 0.68, 1.42
                else:
                    shift_limit = chroma_shift_limit
                    scale_min, scale_max = 0.76, 1.32

                mean_shift = max(-shift_limit, min(shift_limit, target_mean - source_mean))
                scale = max(scale_min, min(scale_max, target_std / source_std))
                desired_center = source_mean + mean_shift

                lookup = []
                for value in range(256):
                    desired = desired_center + (value - source_mean) * scale
                    blended = (1.0 - strength) * value + strength * desired
                    lookup.append(max(0, min(255, round(blended))))
                graded_channels.append(channel.point(lookup))

            graded = Image.merge("LAB", tuple(graded_channels)).convert("RGB")
            graded = _apply_soft_vignette(graded, vignette_strength)

            source_path = Path(image_path)
            graded_path = source_path.with_name(f"{source_path.stem}-graded.png")
            graded.save(graded_path, format="PNG")

        result_profile = _image_lab_style_profile(str(graded_path))
        metadata: dict[str, Any] = {
            "method": "lab_statistical_match",
            "strength": round(strength, 3),
            "anchor": "latest_standard_scene",
            "vignette": round(vignette_strength, 3),
        }
        if result_profile:
            metadata["result_mean_lab"] = [round(v, 2) for v in result_profile["mean"]]
        logger.info(
            "precision image color grading applied: "
            f"source={Path(image_path).name!r}, output={graded_path.name!r}, "
            f"strength={strength:.2f}"
        )
        return str(graded_path), metadata
    except Exception as exc:
        logger.warning(
            "failed to color-grade precision image; using original image: "
            f"image={image_path!r}, error={type(exc).__name__}, detail={exc}"
        )
        return image_path, None

def _render_openai_image_video(image_path: str, clip_duration: float) -> str:
    """
    把生成的图片渲染成 mp4 片段，复用 local 素材的"图片 → 动态片段"管线。

    渲染失败按素材源约定返回空字符串，由调用方跳过该图片继续。
    """
    try:
        # Free temporary PIL/ONNX objects before MoviePy allocates full-frame
        # NumPy arrays for the slow zoom effect.
        gc.collect()
        return video.render_image_zoom_video(image_path, clip_duration)
    except Exception as e:
        logger.error(
            "failed to render generated image as a video clip: "
            f"image={image_path}, error={type(e).__name__}, detail={e}"
        )
        return ""


def _download_videos_openai_image_on_demand(
    *,
    task_id: str,
    search_terms: List[str],
    video_aspect: VideoAspect,
    audio_duration: float,
    max_clip_duration: int,
    material_directory: str,
    scene_durations: list[float] | None = None,
    scene_routes: list[str] | None = None,
    scene_subjects: list[str] | None = None,
    scene_required_features: list[list[str]] | None = None,
    scene_forbidden_features: list[list[str]] | None = None,
    scene_reference_needs: list[str] | None = None,
    scene_reference_queries: list[str] | None = None,
    scene_shot_types: list[str] | None = None,
    scene_framing_intents: list[str] | None = None,
) -> List[str]:
    """Generate OpenAI-compatible images in narration order.

    When ``scene_durations`` is supplied, each prompt is a semantic scene and the
    rendered zoom clip receives that scene's exact narration-aligned duration.
    Without it, the original uniform-duration behavior is preserved.
    """
    if not material_directory:
        material_directory = utils.task_dir(task_id)

    video_paths: List[str] = []
    material_sources: list[dict[str, Any]] = []
    total_duration = 0.0

    precision_diagnostics: dict[str, Any] = {
        "schema_version": 1,
        "task_id": str(task_id),
        "status": "running",
        "scene_count": len(search_terms),
        "scenes": [],
    }
    _precision_diagnostics_persist(task_id, precision_diagnostics)

    try:
        required_duration = float(audio_duration)
    except (TypeError, ValueError):
        required_duration = 0.0
    if required_duration <= 0:
        logger.warning(
            "skip openai image generation because required audio duration is "
            f"not positive: duration={audio_duration}"
        )
        _persist_material_sources(task_id, material_sources)
        return video_paths

    semantic_timing = bool(scene_durations)
    if semantic_timing and len(scene_durations) != len(search_terms):
        logger.error(
            "semantic OpenAI image timing mismatch: "
            f"prompts={len(search_terms)}, durations={len(scene_durations)}"
        )
        _persist_material_sources(task_id, material_sources)
        return []
    if scene_routes is not None and len(scene_routes) != len(search_terms):
        logger.error(
            "semantic OpenAI image routing mismatch: "
            f"prompts={len(search_terms)}, routes={len(scene_routes)}"
        )
        _persist_material_sources(task_id, material_sources)
        return []
    if scene_subjects is not None and len(scene_subjects) != len(search_terms):
        logger.error(
            "semantic OpenAI image subject mismatch: "
            f"prompts={len(search_terms)}, subjects={len(scene_subjects)}"
        )
        _persist_material_sources(task_id, material_sources)
        return []
    if scene_required_features is not None and len(scene_required_features) != len(search_terms):
        logger.error(
            "semantic OpenAI image required-feature mismatch: "
            f"prompts={len(search_terms)}, metadata={len(scene_required_features)}"
        )
        _persist_material_sources(task_id, material_sources)
        return []
    if scene_forbidden_features is not None and len(scene_forbidden_features) != len(search_terms):
        logger.error(
            "semantic OpenAI image forbidden-feature mismatch: "
            f"prompts={len(search_terms)}, metadata={len(scene_forbidden_features)}"
        )
        _persist_material_sources(task_id, material_sources)
        return []

    precision_fallback_logged = False
    precision_reference_cache: dict[str, tuple[str, dict[str, Any]]] = {}
    manual_reference_pack_cache: tuple[list[str], dict[str, Any]] | None = None
    latest_standard_style_profile: dict[str, tuple[float, float, float]] | None = None
    for scene_index, search_term in enumerate(search_terms):
        if semantic_timing:
            try:
                desired_duration = float(scene_durations[scene_index])
            except (TypeError, ValueError, IndexError):
                logger.error(
                    f"invalid semantic scene duration at index {scene_index}: "
                    f"{scene_durations[scene_index] if scene_index < len(scene_durations) else None}"
                )
                _persist_material_sources(task_id, material_sources)
                return []
            if not math.isfinite(desired_duration) or desired_duration <= 0:
                logger.error(
                    f"semantic scene duration must be positive and finite: "
                    f"scene={scene_index + 1}, duration={desired_duration}"
                )
                _persist_material_sources(task_id, material_sources)
                return []
            desired_duration = max(0.25, desired_duration)
        else:
            desired_duration = float(max_clip_duration)

        route = _normalize_openai_image_route(
            scene_routes[scene_index]
            if scene_routes is not None and scene_index < len(scene_routes)
            else "standard"
        )
        scene_model, precision_fallback = _openai_image_model_for_route(route)
        if route == "precision" and precision_fallback and not precision_fallback_logged:
            logger.warning(
                "precision image route requested but openai_image_precision_model is not configured; "
                "falling back to openai_image_model while keeping the precision prompt"
            )
            precision_fallback_logged = True

        reference_image = ""
        reference_images: list[str] = []
        reference_info: dict[str, Any] | None = None
        reference_subject = (
            str(scene_subjects[scene_index] or "").strip()
            if scene_subjects is not None and scene_index < len(scene_subjects)
            else ""
        )
        required_features = (
            [
                str(feature).strip()
                for feature in (scene_required_features[scene_index] or [])
                if str(feature or "").strip()
            ]
            if scene_required_features is not None
            and scene_index < len(scene_required_features)
            else []
        )
        forbidden_features = (
            [
                str(feature).strip()
                for feature in (scene_forbidden_features[scene_index] or [])
                if str(feature or "").strip()
            ]
            if scene_forbidden_features is not None
            and scene_index < len(scene_forbidden_features)
            else []
        )
        reference_need = (str(scene_reference_needs[scene_index] or "identity").strip().lower() if scene_reference_needs is not None and scene_index < len(scene_reference_needs) else "identity")
        reference_query = (str(scene_reference_queries[scene_index] or "").strip() if scene_reference_queries is not None and scene_index < len(scene_reference_queries) else "")
        shot_type = (str(scene_shot_types[scene_index] or "full").strip().lower() if scene_shot_types is not None and scene_index < len(scene_shot_types) else "full")
        framing_intent = (str(scene_framing_intents[scene_index] or "full_subject").strip().lower() if scene_framing_intents is not None and scene_index < len(scene_framing_intents) else "full_subject")
        if route == "precision" and not precision_fallback:
            manual_mode, manual_entries = _load_manual_precision_reference_manifest(
                material_directory
            )
            use_manual_pack = bool(
                manual_entries and manual_mode in {"user_first", "user_only"}
            )

            if use_manual_pack:
                if manual_reference_pack_cache is None:
                    manual_reference_pack_cache = _prepare_manual_precision_reference_pack(
                        reference_subject,
                        material_directory,
                    )
                cached_images, cached_info = manual_reference_pack_cache
                reference_images = list(cached_images or [])
                if reference_images:
                    reference_image = reference_images[0]
                    reference_info = dict(cached_info or {})
                    reference_info["subject"] = _normalized_reference_subject(
                        reference_subject
                    )
                    reference_info["query"] = _normalized_reference_subject(
                        reference_subject
                    )
                    reference_images, reference_info = _select_manual_references_for_scene(
                        reference_images, reference_info, reference_need, reference_query, max_refs=3
                    )
                    reference_image = reference_images[0] if reference_images else ""
                    logger.info(
                        "using scene-adaptive manual references for precision scene: "
                        f"scene={scene_index + 1}, refs={len(reference_images)}, need={reference_need!r}, "
                        f"shot={shot_type!r}, framing={framing_intent!r}, subject={reference_subject!r}"
                    )
                    selected_roles = {str(item.get("role") or "identity").strip().lower() for item in (reference_info.get("reference_pack") or []) if isinstance(item, dict)}
                    if reference_need in {"detail", "internal", "context"} and reference_need not in selected_roles:
                        search_term = (
                            search_term
                            + f". Reference coverage constraint: no dedicated {reference_need} reference is available for this scene. "
                            "Do not fabricate unsupported fine detail; prefer a truthful, externally supported or contextual interpretation while preserving the requested narration."
                        )
                        logger.warning(
                            "specialized reference coverage unavailable; prompt constrained against fabrication: "
                            f"scene={scene_index + 1}, need={reference_need!r}, roles={sorted(selected_roles)!r}"
                        )

            if not reference_images and manual_mode != "user_only":
                cache_key = _normalized_reference_subject(reference_subject).lower()
                cached_reference = _precision_reference_cache_lookup(
                    precision_reference_cache,
                    reference_subject,
                )
                if cached_reference:
                    reference_image, reference_info = cached_reference
                    reference_images = [reference_image] if reference_image else []
                    if cache_key in precision_reference_cache:
                        logger.info(
                            "reusing automatic precision reference for scene: "
                            f"subject={reference_subject!r}, image={reference_image!r}"
                        )
                elif reference_subject:
                    prepared_reference = _prepare_precision_reference(
                        reference_subject,
                        material_directory,
                        required_features=required_features,
                        forbidden_features=forbidden_features,
                    )
                    if prepared_reference[0]:
                        reference_image = str(prepared_reference[0])
                        reference_images = [reference_image]
                        reference_info = dict(prepared_reference[1] or {})
                        reference_info["manual_reference_mode"] = manual_mode
                        if cache_key:
                            precision_reference_cache[cache_key] = (
                                reference_image,
                                reference_info,
                            )

            if not reference_images:
                if manual_mode == "user_only":
                    logger.error(
                        "precision route requires the user identity pack but no usable "
                        "manual references reached ComfyUI: "
                        f"subject={reference_subject!r}, scene={scene_index + 1}"
                    )
                    _persist_material_sources(task_id, material_sources)
                    return []
                if _precision_standard_fallback_enabled():
                    logger.warning(
                        "precision route has no usable dynamic reference; "
                        "falling back to the standard image workflow because "
                        "openai_image_precision_standard_fallback_enabled=true: "
                        f"subject={reference_subject!r}"
                    )
                    route = "standard"
                    scene_model, _ = _openai_image_model_for_route("standard")
                else:
                    logger.error(
                        "precision route rejected all factual references; refusing "
                        "standard fallback to avoid generating a plausible-looking but "
                        "factually wrong substitute: "
                        f"subject={reference_subject!r}, scene={scene_index + 1}"
                    )
                    _persist_material_sources(task_id, material_sources)
                    return []

        logger.info(
            f"generating OpenAI image scene {scene_index + 1}/{len(search_terms)}: "
            f"route={route}, model={scene_model or '<default>'}, "
            f"duration={desired_duration:.2f}s, prompt={search_term!r}"
        )

        precision_scene_diagnostic: dict[str, Any] | None = None
        if route == "precision":
            precision_scene_diagnostic = _precision_diagnostics_scene_record(
                task_id=task_id,
                scene_index=scene_index,
                prompt=search_term,
                route=route,
                duration=desired_duration,
                canonical_subject=reference_subject,
                required_features=required_features,
                forbidden_features=forbidden_features,
                reference_info=reference_info,
                reference_need=reference_need,
                reference_query=reference_query,
                shot_type=shot_type,
                framing_intent=framing_intent,
            )
            precision_diagnostics["scenes"].append(precision_scene_diagnostic)
            _precision_diagnostics_persist(task_id, precision_diagnostics)

        direct_qwen_accept = bool(
            route == "precision"
            and _qwen_direct_accept_enabled(scene_model, reference_images)
        )
        fixed_candidate_count = (
            1
            if direct_qwen_accept
            else (
                _precision_candidate_count()
                if route == "precision" and reference_images
                else 1
            )
        )
        adaptive_precision = bool(
            route == "precision"
            and reference_images
            and not direct_qwen_accept
            and _precision_adaptive_generation_enabled()
        )
        candidate_limit = (
            _precision_adaptive_max_candidates()
            if adaptive_precision
            else fixed_candidate_count
        )
        candidate_items: list[MaterialInfo] = []
        selected_precision_item: MaterialInfo | None = None
        adaptive_stop_reason = (
            "qwen_direct_accept" if direct_qwen_accept else "fixed_count_completed"
        )
        items: list[MaterialInfo] = []

        try:
            if direct_qwen_accept:
                # Qwen Image 2.1 edit with references is already the identity-preserving
                # stage. Generate once and accept it directly. A second attempt happens
                # only if the first request produced no image at all; we never generate
                # a second image merely because a semantic judge returned UNKNOWN.
                failure_attempts = 2 if _precision_retry_on_true_failure_enabled() else 1
                for generation_attempt in range(failure_attempts):
                    logger.info(
                        "Qwen precision direct generation: "
                        f"scene={scene_index + 1}, attempt={generation_attempt + 1}/{failure_attempts}, "
                        f"refs={len(reference_images)}, profile={_openai_image_performance_profile()}"
                    )
                    generated_items = generate_images_openai(
                        search_term=search_term,
                        minimum_duration=max(1, math.ceil(desired_duration)),
                        video_aspect=video_aspect,
                        save_dir=material_directory,
                        route=route,
                        model_override=scene_model,
                        reference_image=reference_image,
                        reference_images=reference_images,
                        reference_info=reference_info,
                        reference_subject=reference_subject,
                        forbidden_features=forbidden_features,
                    )
                    if generated_items:
                        candidate = generated_items[0]
                        image_size = _openai_image_size(video_aspect, route=route, model=scene_model)
                        valid, validation_reason = _validate_generated_image_basic(candidate.url, image_size)
                        if valid:
                            selected_precision_item = candidate
                            candidate_items.append(selected_precision_item)
                            _record_precision_selection(
                                selected_precision_item,
                                {
                                    "status": "direct_accept",
                                    "reason": (
                                        "Qwen Image 2.1 reference edit accepted directly after lightweight technical validation; "
                                        f"profile={_openai_image_performance_profile()}"
                                    ),
                                    "candidate_count": 1,
                                    "selected_index": 1,
                                    "selected_score": None,
                                    "validation": validation_reason,
                                    "scores": [],
                                },
                            )
                            items = [selected_precision_item]
                            break
                        logger.warning(
                            "Qwen image failed lightweight technical validation; one corrective retry is allowed: "
                            f"scene={scene_index + 1}, reason={validation_reason!r}"
                        )
                        search_term = (
                            search_term + ". CORRECTION: the previous render failed a technical image check ("
                            + validation_reason + "). Produce a normal complete photographic frame at the requested aspect ratio; "
                            "do not return a blank, flat, corrupted or presentation-card image."
                        )
                    else:
                        logger.warning(
                            "Qwen precision generation returned no image; retrying only because "
                            f"the generation actually failed: scene={scene_index + 1}, "
                            f"attempt={generation_attempt + 1}/{failure_attempts}"
                        )
            else:
                for candidate_index in range(candidate_limit):
                    if route == "precision":
                        logger.info(
                            f"generating precision candidate {candidate_index + 1}/{candidate_limit} "
                            f"for scene {scene_index + 1}"
                        )

                    candidate_prompt = search_term
                    if adaptive_precision and candidate_index > 0:
                        previous_selection = _precision_selection_metadata(
                            selected_precision_item
                        )
                        candidate_prompt = _precision_retry_prompt(
                            search_term,
                            required_features=required_features,
                            previous_selection=previous_selection,
                        )
                        logger.info(
                            "adaptive precision retry: generating a new independent "
                            f"candidate after status="
                            f"{str(previous_selection.get('status') or 'unknown').upper()}"
                        )

                    generated_items = generate_images_openai(
                        search_term=candidate_prompt,
                        minimum_duration=max(1, math.ceil(desired_duration)),
                        video_aspect=video_aspect,
                        save_dir=material_directory,
                        route=route,
                        model_override=scene_model,
                        reference_image=reference_image,
                        reference_images=reference_images,
                        reference_info=reference_info,
                        reference_subject=reference_subject,
                        forbidden_features=forbidden_features,
                    )
                    if not generated_items:
                        logger.warning(
                            f"precision candidate generation returned no image: "
                            f"attempt={candidate_index + 1}/{candidate_limit}, "
                            f"scene={scene_index + 1}"
                        )
                        continue

                    candidate_items.append(generated_items[0])

                    if precision_scene_diagnostic is not None:
                        _precision_diagnostics_add_candidate(
                            task_id=task_id,
                            scene_record=precision_scene_diagnostic,
                            candidate=generated_items[0],
                            candidate_index=len(candidate_items),
                        )
                        precision_scene_diagnostic["status"] = "candidates_generated"
                        _precision_diagnostics_persist(
                            task_id,
                            precision_diagnostics,
                        )

                    if not adaptive_precision:
                        continue

                    if _precision_geometry_first_batch_enabled():
                        adaptive_stop_reason = "geometry_first_batch_collecting"
                        continue

                    selected_precision_item = _select_precision_candidate(
                        candidate_items,
                        reference_info,
                        subject=reference_subject,
                        required_features=required_features,
                        forbidden_features=forbidden_features,
                        release_models=not _precision_keep_judges_loaded_between_scenes(),
                    )
                    decision = _precision_selection_metadata(selected_precision_item)
                    status = str(decision.get("status") or "").strip().lower()

                    if status == "pass":
                        adaptive_stop_reason = "semantic_pass"
                        logger.info(
                            "adaptive precision generation accepted a candidate early: "
                            f"scene={scene_index + 1}, "
                            f"generated={len(candidate_items)}/{candidate_limit}, "
                            f"selected={decision.get('selected_index')}"
                        )
                        break

                    if status in {"unavailable", "disabled", "observe"}:
                        if len(candidate_items) >= fixed_candidate_count:
                            adaptive_stop_reason = (
                                f"semantic_{status}_fallback_after_"
                                f"{len(candidate_items)}_candidates"
                            )
                            break
                    else:
                        adaptive_stop_reason = "semantic_retry_needed"

                if route == "precision" and candidate_items:
                    if adaptive_precision:
                        if selected_precision_item is None:
                            selected_precision_item = _select_precision_candidate(
                                candidate_items,
                                reference_info,
                                subject=reference_subject,
                                required_features=required_features,
                                forbidden_features=forbidden_features,
                                release_models=not _precision_keep_judges_loaded_between_scenes(),
                            )

                        final_decision = _precision_selection_metadata(
                            selected_precision_item
                        )
                        final_status = str(
                            final_decision.get("status") or ""
                        ).strip().lower()

                        if _precision_geometry_first_batch_enabled():
                            adaptive_stop_reason = "geometry_first_batch_selected"
                            logger.info(
                                "precision geometry-first batch complete: "
                                f"scene={scene_index + 1}, "
                                f"generated={len(candidate_items)}/{candidate_limit}, "
                                f"selected={final_decision.get('selected_index')}, "
                                f"status={final_status.upper() or 'UNKNOWN'}"
                            )
                        elif (
                            len(candidate_items) >= candidate_limit
                            and final_status != "pass"
                        ):
                            adaptive_stop_reason = "max_candidates_exhausted"

                        _annotate_precision_adaptive_result(
                            selected_precision_item,
                            generated_count=len(candidate_items),
                            max_candidates=candidate_limit,
                            stop_reason=adaptive_stop_reason,
                        )
                        items = [selected_precision_item]
                    else:
                        # Non-adaptive strict mode may still have multiple candidates.
                        # With only one candidate, selecting it directly avoids loading
                        # heavy judge models that cannot change the outcome.
                        if len(candidate_items) == 1:
                            selected_precision_item = candidate_items[0]
                            _record_precision_selection(
                                selected_precision_item,
                                {
                                    "status": "single_candidate_accept",
                                    "reason": "only one candidate exists; selector cannot improve the choice",
                                    "candidate_count": 1,
                                    "selected_index": 1,
                                    "selected_score": None,
                                    "scores": [],
                                },
                            )
                        else:
                            selected_precision_item = _select_precision_candidate(
                                candidate_items,
                                reference_info,
                                subject=reference_subject,
                                required_features=required_features,
                                forbidden_features=forbidden_features,
                                release_models=not _precision_keep_judges_loaded_between_scenes(),
                            )
                        items = [selected_precision_item]
                else:
                    items = candidate_items

            if precision_scene_diagnostic is not None:
                # Direct mode deliberately keeps diagnostics lightweight: record the
                # selected output and metadata, but do not copy or semantically score it.
                if direct_qwen_accept and candidate_items:
                    _precision_diagnostics_add_candidate(
                        task_id=task_id,
                        scene_record=precision_scene_diagnostic,
                        candidate=candidate_items[0],
                        candidate_index=1,
                    )
                chosen_item = (
                    selected_precision_item
                    if selected_precision_item is not None
                    else (items[0] if items else None)
                )
                _precision_diagnostics_finalize_scene(
                    scene_record=precision_scene_diagnostic,
                    candidate_items=candidate_items,
                    selected_item=chosen_item,
                    stop_reason=adaptive_stop_reason,
                )
                _precision_diagnostics_persist(
                    task_id,
                    precision_diagnostics,
                )
        finally:
            if (
                adaptive_precision
                and not _precision_keep_judges_loaded_between_scenes()
            ):
                _release_precision_semantic_model()
                _release_precision_rembg_session()

        # Full-scene single-pass strategy:
        # - standard scenes continue to define the video's color/style anchor;
        # - precision scenes remain exactly as the selected generator produced them: subject + background
        #   already belong to one coherent render;
        # - no rembg, cutout, background replacement or seam inpainting is performed;
        # - deterministic LAB grading may still make a small global color adjustment,
        #   which cannot change anatomy, composition or background geometry.
        if items and route == "standard" and _openai_image_color_grading_enabled():
            measured_profile = _image_lab_style_profile(items[0].url)
            if measured_profile:
                latest_standard_style_profile = measured_profile
                logger.info(
                    "updated OpenAI image style anchor from standard scene: "
                    f"scene={scene_index + 1}, image={Path(items[0].url).name!r}"
                )
        elif items and route == "precision":
            logger.info(
                "precision full-scene single-pass: preserving generated subject/background composition "
                f"for scene={scene_index + 1}, image={Path(items[0].url).name!r}"
            )
            if latest_standard_style_profile:
                graded_path, grading_info = _color_grade_precision_image(
                    items[0].url, latest_standard_style_profile
                )
                items[0].url = graded_path
                if grading_info:
                    if not isinstance(items[0].source_info, dict):
                        items[0].source_info = {}
                    items[0].source_info["color_grading"] = grading_info
            else:
                logger.info(
                    "precision scene has no preceding standard style anchor; "
                    "keeping generated colors unchanged"
                )

        if not items and semantic_timing:
            # Dropping a semantic scene would shift every later image against the
            # narration. Fail the material stage instead of silently misaligning it.
            logger.error(
                f"failed to generate semantic OpenAI image scene {scene_index + 1}; "
                "stop to preserve narration alignment"
            )
            precision_diagnostics["status"] = "failed"
            precision_diagnostics["failure"] = (
                f"failed to generate semantic image scene {scene_index + 1}"
            )
            _precision_diagnostics_persist(task_id, precision_diagnostics)
            _persist_material_sources(task_id, material_sources)
            return []

        scene_rendered = False
        for item in items:
            video_file = _render_openai_image_video(item.url, desired_duration)
            if not video_file:
                continue

            scene_rendered = True
            logger.info(
                f"image material rendered: {video_file}, "
                f"duration={desired_duration:.2f}s"
            )
            video_paths.append(video_file)
            try:
                record = _material_source_record(item, video_file)
                record["duration"] = round(desired_duration, 3)
                material_sources.append(record)
            except Exception as source_error:
                logger.warning(
                    "failed to prepare generated material source record: "
                    f"provider=openai_image, "
                    f"error={type(source_error).__name__}, detail={source_error}"
                )
            total_duration += desired_duration
            if precision_scene_diagnostic is not None:
                precision_scene_diagnostic["rendered_video_file"] = Path(
                    video_file
                ).name
                precision_scene_diagnostic["status"] = (
                    precision_scene_diagnostic.get("status")
                    or "completed"
                )
                _precision_diagnostics_persist(
                    task_id,
                    precision_diagnostics,
                )
            break  # one generated image per semantic prompt

        if semantic_timing and not scene_rendered:
            logger.error(
                f"failed to render semantic OpenAI image scene {scene_index + 1}; "
                "stop to preserve narration alignment"
            )
            precision_diagnostics["status"] = "failed"
            precision_diagnostics["failure"] = (
                f"failed to render semantic image scene {scene_index + 1}"
            )
            _precision_diagnostics_persist(task_id, precision_diagnostics)
            _persist_material_sources(task_id, material_sources)
            return []

        if not semantic_timing and total_duration >= required_duration:
            logger.info(
                "generated image materials cover the required duration, stop "
                f"generating more images: generated={total_duration:.1f}s, "
                f"required={required_duration:.1f}s"
            )
            break

    if semantic_timing:
        logger.info(
            "semantic OpenAI image materials complete: "
            f"scenes={len(video_paths)}, generated={total_duration:.2f}s, "
            f"required={required_duration:.2f}s"
        )

    # Quality mode can cache BiRefNet/Florence across scenes; release once when the
    # whole material batch is finished. Fast/Balanced never load them in Qwen direct mode.
    _release_precision_semantic_model()
    _release_precision_rembg_session()

    logger.success(f"generated and rendered {len(video_paths)} image materials")
    precision_diagnostics["status"] = "completed"
    precision_diagnostics["generated_scene_count"] = len(video_paths)
    precision_diagnostics["generated_visual_duration"] = round(total_duration, 3)
    _precision_diagnostics_persist(task_id, precision_diagnostics)
    _persist_material_sources(task_id, material_sources)
    return video_paths

def _search_videos_with_cache(
    provider: str,
    search_videos: Callable[..., List[MaterialInfo]],
    search_term: str,
    minimum_duration: int,
    video_aspect: VideoAspect,
) -> List[MaterialInfo]:
    """
    统一处理三个在线素材源的 24 小时搜索缓存。

    缓存只包裹搜索 API，不改变后续视频下载与去重逻辑。远端返回空列表时不写
    缓存，因为现有 provider 接口使用空列表同时表示“没有结果”和“请求失败”；
    在两者尚未拆分为明确结果类型前，宁可下次重试，也不能把临时故障缓存一天。
    """
    cache_args = {
        "provider": provider,
        "search_term": search_term,
        "minimum_duration": minimum_duration,
        "video_aspect": video_aspect,
    }

    def load_cache_safely() -> List[MaterialInfo] | None:
        try:
            return material_cache.load_material_search_cache(**cache_args)
        except Exception as exc:
            # 缓存是可选优化，任何缓存实现异常都必须按未命中处理，不能阻断
            # Pexels、Pixabay 或 Coverr 的正常远端搜索。
            logger.warning(
                "material search cache read failed, continue with remote search: "
                f"provider={provider}, error={type(exc).__name__}, detail={exc}"
            )
            return None

    def load_matching_cache() -> tuple[List[MaterialInfo] | None, int]:
        cached_items = load_cache_safely()
        if cached_items is None:
            return None, 0

        filtered_cached_items = _filter_materials_by_aspect(
            cached_items,
            video_aspect,
        )
        ignored_count = len(cached_items) - len(filtered_cached_items)
        if ignored_count:
            # 旧版本缓存可能混入其它方向的素材。即使仍有少量可用条目，也要刷新
            # 完整候选集，否则在缓存有效期内会反复使用同一批少量视频。
            return None, ignored_count
        return filtered_cached_items, 0

    cached_items, ignored_count = load_matching_cache()
    if cached_items is not None:
        return cached_items
    if ignored_count:
        logger.info(
            "material search cache contains mismatched orientations, "
            f"refresh from provider: provider={provider}, term={search_term!r}, "
            f"ignored={ignored_count}"
        )

    cache_lock = material_cache.get_material_search_cache_lock(**cache_args)
    with cache_lock:
        # 等待相同搜索条件的线程完成后再次读取，避免多个 API 任务在首次缓存
        # 未命中时同时请求远端，降低第三方接口限流和风控触发概率。
        cached_items, _ = load_matching_cache()
        if cached_items is not None:
            return cached_items

        items = search_videos(
            search_term=search_term,
            minimum_duration=minimum_duration,
            video_aspect=video_aspect,
        )
        # Provider 正常会写入当前关键词，但测试替身、第三方扩展或旧实现可能
        # 遗漏或携带错误值。缓存读取会根据缓存键恢复该字段，因此远端结果也在
        # 同一入口校正，保证首次搜索与缓存命中的任务来源记录保持一致。
        for item in items:
            if isinstance(item.source_info, dict):
                item.source_info = dict(item.source_info)
                item.source_info["search_term"] = search_term
        if items:
            try:
                material_cache.save_material_search_cache(
                    **cache_args,
                    items=items,
                )
            except Exception as exc:
                logger.warning(
                    "material search cache write failed, use remote results: "
                    f"provider={provider}, error={type(exc).__name__}, detail={exc}"
                )
        return items


def download_videos(
    task_id: str,
    search_terms: List[str],
    source: str = "pexels",
    video_aspect: VideoAspect = VideoAspect.portrait,
    video_concat_mode: VideoConcatMode = VideoConcatMode.random,
    audio_duration: float = 0.0,
    max_clip_duration: int = 5,
    match_script_order: bool = False,
    scene_durations: list[float] | None = None,
    scene_routes: list[str] | None = None,
    scene_subjects: list[str] | None = None,
    scene_required_features: list[list[str]] | None = None,
    scene_forbidden_features: list[list[str]] | None = None,
    scene_reference_needs: list[str] | None = None,
    scene_reference_queries: list[str] | None = None,
    scene_shot_types: list[str] | None = None,
    scene_framing_intents: list[str] | None = None,
) -> List[str]:
    provider = "pexels"
    remote_search_videos = search_videos_pexels
    if source == "pixabay":
        provider = "pixabay"
        remote_search_videos = search_videos_pixabay
    elif source == "coverr":
        provider = "coverr"
        remote_search_videos = search_videos_coverr

    def search_videos(
        search_term: str,
        minimum_duration: int,
        video_aspect: VideoAspect,
    ) -> List[MaterialInfo]:
        return _search_videos_with_cache(
            provider=provider,
            search_videos=remote_search_videos,
            search_term=search_term,
            minimum_duration=minimum_duration,
            video_aspect=video_aspect,
        )

    material_directory = config.app.get("material_directory", "").strip()
    if material_directory == "task":
        material_directory = utils.task_dir(task_id)
    elif material_directory and not os.path.isdir(material_directory):
        material_directory = ""

    if source == "wavespeed":
        # AI 生成按条计费，不能沿用库存源"先为全部关键词取回候选、再挑选"
        # 的流程，否则会为用不到的片段付费。生成源改为逐段按需生成，凑够
        # 所需时长立即停止；也不参与 24 小时搜索缓存——产物 URL 是会过期
        # 的签名地址，且复用缓存会让不同任务反复得到同一段生成视频。
        return _download_videos_wavespeed_on_demand(
            task_id=task_id,
            search_terms=search_terms,
            video_aspect=video_aspect,
            audio_duration=audio_duration,
            max_clip_duration=max_clip_duration,
            material_directory=material_directory,
        )
    if source == "volcengine_seedance":
        # 与 WaveSpeed 相同，方舟官方接口会创建异步付费任务。必须按需逐段
        # 生成，只购买当前配音时长真正需要的素材。
        return _download_videos_seedance_on_demand(
            task_id=task_id,
            search_terms=search_terms,
            video_aspect=video_aspect,
            audio_duration=audio_duration,
            max_clip_duration=max_clip_duration,
            material_directory=material_directory,
        )
    if source == "ofox":
        # 与 WaveSpeed/方舟相同的按需付费语义：OFox 网关的 /v1/videos 会创建
        # 异步付费任务，必须逐段生成、凑够所需时长立即停止；产物地址是会过
        # 期的临时直链，也不参与 24 小时搜索缓存。
        return _download_videos_ofox_on_demand(
            task_id=task_id,
            search_terms=search_terms,
            video_aspect=video_aspect,
            audio_duration=audio_duration,
            max_clip_duration=max_clip_duration,
            material_directory=material_directory,
        )
    if source == "metaso_minimax":
        # 秘塔 MiniMax 同样按远端异步任务计费。它与火山方舟的请求体相似，
        # 但任务查询路径和响应结构不同，因此只共享本地按需生成语义，不复用
        # 供应商客户端，避免协议差异渗入素材编排层。
        return _download_videos_metaso_minimax_on_demand(
            task_id=task_id,
            search_terms=search_terms,
            video_aspect=video_aspect,
            audio_duration=audio_duration,
            max_clip_duration=max_clip_duration,
            material_directory=material_directory,
        )
    if source == "openai_image":
        # 与 WaveSpeed 相同的按需付费语义：文生图按张计费，逐段生成、凑够
        # 所需时长立即停止。生成结果是一次性的本地图片文件，也不参与 24
        # 小时搜索缓存——缓存会让不同任务反复拿到同一张图。
        return _download_videos_openai_image_on_demand(
            task_id=task_id,
            search_terms=search_terms,
            video_aspect=video_aspect,
            audio_duration=audio_duration,
            max_clip_duration=max_clip_duration,
            material_directory=material_directory,
            scene_durations=scene_durations,
            scene_routes=scene_routes,
            scene_subjects=scene_subjects,
            scene_required_features=scene_required_features,
            scene_forbidden_features=scene_forbidden_features,
            scene_reference_needs=scene_reference_needs,
            scene_reference_queries=scene_reference_queries,
            scene_shot_types=scene_shot_types,
            scene_framing_intents=scene_framing_intents,
        )

    if match_script_order:
        return _download_videos_by_script_order(
            task_id=task_id,
            search_terms=search_terms,
            search_videos=search_videos,
            video_aspect=video_aspect,
            audio_duration=audio_duration,
            max_clip_duration=max_clip_duration,
            material_directory=material_directory,
        )

    valid_video_items = []
    valid_video_urls = []
    found_duration = 0.0
    for search_term in search_terms:
        video_items = search_videos(
            search_term=search_term,
            minimum_duration=max_clip_duration,
            video_aspect=video_aspect,
        )
        logger.info(f"found {len(video_items)} videos for '{search_term}'")

        for item in video_items:
            if item.url not in valid_video_urls:
                valid_video_items.append(item)
                valid_video_urls.append(item.url)
                found_duration += item.duration

    logger.info(
        f"found total videos: {len(valid_video_items)}, required duration: {audio_duration} seconds, found duration: {found_duration} seconds"
    )
    video_paths = []
    material_sources: list[dict[str, Any]] = []

    concat_mode_value = getattr(video_concat_mode, "value", video_concat_mode)
    if concat_mode_value == VideoConcatMode.random.value:
        random.shuffle(valid_video_items)

    total_duration = 0.0
    for item in valid_video_items:
        try:
            source_info = item.source_info if isinstance(item.source_info, dict) else {}
            logger.info(
                f"downloading {item.provider} video: "
                f"asset_id={source_info.get('asset_id') or 'unknown'}"
            )
            saved_video_path = save_video(
                video_url=item.url, save_dir=material_directory
            )
            if saved_video_path:
                logger.info(f"video saved: {saved_video_path}")
                video_paths.append(saved_video_path)
                try:
                    material_sources.append(
                        _material_source_record(item, saved_video_path)
                    )
                except Exception as source_error:
                    # 来源记录异常不能把已经成功下载的素材视为下载失败，更不能
                    # 阻断视频生成；保留供应商和异常类型用于后续定位。
                    logger.warning(
                        "failed to prepare material source record: "
                        f"provider={item.provider}, "
                        f"error={type(source_error).__name__}, detail={source_error}"
                    )
                seconds = min(max_clip_duration, item.duration)
                total_duration += seconds
                if total_duration > audio_duration:
                    logger.info(
                        f"total duration of downloaded videos: {total_duration} seconds, skip downloading more"
                    )
                    break
        except Exception as e:
            logger.error(
                "failed to download material video: "
                f"provider={item.provider}, error={type(e).__name__}, "
                f"detail={_redact_request_error(e, item.url)}"
            )
    logger.success(f"downloaded {len(video_paths)} videos")
    _persist_material_sources(task_id, material_sources)
    return video_paths


def _download_videos_wavespeed_on_demand(
    *,
    task_id: str,
    search_terms: List[str],
    video_aspect: VideoAspect,
    audio_duration: float,
    max_clip_duration: int,
    material_directory: str,
) -> List[str]:
    """
    按脚本片段顺序逐段生成 WaveSpeed 素材，凑够所需总时长立即停止。

    每个关键词天然对应一个脚本片段，生成即付费：先全量生成再挑选会为
    用不到的片段付费。这里每生成一段就立刻下载并累计有效时长（与库存
    流程一致，按片段时长封顶），累计超过所需配音时长后不再触发新的生成
    请求。单段失败按现有素材源约定跳过并继续下一段。
    """
    video_paths: List[str] = []
    material_sources: list[dict[str, Any]] = []
    total_duration = 0.0
    for search_term in search_terms:
        try:
            video_items = generate_videos_wavespeed(
                search_term=search_term,
                minimum_duration=max_clip_duration,
                video_aspect=video_aspect,
            )
        except WaveSpeedUnconfirmedTaskError as e:
            # 已提交的付费任务状态不明：远端可能仍在运行或已经完成并计费。
            # 继续为后续关键词下单会造成重复生成和重复扣费，因此就地停止，
            # 并把 prediction id 留在日志里供人工在控制台找回产物。
            logger.error(
                "stop submitting new wavespeed tasks, the last submitted task "
                f"is unconfirmed: prediction_id={e.prediction_id or 'unknown'}, "
                f"detail={e}"
            )
            break
        for item in video_items:
            saved_video_path = _save_generated_video_with_retry(
                item.url, material_directory, "wavespeed"
            )
            if not saved_video_path:
                continue
            logger.info(f"video saved: {saved_video_path}")
            video_paths.append(saved_video_path)
            try:
                material_sources.append(_material_source_record(item, saved_video_path))
            except Exception as source_error:
                # 与库存源一致：来源记录异常不能把已经付费生成并成功下载的
                # 素材当作失败，更不能阻断视频生成。
                logger.warning(
                    "failed to prepare material source record: "
                    f"provider={item.provider}, "
                    f"error={type(source_error).__name__}, detail={source_error}"
                )
            total_duration += min(max_clip_duration, item.duration)
            # 用 >= 判断:累计时长恰好等于所需时长时已经够用,再生成会
            # 多付一次费用。内外两处判断必须保持同一语义。
            if total_duration >= audio_duration:
                break
        if total_duration >= audio_duration:
            logger.info(
                "generated materials cover the required duration, stop "
                f"generating more clips: generated={total_duration:.1f}s, "
                f"required={audio_duration:.1f}s"
            )
            break
    logger.success(f"generated and downloaded {len(video_paths)} videos")
    _persist_material_sources(task_id, material_sources)
    return video_paths


def _download_videos_seedance_on_demand(
    *,
    task_id: str,
    search_terms: List[str],
    video_aspect: VideoAspect,
    audio_duration: float,
    max_clip_duration: int,
    material_directory: str,
) -> List[str]:
    """顺序生成方舟 Seedance 素材，覆盖配音时长后立即停止付费下单。"""
    video_paths: List[str] = []
    material_sources: list[dict[str, Any]] = []

    # 付费生成循环必须先验证控制循环次数的两个时长。NaN/Infinity 会让
    # ``total_duration >= audio_duration`` 永远不成立，而非正片段时长会让
    # 累计值无法增长，两者都可能为全部关键词创建无用的付费任务。
    try:
        required_duration = float(audio_duration)
    except (TypeError, ValueError) as exc:
        raise volcengine_seedance.VolcEngineSeedanceError(
            "Seedance audio duration must be a finite number"
        ) from exc
    if not math.isfinite(required_duration):
        raise volcengine_seedance.VolcEngineSeedanceError(
            "Seedance audio duration must be a finite number"
        )
    if required_duration <= 0:
        logger.warning(
            "skip Seedance paid generation because required audio duration is "
            f"not positive: duration={required_duration}"
        )
        _persist_material_sources(task_id, material_sources)
        return video_paths

    try:
        clip_duration = int(max_clip_duration)
    except (TypeError, ValueError, OverflowError) as exc:
        raise volcengine_seedance.VolcEngineSeedanceError(
            "Seedance clip duration must be a positive integer"
        ) from exc
    if clip_duration <= 0:
        raise volcengine_seedance.VolcEngineSeedanceError(
            "Seedance clip duration must be a positive integer"
        )

    total_duration = 0.0
    for search_term in search_terms:
        try:
            video_items = volcengine_seedance.generate_videos(
                search_term=search_term,
                minimum_duration=clip_duration,
                video_aspect=video_aspect,
            )
        except volcengine_seedance.VolcEngineSeedanceUnconfirmedTaskError as exc:
            # 远端付费任务仍可能成功。立即停止继续下单，并保留任务 ID，方便
            # 用户随后在方舟控制台确认或找回结果。
            logger.error(
                "stop submitting new Seedance tasks because the last paid task "
                f"is unconfirmed: task_id={exc.task_id or 'unknown'}, detail={exc}"
            )
            _persist_material_sources(task_id, material_sources)
            raise
        except volcengine_seedance.VolcEngineSeedanceError as exc:
            logger.error(f"Seedance generation failed before completion: {exc}")
            _persist_material_sources(task_id, material_sources)
            raise

        for item in video_items:
            saved_video_path = _save_generated_video_with_retry(
                item.url, material_directory, "volcengine_seedance"
            )
            if not saved_video_path:
                # 远端任务已完成并产生费用，本地下载失败时必须把远端任务 ID
                # 带回任务状态，便于用户去方舟控制台找回结果。这里直接抛出
                # 专用错误，同时阻止后续关键词继续创建新的付费任务。
                source_info = (
                    item.source_info if isinstance(item.source_info, dict) else {}
                )
                remote_task_id = str(source_info.get("asset_id") or "").strip()
                _persist_material_sources(task_id, material_sources)
                raise volcengine_seedance.VolcEngineSeedanceDownloadError(
                    "Seedance generated a paid video but the result could not be "
                    f"downloaded: id={remote_task_id or 'unknown'}",
                    task_id=remote_task_id,
                )
            logger.info(f"video saved: {saved_video_path}")
            video_paths.append(saved_video_path)
            try:
                material_sources.append(_material_source_record(item, saved_video_path))
            except Exception as source_error:
                logger.warning(
                    "failed to prepare generated material source record: "
                    f"provider=volcengine_seedance, "
                    f"error={type(source_error).__name__}, detail={source_error}"
                )
            total_duration += min(clip_duration, item.duration)
            if total_duration >= required_duration:
                break
        if total_duration >= required_duration:
            logger.info(
                "generated Seedance materials cover the required duration; stop "
                f"submitting paid tasks: generated={total_duration:.1f}s, "
                f"required={required_duration:.1f}s"
            )
            break

    logger.success(
        f"generated and downloaded {len(video_paths)} Volcano Engine Seedance videos"
    )
    _persist_material_sources(task_id, material_sources)
    return video_paths


def _download_videos_ofox_on_demand(
    *,
    task_id: str,
    search_terms: List[str],
    video_aspect: VideoAspect,
    audio_duration: float,
    max_clip_duration: int,
    material_directory: str,
) -> List[str]:
    """顺序生成 OFox 素材，覆盖配音时长后立即停止付费下单。"""
    video_paths: List[str] = []
    material_sources: list[dict[str, Any]] = []

    # 付费生成循环必须先验证控制循环次数的两个时长。NaN/Infinity 会让
    # ``total_duration >= audio_duration`` 永远不成立，而非正片段时长会让
    # 累计值无法增长，两者都可能为全部关键词创建无用的付费任务。
    try:
        required_duration = float(audio_duration)
    except (TypeError, ValueError) as exc:
        raise ofox.OFoxError("OFox audio duration must be a finite number") from exc
    if not math.isfinite(required_duration):
        raise ofox.OFoxError("OFox audio duration must be a finite number")
    if required_duration <= 0:
        logger.warning(
            "skip OFox paid generation because required audio duration is "
            f"not positive: duration={required_duration}"
        )
        _persist_material_sources(task_id, material_sources)
        return video_paths

    try:
        clip_duration = int(max_clip_duration)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ofox.OFoxError("OFox clip duration must be a positive integer") from exc
    if clip_duration <= 0:
        raise ofox.OFoxError("OFox clip duration must be a positive integer")

    total_duration = 0.0
    for search_term in search_terms:
        try:
            video_items = ofox.generate_videos(
                search_term=search_term,
                minimum_duration=clip_duration,
                video_aspect=video_aspect,
            )
        except ofox.OFoxUnconfirmedTaskError as exc:
            # 远端付费任务仍可能成功。立即停止继续下单，并保留任务 ID，方便
            # 用户随后在 OFox 控制台确认或找回结果。
            logger.error(
                "stop submitting new OFox tasks because the last paid task "
                f"is unconfirmed: task_id={exc.task_id or 'unknown'}, detail={exc}"
            )
            _persist_material_sources(task_id, material_sources)
            raise
        except ofox.OFoxError as exc:
            logger.error(f"OFox generation failed before completion: {exc}")
            _persist_material_sources(task_id, material_sources)
            raise

        # 单个关键词被远端明确判失败（如触发内容审核）时返回空列表：任务已
        # 结束、无计费悬念，跳过该片段继续生成后续关键词。
        for item in video_items:
            saved_video_path = _save_generated_video_with_retry(
                item.url, material_directory, "ofox"
            )
            if not saved_video_path:
                # 远端任务已完成并产生费用，本地下载失败时必须把远端任务 ID
                # 带回任务状态，便于用户去 OFox 控制台找回结果。这里直接抛出
                # 专用错误，同时阻止后续关键词继续创建新的付费任务。
                source_info = (
                    item.source_info if isinstance(item.source_info, dict) else {}
                )
                remote_task_id = str(source_info.get("asset_id") or "").strip()
                _persist_material_sources(task_id, material_sources)
                raise ofox.OFoxDownloadError(
                    "OFox generated a paid video but the result could not be "
                    f"downloaded: id={remote_task_id or 'unknown'}",
                    task_id=remote_task_id,
                )
            logger.info(f"video saved: {saved_video_path}")
            video_paths.append(saved_video_path)
            try:
                material_sources.append(_material_source_record(item, saved_video_path))
            except Exception as source_error:
                logger.warning(
                    "failed to prepare generated material source record: "
                    f"provider=ofox, "
                    f"error={type(source_error).__name__}, detail={source_error}"
                )
            total_duration += min(clip_duration, item.duration)
            if total_duration >= required_duration:
                break
        if total_duration >= required_duration:
            logger.info(
                "generated OFox materials cover the required duration; stop "
                f"submitting paid tasks: generated={total_duration:.1f}s, "
                f"required={required_duration:.1f}s"
            )
            break

    logger.success(f"generated and downloaded {len(video_paths)} OFox videos")
    _persist_material_sources(task_id, material_sources)
    return video_paths


def _download_videos_metaso_minimax_on_demand(
    *,
    task_id: str,
    search_terms: List[str],
    video_aspect: VideoAspect,
    audio_duration: float,
    max_clip_duration: int,
    material_directory: str,
) -> List[str]:
    """顺序生成秘塔 MiniMax 素材，覆盖配音时长后立即停止付费下单。"""
    video_paths: List[str] = []
    material_sources: list[dict[str, Any]] = []

    # 远端最短生成 4 秒，但本地仍按用户片段时长裁剪和累计。提前验证循环
    # 控制参数，避免 NaN、Infinity 或非正数让停止条件永远无法满足，进而把
    # 所有关键词都提交为付费任务。
    try:
        required_duration = float(audio_duration)
    except (TypeError, ValueError) as exc:
        raise metaso_minimax.MetasoMiniMaxError(
            "Metaso MiniMax audio duration must be a finite number"
        ) from exc
    if not math.isfinite(required_duration):
        raise metaso_minimax.MetasoMiniMaxError(
            "Metaso MiniMax audio duration must be a finite number"
        )
    if required_duration <= 0:
        logger.warning(
            "skip Metaso MiniMax paid generation because required audio duration "
            f"is not positive: duration={required_duration}"
        )
        _persist_material_sources(task_id, material_sources)
        return video_paths

    try:
        clip_duration = int(max_clip_duration)
    except (TypeError, ValueError, OverflowError) as exc:
        raise metaso_minimax.MetasoMiniMaxError(
            "Metaso MiniMax clip duration must be a positive integer"
        ) from exc
    if clip_duration <= 0:
        raise metaso_minimax.MetasoMiniMaxError(
            "Metaso MiniMax clip duration must be a positive integer"
        )

    total_duration = 0.0
    for search_term in search_terms:
        try:
            video_items = metaso_minimax.generate_videos(
                search_term=search_term,
                minimum_duration=clip_duration,
                video_aspect=video_aspect,
            )
        except metaso_minimax.MetasoMiniMaxUnconfirmedTaskError as exc:
            # 请求或轮询状态不明时，远端任务仍可能成功并计费。立即停止整个
            # 生成循环，防止后续关键词继续下单，并把任务 ID 交给任务服务保存。
            logger.error(
                "stop submitting new Metaso MiniMax tasks because the last paid "
                f"task is unconfirmed: task_id={exc.task_id or 'unknown'}, "
                f"detail={exc}"
            )
            _persist_material_sources(task_id, material_sources)
            raise
        except metaso_minimax.MetasoMiniMaxError as exc:
            logger.error(f"Metaso MiniMax generation failed before completion: {exc}")
            _persist_material_sources(task_id, material_sources)
            raise

        for item in video_items:
            saved_video_path = _save_generated_video_with_retry(
                item.url, material_directory, "metaso_minimax"
            )
            if not saved_video_path:
                # 生成成功已产生费用，下载失败时不能继续创建新任务来替代。
                # 抛出携带远端 ID 的专用错误，供任务状态和人工恢复使用。
                source_info = (
                    item.source_info if isinstance(item.source_info, dict) else {}
                )
                remote_task_id = str(source_info.get("asset_id") or "").strip()
                _persist_material_sources(task_id, material_sources)
                raise metaso_minimax.MetasoMiniMaxDownloadError(
                    "Metaso MiniMax generated a paid video but the result could "
                    f"not be downloaded: id={remote_task_id or 'unknown'}",
                    task_id=remote_task_id,
                )
            logger.info(f"video saved: {saved_video_path}")
            video_paths.append(saved_video_path)
            try:
                material_sources.append(_material_source_record(item, saved_video_path))
            except Exception as source_error:
                logger.warning(
                    "failed to prepare generated material source record: "
                    f"provider=metaso_minimax, error={type(source_error).__name__}, "
                    f"detail={source_error}"
                )

            # 本地成片只使用用户选择的片段长度；即使 H3 因最短时长约束生成
            # 了更长素材，也不能把未使用部分计入覆盖时长并少生成必要画面。
            total_duration += min(clip_duration, item.duration)
            if total_duration >= required_duration:
                break
        if total_duration >= required_duration:
            logger.info(
                "generated Metaso MiniMax materials cover the required duration; "
                f"stop submitting paid tasks: generated={total_duration:.1f}s, "
                f"required={required_duration:.1f}s"
            )
            break

    logger.success(f"generated and downloaded {len(video_paths)} Metaso MiniMax videos")
    _persist_material_sources(task_id, material_sources)
    return video_paths


def _download_videos_by_script_order(
    task_id: str,
    search_terms: List[str],
    search_videos,
    video_aspect: VideoAspect,
    audio_duration: float,
    max_clip_duration: int,
    material_directory: str,
) -> List[str]:
    """
    按脚本文案顺序下载素材。

    默认下载逻辑会把所有关键词的候选素材合并成一个大列表；如果第一个
    关键词返回很多结果，最终下载时可能一直消耗这个关键词的素材，后续
    脚本主题就排不上时间线。这里按关键词分组后轮询下载：
    第 1 轮取每个关键词的第 1 个候选，第 2 轮取每个关键词的第 2 个候选。
    这样在不重写视频合成引擎的前提下，尽量保证素材顺序贴近文案顺序。
    """
    logger.info("downloading videos with script-order material matching")
    candidate_groups = []
    valid_video_urls = set()
    found_duration = 0.0

    for search_term in search_terms:
        video_items = search_videos(
            search_term=search_term,
            minimum_duration=max_clip_duration,
            video_aspect=video_aspect,
        )
        logger.info(f"found {len(video_items)} videos for '{search_term}'")

        term_items = []
        for item in video_items:
            if item.url in valid_video_urls:
                continue
            term_items.append(item)
            valid_video_urls.add(item.url)
            found_duration += item.duration

        if term_items:
            candidate_groups.append((search_term, term_items))

    logger.info(
        f"found total ordered video candidates: {sum(len(items) for _, items in candidate_groups)}, "
        f"required duration: {audio_duration} seconds, found duration: {found_duration} seconds"
    )

    video_paths = []
    material_sources: list[dict[str, Any]] = []
    total_duration = 0.0
    candidate_index = 0
    while candidate_groups and total_duration <= audio_duration:
        has_candidate = False
        for search_term, term_items in candidate_groups:
            if candidate_index >= len(term_items):
                continue

            has_candidate = True
            item = term_items[candidate_index]
            try:
                source_info = (
                    item.source_info if isinstance(item.source_info, dict) else {}
                )
                logger.info(
                    f"downloading ordered {item.provider} video for {search_term!r}: "
                    f"asset_id={source_info.get('asset_id') or 'unknown'}"
                )
                saved_video_path = save_video(
                    video_url=item.url, save_dir=material_directory
                )
                if saved_video_path:
                    logger.info(f"video saved: {saved_video_path}")
                    video_paths.append(saved_video_path)
                    try:
                        material_sources.append(
                            _material_source_record(item, saved_video_path)
                        )
                    except Exception as source_error:
                        logger.warning(
                            "failed to prepare ordered material source record: "
                            f"provider={item.provider}, "
                            f"error={type(source_error).__name__}, "
                            f"detail={source_error}"
                        )
                    total_duration += min(max_clip_duration, item.duration)
                    if total_duration > audio_duration:
                        logger.info(
                            f"total duration of downloaded videos: {total_duration} seconds, skip downloading more"
                        )
                        break
            except Exception as e:
                logger.error(
                    "failed to download ordered material video: "
                    f"provider={item.provider}, error={type(e).__name__}, "
                    f"detail={_redact_request_error(e, item.url)}"
                )

        if not has_candidate:
            break
        candidate_index += 1

    logger.success(f"downloaded {len(video_paths)} ordered videos")
    _persist_material_sources(task_id, material_sources)
    return video_paths


if __name__ == "__main__":
    download_videos(
        "test123", ["Money Exchange Medium"], audio_duration=100, source="pixabay"
    )
