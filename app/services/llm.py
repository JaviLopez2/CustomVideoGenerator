import json
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
from time import perf_counter
from typing import List

from loguru import logger
from openai import AzureOpenAI, OpenAI
from openai.types.chat import ChatCompletion

from app.config import config
from app.models.llm_provider import DEFAULT_LLM_PROVIDER_ID, get_llm_provider

_max_retries = 5
MIN_SCRIPT_PARAGRAPH_NUMBER = 1
MAX_SCRIPT_PARAGRAPH_NUMBER = 10
MAX_SCRIPT_PROMPT_LENGTH = 2000
MAX_SCRIPT_SYSTEM_PROMPT_LENGTH = 8000
_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>", re.IGNORECASE | re.DOTALL)
_UNCLOSED_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*$", re.IGNORECASE | re.DOTALL)
_URL_USERINFO_RE = re.compile(
    r"((?:https?|wss?)://)([^/\s?#@]*:[^/\s?#@]*@)", re.IGNORECASE
)
_SENSITIVE_QUERY_RE = re.compile(
    r"([?&](?:api[_-]?key|access[_-]?token|token|key|secret|password)=)([^&#\s]+)",
    re.IGNORECASE,
)

DEFAULT_SCRIPT_SYSTEM_PROMPT = """
# Role: Video Script Generator

## Goals:
Generate a script for a video, depending on the subject of the video.

## Constrains:
1. the script is to be returned as a string with the specified number of paragraphs.
2. do not under any circumstance reference this prompt in your response.
3. get straight to the point, don't start with unnecessary things like, "welcome to this video".
4. you must not include any type of markdown or formatting in the script, never use a title.
5. only return the raw content of the script.
6. do not include "voiceover", "narrator" or similar indicators of what should be spoken at the beginning of each paragraph or line.
7. you must not mention the prompt, or anything about the script itself. also, never talk about the amount of paragraphs or lines. just write the script.
8. respond in the same language as the video subject.
9. for factual or explanatory topics, never invent exact mechanisms, hidden geometry, component counts, chemical names,
   material names, timings, causal steps or branded technical details merely because they sound plausible.
10. when a highly specific technical claim is uncertain, prefer a broader accurate description over a confident
    unsupported detail. Do not fill knowledge gaps with plausible-sounding specificity.
11. keep setup, exposure/action, output and later transformation steps in physically coherent chronological order.
12. distinguish what is directly observable from what happens inside an opaque object, between hidden layers or inside
    a closed system; do not narrate an inferred hidden process as if it were visibly observed.
""".strip()

# Claude Code CLI 默认使用编码 agent 的系统提示词，其中大量约束与文案写作
# 无关，会让脚本和关键词生成偏离要求，因此调用时整体替换掉。
CLAUDE_CODE_SYSTEM_PROMPT = (
    "You are a concise copywriter. Follow the user's instructions and output "
    "format exactly, and output nothing else."
)
CLAUDE_CODE_DEFAULT_TIMEOUT = 300.0
# `--tools ""` 关闭全部内置工具，`--safe-mode` 关闭 CLAUDE.md、skills、hooks、
# plugins、MCP 等所有用户级定制，同时保持鉴权、模型选择和权限正常工作。
# 二者需要较新的 CLI；低版本会以 "unknown option" 退出，由调用处转成明确提示。
CLAUDE_CODE_MIN_CLI_VERSION = "2.1.260"
# 这些环境变量会让 CLI 改用 API Key 或第三方供应商（Bedrock、Vertex、Foundry、
# Mantle、Gateway 等），从而绕过订阅登录并产生额外计费。逐个列举容易漏项，
# 而且 CLI 后续还会新增供应商，因此按前缀整类剔除：
#   ANTHROPIC_*           API Key、Auth Token、Base URL、各家供应商端点和 Profile
#   CLAUDE_CODE_USE_*     供应商开关
#   CLAUDE_CODE_SKIP_*_AUTH  跳过供应商鉴权的开关
CLAUDE_CODE_CONFLICTING_ENV_PREFIXES = ("ANTHROPIC_", "CLAUDE_CODE_USE_")
CLAUDE_CODE_CONFLICTING_ENV_VARS = (
    "AWS_BEARER_TOKEN_BEDROCK",
    "CLAUDE_CODE_GATEWAY_TOKEN_FILE_DESCRIPTOR",
)
# 这两类变量不能剔除：
#   CLAUDE_CODE_OAUTH_TOKEN 是容器内唯一的订阅鉴权方式（不匹配上面的前缀）；
#   *_CONFIG_DIR 只是指出凭证存放位置，剔除后反而会让已登录的订阅失效。
CLAUDE_CODE_PRESERVED_ENV_VARS = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_CONFIG_DIR",
    "CLAUDE_CONFIG_DIR",
)


def _is_conflicting_claude_code_env(name: str) -> bool:
    """判断某个环境变量是否会把 CLI 从订阅登录切换到别的鉴权方式。"""
    if name in CLAUDE_CODE_PRESERVED_ENV_VARS:
        return False
    if name in CLAUDE_CODE_CONFLICTING_ENV_VARS:
        return True
    if name.startswith(CLAUDE_CODE_CONFLICTING_ENV_PREFIXES):
        return True
    return name.startswith("CLAUDE_CODE_SKIP_") and name.endswith("_AUTH")


def coerce_claude_code_timeout(value, config_key: str = "claude_code_timeout"):
    """
    把配置里的超时值解析成正的有限秒数。

    TOML 既可能写成 `claude_code_timeout = 300`（int/float），也可能写成
    `"300"`（字符串），因此不能直接调用 `strip()`。nan / inf 会让
    `subprocess.run(timeout=...)` 永久阻塞，这里一并拒绝。
    """
    if value is None:
        return CLAUDE_CODE_DEFAULT_TIMEOUT

    if isinstance(value, bool):
        # bool 是 int 的子类，但 True 秒显然不是用户想要的超时配置。
        raise ValueError(f"{config_key} must be a number of seconds, got {value!r}")

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return CLAUDE_CODE_DEFAULT_TIMEOUT
        try:
            seconds = float(text)
        except ValueError:
            raise ValueError(
                f"{config_key} must be a number of seconds, got {value!r}"
            ) from None
    elif isinstance(value, (int, float)):
        seconds = float(value)
    else:
        raise ValueError(f"{config_key} must be a number of seconds, got {value!r}")

    if not math.isfinite(seconds):
        raise ValueError(f"{config_key} must be a finite number, got {value!r}")
    if seconds <= 0:
        raise ValueError(f"{config_key} must be greater than 0, got {value!r}")
    return seconds


def _resolve_provider_field_value(raw_value, default_value):
    """
    只有「未配置」时才回退到 Registry 默认值。

    之前用 `raw or default_value`，会把 0 和 false 这类合法取值也当成未配置
    替换掉：`claude_code_timeout = 0` 被静默改成 300，而 `"0"` 却报错。默认值
    只在 None 或空白字符串时生效，配置校验才能对所有写法保持一致。
    """
    if raw_value is None:
        return default_value
    if isinstance(raw_value, str) and not raw_value.strip():
        return default_value
    return raw_value


def build_claude_code_env(base_env=None):
    """
    构造只依赖订阅登录的子进程环境。

    返回 (环境变量字典, 被剔除的变量名列表)。剔除的是会切换鉴权方式或供应商
    的变量，`CLAUDE_CODE_OAUTH_TOKEN` 必须保留：容器内没有 keychain，CLI 只能
    靠它完成订阅鉴权。
    """
    env = dict(os.environ if base_env is None else base_env)
    removed = sorted(name for name in env if _is_conflicting_claude_code_env(name))
    for name in removed:
        env.pop(name, None)
    return env, removed


def _normalize_text_response(content, llm_provider: str) -> str:
    # 不同 LLM SDK 在异常或被拦截场景下，可能返回 None、空字符串，
    # 甚至返回非字符串对象。这里统一做兜底校验，避免后续直接调用
    # `.replace()` 时抛出 `NoneType` 之类的属性错误。
    if content is None:
        raise ValueError(f"[{llm_provider}] returned empty text content")

    if not isinstance(content, str):
        raise TypeError(
            f"[{llm_provider}] returned non-text content: {type(content).__name__}"
        )

    # MiniMax M3、DeepSeek R1 这类 reasoning 模型可能会把内部推理包在
    # `<think>...</think>` 中返回。视频脚本和关键词只需要最终可朗读文本，
    # 如果不在服务层统一清理，WebUI、字幕和配音都会把思考过程当正文处理。
    content = _THINK_BLOCK_RE.sub("", content)
    content = _UNCLOSED_THINK_BLOCK_RE.sub("", content).strip()
    if not content:
        raise ValueError(f"[{llm_provider}] returned empty text content")

    # 前面的 ``strip()`` 已经清理首尾空白。这里必须保留正文中的单换行和
    # 双换行：脚本生成依赖双换行区分段落，字幕处理也会按行读取用户文案。
    return content


def _sanitize_error_message(error: object) -> str:
    """
    清理返回给 WebUI/API 的错误信息，避免自定义 base_url 中的凭据泄露。

    一些 OpenAI-compatible SDK 会把请求 URL 原样拼进异常信息。如果用户为了
    代理网关配置了 `https://user:pass@example.com/v1`，直接返回 `str(e)`
    就会把密码暴露给页面、API 调用方或后续日志。这里仅处理错误文案，不改变
    实际请求地址，避免影响正常调用链路。
    """
    message = str(error)
    message = _URL_USERINFO_RE.sub(r"\1***:***@", message)
    message = _SENSITIVE_QUERY_RE.sub(r"\1***", message)
    return message


def _extract_chat_completion_text(response, llm_provider: str) -> str:
    # OpenAI 兼容接口在异常场景下，可能返回没有 choices、
    # 或者 choices/message/content 为空的响应对象。
    # 这里统一做结构校验，避免出现 `NoneType is not subscriptable`
    # 这类底层属性访问错误。
    choices = getattr(response, "choices", None)
    if not choices:
        raise ValueError(f"[{llm_provider}] returned empty choices")

    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    if message is None:
        raise ValueError(f"[{llm_provider}] returned empty message")

    content = getattr(message, "content", None)
    return _normalize_text_response(content, llm_provider)


def _get_response_field(value, key: str):
    """兼容 dict 和 SDK 响应对象的字段读取。"""
    if isinstance(value, dict):
        return value.get(key)

    try:
        return value[key]
    except (KeyError, TypeError, AttributeError):
        return getattr(value, key, None)


def _extract_qwen_generation_text(response) -> str:
    """
    从 DashScope Generation 响应中提取文本。

    Qwen 使用 `messages` 调用时返回的是 chat 结构：
    `output.choices[0].message.content`；旧 completion 形态才会返回
    `output.text`。这里两个路径都兼容，避免 `output.text` 为 None 时
    继续 `.replace()` 触发不可诊断的 AttributeError。
    """
    output = _get_response_field(response, "output")
    choices = _get_response_field(output, "choices") if output else None
    if choices is not None:
        if not choices:
            logger.warning("Qwen returned an empty choices list")
            raise ValueError("[qwen] returned empty choices")

        first_choice = choices[0]
        message = _get_response_field(first_choice, "message")
        content = _get_response_field(message, "content") if message else None
        if content is not None:
            return _normalize_text_response(content, "qwen")

    text = _get_response_field(output, "text") if output else None
    return _normalize_text_response(text, "qwen")


def _generate_response(prompt: str, app_config=None) -> str:
    try:
        # WebUI 在视频生成期间允许用户准备下一条文案。调用方可以传入提交瞬间
        # 的配置快照，确保模型请求重试期间不会因为后台任务结束并应用新配置，
        # 而切换到另一个 Provider、Base URL 或模型。
        runtime_app_config = app_config if app_config is not None else config.app
        llm_provider = str(
            runtime_app_config.get("llm_provider", DEFAULT_LLM_PROVIDER_ID)
        ).lower()
        provider = get_llm_provider(llm_provider)
        if provider is None:
            raise ValueError(f"{llm_provider}: unsupported llm provider")

        logger.info(f"llm provider: {llm_provider}")
        api_key = runtime_app_config.get(provider.config_key("api_key"), "")
        configured_model = runtime_app_config.get(provider.config_key("model_name"), "")
        model_name = provider.resolve_model_name(configured_model)
        if configured_model and model_name != configured_model:
            logger.warning(
                f"{llm_provider} model '{configured_model}' is deprecated, "
                f"fallback to '{model_name}'"
            )
        configured_base_url = runtime_app_config.get(
            provider.config_key("base_url"), ""
        )
        base_url = provider.resolve_base_url(configured_base_url)
        if configured_base_url and configured_base_url.strip().rstrip("/") in {
            url.rstrip("/") for url in provider.deprecated_base_urls
        }:
            logger.warning(
                f"{llm_provider} base URL '{configured_base_url}' is deprecated, "
                f"fallback to '{base_url}'"
            )
        adapter = provider.adapter
        api_version = ""

        # Ollama 的默认地址依赖当前是否运行在容器中，无法作为静态 Registry
        # 值保存；Registry 仍负责模型和必填规则，运行环境差异在这里解析。
        if llm_provider == "ollama":
            api_key = "ollama"
            if not base_url:
                base_url = config.get_default_ollama_base_url()

        if adapter == "azure":
            api_version = runtime_app_config.get(
                provider.config_key("api_version"), "2024-02-15-preview"
            )

        extra_values = {
            field.config_suffix: _resolve_provider_field_value(
                runtime_app_config.get(provider.config_key(field.config_suffix)),
                field.default_value,
            )
            for field in provider.extra_fields
        }

        if provider.requires_api_key and not api_key:
            raise ValueError(
                f"{llm_provider}: api_key is not set, please set it in the config.toml file."
            )
        if provider.requires_model_name and not model_name:
            raise ValueError(
                f"{llm_provider}: model_name is not set, please set it in the config.toml file."
            )
        if provider.requires_base_url and not base_url:
            raise ValueError(
                f"{llm_provider}: base_url is not set, please set it in the config.toml file."
            )

        for field in provider.extra_fields:
            if field.required and not extra_values[field.config_suffix]:
                raise ValueError(
                    f"{llm_provider}: {field.config_suffix} is not set, "
                    "please set it in the config.toml file."
                )

        if adapter == "qwen":
            import dashscope
            from dashscope.api_entities.dashscope_response import GenerationResponse

            dashscope.api_key = api_key
            response = dashscope.Generation.call(
                model=model_name, messages=[{"role": "user", "content": prompt}]
            )
            if response:
                if isinstance(response, GenerationResponse):
                    status_code = response.status_code
                    if status_code != 200:
                        raise Exception(
                            f'[{llm_provider}] returned an error response: "{response}"'
                        )

                    return _extract_qwen_generation_text(response)
                else:
                    raise Exception(
                        f'[{llm_provider}] returned an invalid response: "{response}"'
                    )
            else:
                raise Exception(f"[{llm_provider}] returned an empty response")

        if adapter == "gemini":
            from google import genai
            from google.genai import types

            http_options = types.HttpOptions(base_url=base_url) if base_url else None
            generation_config = types.GenerateContentConfig(
                temperature=0.5,
                top_p=1,
                top_k=1,
                max_output_tokens=2048,
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT",
                        threshold="BLOCK_ONLY_HIGH",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH",
                        threshold="BLOCK_ONLY_HIGH",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="BLOCK_ONLY_HIGH",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="BLOCK_ONLY_HIGH",
                    ),
                ],
            )

            try:
                # 新版 google-genai 通过统一 Client 暴露模型服务。上下文管理器
                # 会在请求结束后关闭底层 HTTP 连接，避免频繁生成时积累连接资源。
                with genai.Client(
                    api_key=api_key,
                    http_options=http_options,
                ) as client:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=generation_config,
                    )
                generated_text = response.text
            except (AttributeError, IndexError, ValueError) as e:
                logger.warning(f"gemini returned invalid response content: {str(e)}")
                raise ValueError(f"[{llm_provider}] returned invalid response content")

            return _normalize_text_response(generated_text, llm_provider)

        if adapter == "cloudflare_ai_gateway":
            account_id = extra_values["account_id"]
            gateway_id = extra_values["gateway_id"]
            # Cloudflare 当前推荐的 AI Gateway REST API 兼容 OpenAI SDK。
            # Account ID 用于构造统一端点，Gateway ID 通过请求头选择；这里
            # 不再调用 Workers AI 的 /ai/run/{model} 专用接口。
            client = OpenAI(
                api_key=api_key,
                base_url=(
                    f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"
                ),
                default_headers={"cf-aig-gateway-id": gateway_id},
            )
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            return _extract_chat_completion_text(response, llm_provider)

        if adapter == "litellm":
            import litellm

            if not model_name:
                raise ValueError(
                    f"{llm_provider}: model_name is not set, please set it in the config.toml file."
                )

            response = litellm.completion(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                drop_params=True,
            )

            if not response:
                raise ValueError(f"[{llm_provider}] returned empty response")
            if not getattr(response, "choices", None):
                raise ValueError(f"[{llm_provider}] returned empty response")

            return _extract_chat_completion_text(response, llm_provider)

        if adapter == "azure":
            # Azure OpenAI SDK 使用 `azure_endpoint` 和 `api_version` 生成专用请求地址，
            # 不能继续复用下面普通 OpenAI-compatible 的 `base_url` 初始化逻辑。
            # 这里在 Azure 分支内完成请求并立即返回，避免客户端被后续 fallback
            # 覆盖，导致用户配置的 Azure 凭证通过校验但实际请求没有被使用。
            logger.info(f"requesting azure chat completion, model: {model_name}")
            client = AzureOpenAI(
                api_key=api_key,
                api_version=api_version,
                azure_endpoint=base_url,
            )
            response = client.chat.completions.create(
                model=model_name, messages=[{"role": "user", "content": prompt}]
            )
            if response:
                if isinstance(response, ChatCompletion):
                    return _extract_chat_completion_text(response, llm_provider)
                else:
                    raise Exception(
                        f'[{llm_provider}] returned an invalid response: "{response}", please check your network '
                        f"connection and try again."
                    )
            else:
                raise Exception(
                    f"[{llm_provider}] returned an empty response, please check your network connection and try again."
                )

        if adapter == "claude_code":
            # Claude 订阅（Pro / Max / Team）不签发 API Key，其凭证只能由
            # Claude Code 官方客户端自己使用。这里不直接请求 Anthropic API，
            # 而是以 headless 模式调用本机已登录的 claude CLI（`claude -p`），
            # 由 CLI 完成鉴权，脚本生成只消费它返回的文本。
            configured_cli = (extra_values.get("cli_path") or "").strip() or "claude"
            cli_path = shutil.which(configured_cli)
            if not cli_path and os.path.isfile(configured_cli):
                cli_path = configured_cli
            if not cli_path:
                raise ValueError(
                    f"{llm_provider}: claude CLI not found ('{configured_cli}'), "
                    f"install it in the runtime or set "
                    f"{provider.config_key('cli_path')} in the config.toml file."
                )

            try:
                timeout_seconds = coerce_claude_code_timeout(
                    extra_values.get("timeout"), provider.config_key("timeout")
                )
            except ValueError as timeout_error:
                raise ValueError(f"{llm_provider}: {timeout_error}") from None

            command = [
                cli_path,
                "-p",
                prompt,
                "--output-format",
                "json",
                "--system-prompt",
                CLAUDE_CODE_SYSTEM_PROMPT,
                # 关闭全部内置工具，保证只做文本生成。
                "--tools",
                "",
                # 关闭 CLAUDE.md、skills、hooks、plugins、MCP 等用户级定制；
                # 鉴权与模型选择不受影响（不能用 --bare，它会禁用 OAuth）。
                "--safe-mode",
            ]
            # 模型名留空时沿用 CLI 自己的默认模型，避免这里硬编码的模型 ID
            # 随订阅可用模型变化而失效。
            if model_name:
                command += ["--model", model_name]

            cli_env, removed_env = build_claude_code_env()
            if removed_env:
                # 只记录变量名，不记录取值，避免把密钥写进日志。
                logger.warning(
                    f"{llm_provider}: ignoring conflicting environment variables "
                    f"so the subscription login is used: {', '.join(removed_env)}"
                )

            logger.info(f"invoking claude cli, model: {model_name or 'cli default'}")
            # CLI 会读取工作目录下的 CLAUDE.md 和项目设置，这些内容会污染
            # 文案结果，因此固定在一个临时空目录中执行。
            with tempfile.TemporaryDirectory() as work_dir:
                try:
                    completed = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=timeout_seconds,
                        cwd=work_dir,
                        env=cli_env,
                    )
                except subprocess.TimeoutExpired:
                    raise Exception(
                        f"[{llm_provider}] claude cli timed out after "
                        f"{timeout_seconds:.0f}s"
                    )

            # 未登录、用量耗尽这类失败同样会返回 JSON（`is_error` 为真，
            # `result` 是可读原因），只是退出码非 0。因此先解析 stdout，
            # 只有在拿不到 JSON 时才回退到退出码和 stderr。
            stdout = (completed.stdout or "").strip()
            try:
                payload = json.loads(stdout) if stdout else None
            except json.JSONDecodeError:
                payload = None

            if payload is None:
                detail = (completed.stderr or stdout or "").strip()
                if "unknown option" in detail.lower():
                    raise Exception(
                        f"[{llm_provider}] the installed claude CLI does not support "
                        f"the required isolation flags; upgrade to "
                        f"{CLAUDE_CODE_MIN_CLI_VERSION} or newer: {detail[:300]}"
                    )
                if completed.returncode != 0:
                    raise Exception(
                        f"[{llm_provider}] claude cli exited with code "
                        f"{completed.returncode}: {detail[:500]}"
                    )
                raise Exception(
                    f'[{llm_provider}] returned an invalid response: "{detail[:500]}"'
                )

            if payload.get("is_error") or completed.returncode != 0:
                reason = str(payload.get("result") or "").strip() or (
                    f"claude cli exited with code {completed.returncode}"
                )
                # 容器里无法执行交互式 /login，这里直接给出可用的鉴权方式。
                if "login" in reason.lower():
                    reason += (
                        " (run `claude setup-token` on the host and pass the token "
                        "to the container as CLAUDE_CODE_OAUTH_TOKEN)"
                    )
                raise Exception(
                    f'[{llm_provider}] returned an error response: "{reason[:500]}"'
                )

            return _normalize_text_response(payload.get("result"), llm_provider)

        if adapter == "modelscope":
            content = ""
            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
            )
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                extra_body={"enable_thinking": False},
                stream=True,
            )
            if response:
                for chunk in response:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        content += delta.content

                if not content.strip():
                    raise ValueError("Empty content in stream response")

                return _normalize_text_response(content, llm_provider)
            else:
                raise Exception(f"[{llm_provider}] returned an empty response")

        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

        response = client.chat.completions.create(
            model=model_name, messages=[{"role": "user", "content": prompt}]
        )
        if response:
            if isinstance(response, ChatCompletion):
                return _extract_chat_completion_text(response, llm_provider)
            else:
                raise Exception(
                    f'[{llm_provider}] returned an invalid response: "{response}", please check your network '
                    f"connection and try again."
                )
        else:
            raise Exception(
                f"[{llm_provider}] returned an empty response, please check your network connection and try again."
            )

    except Exception as e:
        return f"Error: {_sanitize_error_message(e)}"


def test_connection() -> tuple[bool, str, float]:
    """
    使用当前 Provider 配置发起一次最小请求，验证实际生成链路是否可用。

    连接测试直接复用 `_generate_response()`，因此会覆盖 API Key、Base URL、
    模型名称和 Provider 专用字段，但不会进入脚本生成的重试逻辑，也不会发送
    用户的视频主题或文案。返回值依次为成功状态、错误信息和请求耗时。
    """
    started_at = perf_counter()
    response = _generate_response(prompt="Reply with exactly: OK")
    elapsed = perf_counter() - started_at

    if not response:
        error_message = "LLM returned an empty response"
        logger.warning(f"llm connection test failed: {error_message}")
        return False, error_message, elapsed

    if response.startswith("Error:"):
        error_message = response.removeprefix("Error:").strip()
        logger.warning(f"llm connection test failed: {error_message}")
        return False, error_message, elapsed

    logger.info(f"llm connection test succeeded, elapsed: {elapsed:.2f}s")
    return True, "", elapsed


def _limit_script_text(text: str | None, max_length: int, field_name: str) -> str:
    value = (text or "").strip()
    if len(value) <= max_length:
        return value

    # API 层已经用 Pydantic 做长度校验；这里继续兜底，是为了保护
    # WebUI 或内部服务直接调用 generate_script 时不会把超长提示词发送给模型，
    # 避免 token 成本异常和请求失败。
    logger.warning(
        f"{field_name} is too long and will be truncated to {max_length} characters."
    )
    return value[:max_length]


def _normalize_script_paragraph_number(paragraph_number: int | None) -> int:
    try:
        value = int(paragraph_number or MIN_SCRIPT_PARAGRAPH_NUMBER)
    except (TypeError, ValueError):
        value = MIN_SCRIPT_PARAGRAPH_NUMBER

    if value < MIN_SCRIPT_PARAGRAPH_NUMBER or value > MAX_SCRIPT_PARAGRAPH_NUMBER:
        # WebUI 和 API 都会限制范围；这里兜底处理内部调用，避免异常参数直接扩大
        # LLM 生成成本或生成空结果。
        logger.warning(
            f"script paragraph_number is out of range and will be clamped: {value}"
        )
        return max(MIN_SCRIPT_PARAGRAPH_NUMBER, min(value, MAX_SCRIPT_PARAGRAPH_NUMBER))

    return value


def build_script_prompt(
    video_subject: str,
    language: str = "",
    paragraph_number: int = 1,
    video_script_prompt: str = "",
    custom_system_prompt: str = "",
) -> str:
    paragraph_number = _normalize_script_paragraph_number(paragraph_number)
    video_script_prompt = _limit_script_text(
        video_script_prompt, MAX_SCRIPT_PROMPT_LENGTH, "video_script_prompt"
    )
    custom_system_prompt = _limit_script_text(
        custom_system_prompt, MAX_SCRIPT_SYSTEM_PROMPT_LENGTH, "custom_system_prompt"
    )

    # 将“脚本生成规则”和“运行时上下文”分开拼接。这样高级用户即使覆盖默认
    # system prompt，也不会漏掉视频主题、语言、段落数这些每次生成都必须带上的参数。
    prompt = custom_system_prompt or DEFAULT_SCRIPT_SYSTEM_PROMPT
    prompt += f"""

# Initialization:
- video subject: {video_subject}
- number of paragraphs: {paragraph_number}
""".rstrip()
    if language:
        prompt += f"\n- language: {language}"
    if video_script_prompt:
        prompt += f"""

# Additional User Requirements:
{video_script_prompt}
""".rstrip()

    return prompt


def generate_script(
    video_subject: str,
    language: str = "",
    paragraph_number: int = 1,
    video_script_prompt: str = "",
    custom_system_prompt: str = "",
    app_config=None,
) -> str:
    paragraph_number = _normalize_script_paragraph_number(paragraph_number)
    video_script_prompt = _limit_script_text(
        video_script_prompt, MAX_SCRIPT_PROMPT_LENGTH, "video_script_prompt"
    )
    custom_system_prompt = _limit_script_text(
        custom_system_prompt, MAX_SCRIPT_SYSTEM_PROMPT_LENGTH, "custom_system_prompt"
    )
    prompt = build_script_prompt(
        video_subject=video_subject,
        language=language,
        paragraph_number=paragraph_number,
        video_script_prompt=video_script_prompt,
        custom_system_prompt=custom_system_prompt,
    )
    final_script = ""
    logger.info(
        "generating video script: "
        f"subject={video_subject}, paragraph_number={paragraph_number}, "
        f"has_custom_prompt={bool(video_script_prompt.strip())}, "
        f"has_custom_system_prompt={bool(custom_system_prompt.strip())}"
    )

    def format_response(response):
        # Clean the script
        # Remove asterisks, hashes
        response = response.replace("*", "")
        response = response.replace("#", "")

        # Remove markdown syntax.  Use non-greedy .*? so each bracket/paren
        # group is removed independently; the greedy form would eat all text
        # between the first opener and the last closer on the same line.
        response = re.sub(r"\[.*?\]", "", response)
        response = re.sub(r"\(.*?\)", "", response)

        # Split the script into paragraphs
        paragraphs = response.split("\n\n")

        # Select the specified number of paragraphs
        # selected_paragraphs = paragraphs[:paragraph_number]

        # Join the selected paragraphs into a single string
        return "\n\n".join(paragraphs)

    for i in range(_max_retries):
        try:
            if app_config is None:
                response = _generate_response(prompt=prompt)
            else:
                response = _generate_response(prompt=prompt, app_config=app_config)
            if response:
                final_script = format_response(response)
            else:
                logging.error("gpt returned an empty response")

            # Some upstream providers may return quota errors as plain text.
            if final_script and "当日额度已消耗完" in final_script:
                raise ValueError(final_script)

            if final_script:
                break
        except Exception as e:
            logger.error(f"failed to generate script: {e}")

        if i < _max_retries - 1:
            logger.warning(f"failed to generate video script, trying again... {i + 1}")
    if "Error: " in final_script:
        logger.error(f"failed to generate video script: {final_script}")
    else:
        logger.success(f"completed: \n{final_script}")
    return final_script.strip()


def _strip_code_fence(text: str) -> str:
    """Strip a surrounding markdown code fence from an LLM response.

    Non-OpenAI providers (Claude, Gemini, …) frequently wrap JSON output in a
    ```json … ``` fence even when asked to return raw JSON. Removing it lets the
    first json.loads() succeed instead of falling through to the regex recovery
    path (and spuriously logging a warning). Mirrors the DOTALL handling already
    used in _parse_social_metadata().
    """
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def generate_terms(
    video_subject: str,
    video_script: str,
    amount: int = 5,
    match_script_order: bool = False,
    app_config=None,
) -> List[str]:
    if match_script_order:
        goal = (
            f"Generate {amount} chronological stock-video search terms that follow "
            "the order of topics in the video script."
        )
        ordering_rule = (
            "6. keep the terms in the same order as the script narration; "
            "earlier terms must describe earlier visual moments."
        )
        # 有序关键词模式下，示例数量要和 amount 保持一致，避免模型被固定
        # 的 4 个示例误导，导致长文案只返回少量关键词，影响素材覆盖度。
        example_terms = [
            "opening visual topic",
            *[f"script visual topic {index}" for index in range(2, max(amount, 1))],
            "final visual topic",
        ]
        output_example = json.dumps(example_terms[:amount], ensure_ascii=False)
    else:
        goal = (
            f"Generate {amount} search terms for stock videos, depending on the "
            "subject of a video."
        )
        ordering_rule = ""
        output_example = (
            '["search term 1", "search term 2", "search term 3",'
            '"search term 4", "search term 5"]'
        )

    prompt = f"""
# Role: Video Search Terms Generator


## Goals:
{goal}

## Constrains:
1. the search terms are to be returned as a json-array of strings.
2. each search term should consist of 1-3 words, always add the main subject of the video.
3. you must only return the json-array of strings. you must not return anything else. you must not return the script.
4. the search terms must be related to the subject of the video.
5. reply with english search terms only.
{ordering_rule}

## Output Example:
{output_example}

## Context:
### Video Subject
{video_subject}

### Video Script
{video_script}

Please note that you must use English for generating video search terms; Chinese is not accepted.
""".strip()

    logger.info(f"subject: {video_subject}, match_script_order: {match_script_order}")

    search_terms = []
    response = ""
    for i in range(_max_retries):
        try:
            if app_config is None:
                response = _generate_response(prompt)
            else:
                response = _generate_response(prompt, app_config=app_config)
            if response.startswith("Error: "):
                # generate_terms 的公开返回类型是 List[str]。如果把 Provider 的
                # 错误文案原样返回，下游只做空值判断时会把非空字符串误认为成功，
                # 素材下载循环还会按字符遍历错误文案，产生无意义的外部请求。
                # 这里统一返回空列表，让任务编排层在真实故障位置立即结束任务。
                logger.error(f"failed to generate video terms: {response}")
                return []
            search_terms = json.loads(_strip_code_fence(response))
            if not isinstance(search_terms, list) or not all(
                isinstance(term, str) for term in search_terms
            ):
                logger.error("response is not a list of strings.")
                continue

        except Exception as e:
            logger.warning(f"failed to generate video terms: {str(e)}")
            if response:
                match = re.search(r"\[.*]", response, re.DOTALL)
                if match:
                    try:
                        search_terms = json.loads(match.group())
                    except Exception as e:
                        # 这里保留重试流程，但必须记录 LLM 返回的非标准 JSON，
                        # 否则后续排查搜索词为空时无法定位
                        # 是模型格式问题还是解析逻辑问题。
                        logger.warning(f"failed to generate video terms: {str(e)}")

        if search_terms and len(search_terms) > 0:
            break
        if i < _max_retries - 1:
            logger.warning(f"failed to generate video terms, trying again... {i + 1}")

    logger.success(f"completed: \n{search_terms}")
    return search_terms


# =============================================================================
# Social publishing metadata
#
# 根据视频主题和脚本生成发布到短视频平台时常用的 title、caption 和 hashtags。
# 这块能力只复用现有 LLM provider，不接入任何外部发布服务，也不影响视频生成主链路。
# =============================================================================

# 不同平台的文案长度和 hashtag 数量偏好不同。这里使用保守上限，避免模型返回
# 过长内容后调用方还需要二次裁剪。
SOCIAL_PLATFORMS = {
    "tiktok": {"title_max": 100, "caption_max": 2200, "hashtag_count": 5},
    "youtube_shorts": {"title_max": 100, "caption_max": 5000, "hashtag_count": 3},
    "instagram_reels": {"title_max": 125, "caption_max": 2200, "hashtag_count": 8},
    "facebook_reels": {"title_max": 125, "caption_max": 2200, "hashtag_count": 5},
}
DEFAULT_SOCIAL_PLATFORM = "tiktok"
DEFAULT_SOCIAL_LANGUAGE = "auto"
MAX_SOCIAL_SUBJECT_LENGTH = 500
MAX_SOCIAL_SCRIPT_LENGTH = 8000
MAX_SOCIAL_LANGUAGE_LENGTH = 64

SOCIAL_PLATFORM_LABELS = {
    "tiktok": "TikTok",
    "youtube_shorts": "YouTube Shorts",
    "instagram_reels": "Instagram Reels",
    "facebook_reels": "Facebook Reels",
}

# LLM 不可用时的通用兜底标签。这里故意不绑定某个国家或语种，保证 API
# 对中文、英文、越南语等不同场景都能返回可用结构。
DEFAULT_SOCIAL_HASHTAGS = [
    "#shorts",
    "#viral",
    "#trending",
    "#fyp",
    "#video",
    "#reels",
    "#creator",
    "#content",
]

def generate_image_prompts(
    video_subject: str,
    video_script: str,
    amount: int,
    app_config=None,
) -> List[str]:
    """
    Generate chronological, detailed visual prompts for AI image generation.

    Unlike generate_terms(), these are not stock-video search keywords.
    Each item describes one concrete visual scene for image models such as
    Z-Image, FLUX or SDXL.
    """
    amount = max(1, int(amount))

    prompt = f"""
# Role: AI Video Scene Prompt Generator

## Goal
Create exactly {amount} detailed image-generation prompts that visually follow
the narration from beginning to end.

## Rules
1. Return ONLY a valid JSON array containing exactly {amount} strings.
2. Prompts must be in English.
3. Each prompt represents one chronological visual scene.
4. Cover the entire script from beginning to end.
5. Do not repeat the same scene or composition unless the narration requires it.
6. Each prompt should be approximately 20-45 words.
7. Describe the concrete subject, environment, composition, camera/framing and lighting.
8. Prefer visually specific descriptions instead of abstract concepts.
9. When depicting real animals, organisms, objects, places or scientific concepts,
   make them visually and scientifically plausible.
10. Use a vertical composition with the important subject near the center and
    important details away from the extreme edges.
11. Do not generate visible text, captions, logos, watermarks or UI elements.
12. Do not write labels such as "Scene 1", "Scene 2", etc.
13. Do not return stock-video search keywords. These prompts will be sent directly
    to an AI image generator.
14. Earlier prompts must correspond to earlier narration and later prompts to later narration.

## Video Subject
{video_subject}

## Full Narration
{video_script}

Return exactly {amount} prompts as a JSON array and nothing else.
""".strip()

    response = ""

    for i in range(_max_retries):
        try:
            if app_config is None:
                response = _generate_response(prompt)
            else:
                response = _generate_response(prompt, app_config=app_config)

            if response.startswith("Error: "):
                logger.error(f"failed to generate image prompts: {response}")
                return []

            image_prompts = json.loads(_strip_code_fence(response))

            if not isinstance(image_prompts, list):
                raise ValueError("response is not a JSON list")

            image_prompts = [
                str(item).strip()
                for item in image_prompts
                if isinstance(item, str) and item.strip()
            ]

            if len(image_prompts) != amount:
                raise ValueError(
                    f"expected exactly {amount} image prompts, "
                    f"but received {len(image_prompts)}"
                )

            logger.success(
                f"generated {len(image_prompts)} chronological AI image prompts"
            )
            logger.debug(
                f"AI image prompts:\n{json.dumps(image_prompts, ensure_ascii=False, indent=2)}"
            )
            return image_prompts

        except Exception as e:
            logger.warning(
                f"failed to generate AI image prompts: {type(e).__name__}: {e}"
            )

        if i < _max_retries - 1:
            logger.warning(
                f"retrying AI image prompt generation... {i + 1}"
            )

    return []

_KNOWN_VISUAL_IDENTITY_FALLBACKS = (
    (
        ("tardigrade", "tardigrado", "tardígrado", "water bear"),
        "microscopic tardigrade (water bear), plump segmented translucent body, "
        "exactly four pairs of short stubby lobopod legs (eight legs total), "
        "tiny terminal claws, compact soft-bodied anatomy, no antennae, no wings, "
        "no long jointed insect-like legs, no hard crustacean carapace",
    ),
    (
        ("copepod", "copepods", "copepodo", "copépodo", "copépodos"),
        "microscopic planktonic copepod crustacean, small translucent teardrop or elongated body, "
        "long paired antennae, compact segmented trunk, forked tail region, delicate swimming appendages, "
        "not shaped like an insect or large shrimp",
    ),
    (
        ("diatom", "diatoms", "diatomea", "diatomeas"),
        "single-celled diatom microalga with a rigid glass-like silica frustule, "
        "fine geometric pores and radial or bilateral symmetry, intricate mineral shell, "
        "no animal limbs or multicellular body",
    ),
    (
        ("dinoflagellate", "dinoflagellates", "dinoflagelado", "dinoflagelados"),
        "single-celled dinoflagellate plankton, compact unicellular body with sculpted surface or armored plates, "
        "two flagellar grooves/flagella when visible, microscopic scale, blue bioluminescent emission when relevant, "
        "no multicellular animal anatomy",
    ),
    (
        ("bacteria", "bacterium", "bacteria", "bacterias", "bacteria marina", "bacterias marinas"),
        "microscopic bacterial cells at true cellular scale, rods, cocci or curved cells as appropriate, "
        "simple prokaryotic cell morphology, no limbs, no animal anatomy",
    ),
    (
        ("virus", "viruses", "virus marino", "virus marinos", "marine virus", "marine viruses"),
        "nanoscale virus particles shown as a scientific visualization, compact capsids or bacteriophage-like forms "
        "only when appropriate, clearly non-cellular particles, no animal anatomy or oversized fantasy creatures",
    ),
)


def _known_visual_identity_fallback(narration: str) -> str:
    """Return an optional safety-net identity hint for a few known difficult subjects.

    The structured LLM planner remains the general mechanism for every topic. These
    entries only reinforce subjects that have historically been confused by image
    models; they are not required for routing or for unrelated themes to work.
    """
    normalized = (narration or "").strip().lower()
    for aliases, hint in _KNOWN_VISUAL_IDENTITY_FALLBACKS:
        if any(alias in normalized for alias in aliases):
            return hint
    return ""


def _normalize_visual_feature_list(value, *, max_items: int = 8) -> list[str]:
    """Normalize LLM-provided visual constraints into a compact list of strings."""
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip().strip(".;")
        if text and text.lower() not in {entry.lower() for entry in result}:
            result.append(text)
        if len(result) >= max_items:
            break
    return result



_ARTIFICIAL_REFERENCE_PRESENTATION_RE = re.compile(
    r"\b(?:"
    r"microscope\s+(?:eyepiece|field|viewport|frame|circle|oval)|"
    r"through\s+(?:a|the)\s+microscope|"
    r"circular\s+(?:microscope\s+)?(?:field|frame|viewport|viewing\s+area|crop|border)|"
    r"oval\s+(?:microscope\s+)?(?:field|frame|viewport|viewing\s+area|crop|border)|"
    r"eyepiece\s+(?:view|frame|border|circle)|"
    r"petri\s+dish\s+(?:frame|framing|view|presentation)|"
    r"specimen\s+(?:plate|slide)\s+(?:frame|framing|presentation)|"
    r"isolated\s+specimen\s+(?:presentation|display)"
    r")\b",
    re.IGNORECASE,
)

_EXPLICIT_PRESENTATION_REQUEST_RE = re.compile(
    r"\b(?:"
    r"microscope|microscopy|eyepiece|petri\s+dish|specimen\s+slide|specimen\s+plate|"
    r"microscopio|microscopía|microscopia|ocular|placa\s+de\s+petri|portaobjetos|"
    r"campo\s+circular|campo\s+oval(?:ado)?"
    r")\b",
    re.IGNORECASE,
)


def _sanitize_precision_scene_field(
    value: str,
    *,
    field_name: str,
    narration: str,
) -> str:
    """Prevent the LLM scene plan from reintroducing reference-photo framing.

    This is intentionally topic-agnostic: it only intervenes when a precision scene
    contains an artificial presentation device that the narration itself did not ask
    for. Literal requests for a microscope/slide/Petri-dish view remain untouched.
    """
    text = str(value or "").strip().rstrip(" .")
    if not text or _EXPLICIT_PRESENTATION_REQUEST_RE.search(narration or ""):
        return text
    if not _ARTIFICIAL_REFERENCE_PRESENTATION_RE.search(text):
        return text

    logger.warning(
        "sanitized precision scene direction that introduced artificial reference framing: "
        f"field={field_name!r}, original={text!r}"
    )
    if field_name == "composition":
        return (
            "natural full-frame composition at a scientifically plausible scale, "
            "clear visual focus appropriate to the narration, no artificial viewing boundary"
        )
    if field_name == "environment":
        return (
            "continuous edge-to-edge environment appropriate to the narration and the "
            "subject's real scale"
        )

    # For prose fields, remove only the offending presentation phrase and preserve
    # the factual scene content around it.
    cleaned = _ARTIFICIAL_REFERENCE_PRESENTATION_RE.sub("full-frame view", text)
    return re.sub(r"\s{2,}", " ", cleaned).strip(" ,;.-")


def _resolve_semantic_image_route(
    requested_route: str,
    narration: str,
    identity_hint: str,
    shared_visual_style: str,
) -> str:
    """Choose a stable scene route and never let the LLM downgrade known hard subjects."""
    route = str(requested_route or "").strip().lower()
    if identity_hint:
        return "precision"

    # Let the director request precision for other literal/factual scenes, but keep
    # the public route vocabulary deliberately tiny so material.py can route it safely.
    if route in {"precision", "scientific", "reference", "factual"}:
        return "precision"
    return "standard"


DEFAULT_OPENAI_IMAGE_VISUAL_STYLE = (
    "high-end factual documentary realism, photorealistic rendering, natural color science, "
    "controlled cinematic contrast, restrained saturation, realistic optics, subtle depth of field, "
    "coherent lighting, clean detail, no fantasy stylization"
)


def _openai_image_shared_visual_style(app_config=None) -> str:
    runtime_config = app_config if app_config is not None else config.app
    configured = str(runtime_config.get("openai_image_visual_style", "") or "").strip()
    return configured or DEFAULT_OPENAI_IMAGE_VISUAL_STYLE


def _normalize_scene_enum(value: str, allowed: set[str], default: str) -> str:
    value = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return value if value in allowed else default


_SCENE_SHOT_TYPES = {"wide", "full", "medium", "close", "detail", "macro", "context"}
_SCENE_FRAMING_INTENTS = {"full_subject", "medium_subject", "detail", "context", "macro"}
_SCENE_REFERENCE_NEEDS = {"none", "identity", "detail", "internal", "context"}
_SCENE_ROLES = {"establish", "identity", "detail", "context", "process", "evidence", "transition", "closing"}
_SCENE_EVIDENCE_SCOPES = {
    "externally_visible",
    "specialized_visible",
    "hidden_internal",
    "contextual",
}
_SCENE_REFERENCE_TARGETS = {
    "primary_subject",
    "output",
    "secondary_subject",
    "environment",
    "none",
}


def _coerce_scene_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _reference_inventory_roles(reference_inventory: list[dict] | None) -> set[str]:
    return {
        str(item.get("role") or "identity").strip().lower()
        for item in (reference_inventory or [])
        if isinstance(item, dict)
    }


def _scene_hidden_evidence_signals(item: dict) -> list[str]:
    """Detect generic language that explicitly asks for a normally hidden view.

    This is intentionally topic-agnostic. It does not try to know whether a
    particular mechanism is real; it only notices when the requested camera view
    itself admits that the evidence is internal, layered, cut away or disassembled.
    """
    if not isinstance(item, dict):
        return []
    values = [
        item.get("scene_description"),
        item.get("environment"),
        item.get("composition"),
        item.get("reference_query"),
        " ".join(_normalize_visual_feature_list(item.get("required_features"))),
    ]
    text = " ".join(str(value or "") for value in values).lower()
    phrases = (
        "cutaway",
        "cross-section",
        "cross section",
        "inside the ",
        "inside a ",
        "inside an ",
        "internal ",
        "internal-",
        "interior cavity",
        "inside cavity",
        "between layers",
        "between the layers",
        "within layers",
        "beneath the surface",
        "under the surface",
        "opened housing",
        "open housing",
        "disassembled",
        "transparent enclosure",
        "transparent housing",
    )
    return [phrase.strip() for phrase in phrases if phrase in text]


def _scene_reference_coverage(
    item: dict,
    reference_inventory: list[dict] | None,
) -> tuple[str, str]:
    """Return whether the available manual evidence supports this scene's requested view."""
    inventory = [x for x in (reference_inventory or []) if isinstance(x, dict)]
    if not inventory:
        return (
            "unknown",
            "no manual reference inventory is available; downstream automatic reference routing may still provide evidence",
        )

    roles = _reference_inventory_roles(inventory)
    need = _normalize_scene_enum(
        item.get("reference_need"),
        _SCENE_REFERENCE_NEEDS,
        "none",
    )
    default_scope = (
        "hidden_internal"
        if need == "internal"
        else "specialized_visible"
        if need == "detail"
        else "contextual"
        if need in {"none", "context"}
        else "externally_visible"
    )
    scope = _normalize_scene_enum(
        item.get("evidence_scope"),
        _SCENE_EVIDENCE_SCOPES,
        default_scope,
    )
    critical = _coerce_scene_bool(item.get("reference_critical"), False)
    target = _normalize_scene_enum(
        item.get("reference_target"),
        _SCENE_REFERENCE_TARGETS,
        (
            "primary_subject"
            if need in {"identity", "detail", "internal"}
            else "environment"
            if need == "context"
            else "none"
        ),
    )

    # The current manual library is an identity/evidence pack for the primary
    # subject. Do not silently treat those images as proof of a produced output or
    # a distinct secondary entity just because they belong to the same topic.
    if target in {"output", "secondary_subject", "none"} and (
        need in {"identity", "detail", "internal"}
        or scope in {"specialized_visible", "hidden_internal"}
        or critical
    ):
        return (
            "unsupported",
            f"manual reference inventory targets the primary subject, not reference_target={target!r}",
        )
    if target == "environment" and need not in {"none", "context"}:
        return (
            "unsupported",
            f"environment reference_target cannot satisfy reference_need={need!r}",
        )

    required_role = ""
    if scope == "hidden_internal":
        required_role = "internal"
    elif scope == "specialized_visible":
        if need == "context":
            required_role = "context"
        else:
            required_role = "detail"
    elif scope == "externally_visible" and critical:
        required_role = "identity"
    elif scope == "contextual" and need == "context":
        required_role = "context"

    if not required_role:
        return "covered", "scene does not require a dedicated manual evidence role"
    if required_role in roles:
        return "covered", f"manual reference inventory contains required role {required_role!r}"
    return (
        "unsupported",
        f"manual reference inventory lacks required role {required_role!r} for evidence_scope={scope!r}",
    )


def _scene_plan_preflight_issues(
    items: list[dict],
    *,
    reference_inventory: list[dict] | None = None,
    precision_budget_ratio: float = 1.0,
) -> list[str]:
    """Cheap deterministic QA for diversity, factual support and routing before GPU work."""
    issues = list(_scene_plan_diversity_issues(items))
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            issues.append(f"scene {index} is not a JSON object")
            continue

        required = {
            str(value).strip().lower()
            for value in _normalize_visual_feature_list(item.get("required_features"))
        }
        forbidden = {
            str(value).strip().lower()
            for value in _normalize_visual_feature_list(item.get("forbidden_features"))
        }
        overlap = sorted(required & forbidden)
        if overlap:
            issues.append(
                f"scene {index} has contradictory required/forbidden features: {overlap!r}"
            )

        need = _normalize_scene_enum(
            item.get("reference_need"),
            _SCENE_REFERENCE_NEEDS,
            "none",
        )
        scope = _normalize_scene_enum(
            item.get("evidence_scope"),
            _SCENE_EVIDENCE_SCOPES,
            (
                "hidden_internal"
                if need == "internal"
                else "specialized_visible"
                if need == "detail"
                else "contextual"
                if need in {"none", "context"}
                else "externally_visible"
            ),
        )
        hidden_signals = _scene_hidden_evidence_signals(item)
        if hidden_signals and scope != "hidden_internal":
            issues.append(
                f"scene {index} explicitly requests a hidden/cutaway view ({hidden_signals!r}) but evidence_scope is {scope!r}; use hidden_internal"
            )
        if scope == "hidden_internal" and need != "internal":
            issues.append(
                f"scene {index} depicts hidden/internal evidence but reference_need is {need!r}; use reference_need='internal'"
            )

        coverage_status, coverage_reason = _scene_reference_coverage(
            item,
            reference_inventory,
        )
        if coverage_status == "unsupported":
            issues.append(
                f"scene {index} lacks evidence coverage and must be rewritten as a covered external/contextual scene before generation: {coverage_reason}"
            )

    continuity_groups: dict[str, dict[str, str]] = {}
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        key = re.sub(
            r"[^a-z0-9_]+",
            "_",
            str(item.get("continuity_key") or "none").strip().lower(),
        ).strip("_") or "none"
        if key == "none":
            continue
        description = " ".join(
            str(item.get("continuity_description") or "").strip().lower().split()
        )
        canonical = " ".join(
            str(item.get("canonical_subject") or item.get("subject") or "")
            .strip()
            .lower()
            .split()
        )
        if not description:
            issues.append(
                f"scene {index} continuity_key={key!r} has no continuity_description"
            )
            continue
        previous = continuity_groups.get(key)
        if previous is None:
            continuity_groups[key] = {
                "description": description,
                "canonical_subject": canonical,
            }
            continue
        if description != previous["description"]:
            issues.append(
                f"scene {index} changes continuity_description inside continuity_key={key!r}; keep the same underlying instance/content"
            )
        if canonical and previous["canonical_subject"] and canonical != previous["canonical_subject"]:
            issues.append(
                f"scene {index} changes canonical_subject inside continuity_key={key!r}"
            )

    try:
        ratio = max(0.0, min(1.0, float(precision_budget_ratio)))
    except (TypeError, ValueError):
        ratio = 1.0
    if items and ratio < 0.999:
        allowed_critical = max(1, int(math.ceil(len(items) * ratio)))
        critical_count = sum(
            _coerce_scene_bool(item.get("reference_critical"), False)
            for item in items
            if isinstance(item, dict)
        )
        if critical_count > allowed_critical:
            issues.append(
                f"reference_critical is over budget ({critical_count}>{allowed_critical}); keep only genuinely identity/factual-critical scenes critical and redesign the others as context/process/transition shots"
            )

    # Preserve order while deduplicating repeated deterministic findings.
    return list(dict.fromkeys(issues))


def _scene_plan_diversity_issues(items: list[dict]) -> list[str]:
    """Cheap deterministic QA for the LLM plan before any GPU image is generated."""
    if len(items) < 4:
        return []
    issues: list[str] = []
    env_keys = [str(i.get("environment_key") or "").strip().lower() for i in items]
    shot_types = [str(i.get("shot_type") or "").strip().lower() for i in items]
    environments = [str(i.get("environment") or "").strip().lower() for i in items]
    composition_keys = [
        str(i.get("composition_key") or "").strip().lower() for i in items
    ]

    # No environment family should dominate a normal multi-scene video.
    nonempty_env = [x for x in env_keys if x]
    if len(items) >= 6 and nonempty_env and len(set(nonempty_env)) < 3:
        issues.append("use at least three meaningfully different environment families")
    for key in sorted(set(nonempty_env)):
        if nonempty_env.count(key) > max(2, (len(items) + 3) // 4):
            issues.append(f"environment family {key!r} is repeated too often")

    # Three identical shot scales in a row usually reads like a slideshow/catalogue.
    for idx in range(len(shot_types) - 2):
        triple = shot_types[idx:idx + 3]
        if triple[0] and len(set(triple)) == 1:
            issues.append(f"shot type {triple[0]!r} repeats for three consecutive scenes")
            break
    if len(items) >= 7 and len({x for x in shot_types if x}) < 3:
        issues.append("use at least three shot types across the video")

    for idx in range(len(composition_keys) - 2):
        triple = composition_keys[idx:idx + 3]
        if triple[0] and len(set(triple)) == 1:
            issues.append(
                f"composition family {triple[0]!r} repeats for three consecutive scenes"
            )
            break

    # Controlled/plain presentation is valid, but should not silently become the whole video.
    controlled_terms = ("studio", "showroom", "plain background", "neutral background", "seamless background")
    controlled_count = sum(any(term in env for term in controlled_terms) for env in environments)
    if len(items) >= 6 and controlled_count > 2:
        issues.append("controlled/studio/plain-background scenes are overused; prefer narration-grounded context")
    return issues


def _build_structured_scene_image_prompt(
    *,
    subject: str,
    route: str,
    narration: str,
    scene_description: str,
    required_features: list[str],
    forbidden_features: list[str],
    environment: str,
    composition: str,
    lighting: str,
    identity_hint: str,
    shared_visual_style: str,
    shot_type: str = "full",
    framing_intent: str = "full_subject",
) -> str:
    """Build a theme-agnostic, model-facing prompt from the structured scene plan."""
    subject = str(subject or "").strip()
    narration = str(narration or "").strip()
    scene_description = str(scene_description or "").strip().rstrip(" .")
    environment = str(environment or "").strip().rstrip(" .")
    composition = str(composition or "").strip().rstrip(" .")
    lighting = str(lighting or "").strip().rstrip(" .")
    shot_type = _normalize_scene_enum(shot_type, _SCENE_SHOT_TYPES, "full")
    framing_intent = _normalize_scene_enum(
        framing_intent, _SCENE_FRAMING_INTENTS, "full_subject"
    )

    if route == "precision":
        scene_description = _sanitize_precision_scene_field(
            scene_description, field_name="scene_description", narration=narration
        )
        environment = _sanitize_precision_scene_field(
            environment, field_name="environment", narration=narration
        )
        composition = _sanitize_precision_scene_field(
            composition, field_name="composition", narration=narration
        )

    parts: list[str] = []
    if route == "precision":
        parts.append(
            f"{subject}, rendered with accurate factual identity, morphology, proportions and physically plausible scale"
        )
        if required_features:
            parts.append("Clearly preserve these subject-defining visible traits: " + "; ".join(required_features))
        elif identity_hint:
            parts.append(f"Subject-defining morphology: {identity_hint}")
    else:
        parts.append(f"Main visible subject: {subject}")
        if required_features:
            parts.append("Important visible details: " + "; ".join(required_features))

    if scene_description:
        parts.append(f"Scene action and visual content: {scene_description}")
    elif narration:
        parts.append(f"Visualize this narration literally: {narration}")
    if environment:
        parts.append(f"Environment: {environment}")
    if composition:
        parts.append(f"Camera and composition: {composition}")
    if lighting:
        parts.append(f"Lighting: {lighting}")

    # Deterministic framing constraints prevent accidental catalogue crops while still
    # allowing intentional details/macro shots for any topic.
    if framing_intent == "full_subject":
        parts.append(
            "Framing rule: show the complete important subject comfortably inside the vertical frame with safe margins; "
            "do not crop defining extremities, edges, wheels, limbs, top or base unless physically impossible"
        )
    elif framing_intent == "medium_subject":
        parts.append(
            "Framing rule: a deliberate medium crop is allowed, but keep the complete identifying region and enough context to read the subject clearly"
        )
    elif framing_intent == "detail":
        parts.append(
            "Framing rule: a deliberate close crop is allowed only around the narrated feature; make the feature unambiguous and physically connected to the subject"
        )
    elif framing_intent == "macro":
        parts.append(
            "Framing rule: macro/microscopic framing is intentional; preserve plausible scale cues and do not add artificial circular viewports or presentation borders"
        )
    else:
        parts.append(
            "Framing rule: prioritize the narration-grounded environment while keeping the main subject clearly readable and intentionally composed"
        )

    parts.append(
        "Render one complete physically coherent edge-to-edge scene in a single pass. Subject and environment must share continuous lighting, focus, depth of field, atmosphere and photographic response"
    )
    if forbidden_features:
        # Keep this concise; Qwen also receives the same constraints through a real negative prompt.
        parts.append("Avoid factual substitutions or misleading structures such as: " + "; ".join(forbidden_features[:6]))
    if shared_visual_style:
        parts.append(shared_visual_style)

    parts.append(
        "Vertical 9:16 composition. No captions, watermarks, UI overlays or unrelated readable text. "
        "Do not invent or garble branding, labels or markings; if an authentic marking cannot be reproduced reliably, leave it unobtrusive rather than fabricating substitute text"
    )
    return ". ".join(part for part in parts if part).strip() + "."


def generate_scene_image_plan(
    video_subject: str,
    scene_plan: list[dict],
    app_config=None,
    reference_inventory: list[dict] | None = None,
    precision_budget_ratio: float = 1.0,
) -> list[dict]:
    """Create a factual, diverse and reference-aware visual plan before GPU generation."""
    if not scene_plan:
        return []

    amount = len(scene_plan)
    scene_context = []
    identity_hints: list[str] = []
    shared_visual_style = _openai_image_shared_visual_style(app_config)
    reference_inventory = [dict(item) for item in (reference_inventory or []) if isinstance(item, dict)]

    for index, scene in enumerate(scene_plan):
        narration = str(scene.get("narration", "")).strip()
        identity_hint = _known_visual_identity_fallback(narration)
        identity_hints.append(identity_hint)
        scene_context.append(
            {
                "scene": index + 1,
                "narration": narration,
                "beat": f"{scene.get('beat', 1)}/{scene.get('beats', 1)}",
                "duration_seconds": round(float(scene.get("duration", 0) or 0), 2),
                "known_identity_constraint": identity_hint or None,
            }
        )

    inventory_text = json.dumps(reference_inventory, ensure_ascii=False, indent=2) if reference_inventory else "[]"
    prompt = f"""
# Role: Documentary Visual Director and Factual Scene Planner

Create a chronological visual plan for AI image generation. The topic can be anything. Do not assume vehicles,
animals, products, science, history, people or any other fixed subject category. Plan from the narration itself.

## Output
Return ONLY a valid JSON array containing exactly {amount} objects. Every object MUST contain:
- "subject": concrete English name of the visible subject in this scene
- "canonical_subject": stable factual identity shared by scenes that depict the same real subject
- "route": "standard" or "precision"
- "scene_description": literal visible content
- "required_features": 0-7 concrete factual visible traits
- "forbidden_features": 0-7 likely misleading substitutions/structural errors
- "environment": narration-grounded environment/background
- "environment_key": short lowercase semantic family name for that environment
- "composition": camera position, angle and layout for a vertical image
- "composition_key": short lowercase semantic family name for the camera/composition setup
- "lighting": realistic lighting
- "shot_type": one of wide, full, medium, close, detail, macro, context
- "framing_intent": one of full_subject, medium_subject, detail, context, macro
- "shot_role": one of establish, identity, detail, context, process, evidence, transition, closing
- "reference_need": one of none, identity, detail, internal, context
- "reference_target": one of primary_subject, output, secondary_subject, environment, none
- "reference_query": short phrase describing what a useful reference should visibly show
- "evidence_scope": one of externally_visible, specialized_visible, hidden_internal, contextual
- "reference_critical": JSON boolean; true only when a generic/wrong subject or unsupported view would materially mislead
- "safe_visual_alternative": concise externally supported or contextual scene description to use if requested specialized evidence is unavailable
- "continuity_key": short stable id shared only by scenes that show the same physical instance/output evolving over time; otherwise "none"
- "continuity_description": when continuity_key is not "none", one exact stable English description of the underlying object's/content's identity that MUST remain unchanged across those scenes
- "precision_importance": number from 0.0 to 1.0 indicating how damaging a generic/wrong visual substitute would be

## Routing
Use precision only when exact factual appearance materially matters. Use standard for atmosphere, generic context,
landscapes, broad concepts and shots where a generic rendering is not misleading. A known identity constraint must
remain precision before later performance budgeting.

## Direction and diversity rules
1. Visualize the current narration beat, not the whole topic.
2. Treat the sequence as a documentary/edit, not a product catalogue or nine unrelated hero photos.
3. Do not repeat the same environment_key more than necessary. For 6+ scenes, normally use at least three
   meaningful environment families unless continuity genuinely requires otherwise.
4. Do not use the same shot_type for three consecutive scenes. For 7+ scenes, normally use at least three shot types.
5. Controlled/studio/plain backgrounds are valid when narratively useful but should not become the default background.
6. Vary visual function: establishing/context/evidence/detail/process/closing as appropriate to the narration.
7. Full-subject shots must leave safe margins. Close/detail crops must be intentional and tied to the narrated feature.
8. References, when supplied later, are identity/evidence sources only; never design a scene around copying their
   background, pose, crop, lighting or presentation.
9. Never invent readable captions, fake branding, fake UI or fake documentary evidence.
10. Classify evidence_scope independently from shot scale. A close/detail shot can still be hidden_internal if it depicts
    a mechanism, anatomy, layer or structure that is not normally visible from the outside. Never label hidden evidence
    as merely "detail" because the camera is close.
11. If evidence_scope=hidden_internal, reference_need must normally be internal. If the manual reference inventory has no
    suitable internal evidence, plan safe_visual_alternative around an externally visible cause/effect, context, or other
    narration-faithful representation. Do not invent the hidden structure.
12. specialized_visible means a real visible feature/view that needs dedicated evidence. It is not a substitute for
    hidden_internal.
13. Set reference_critical=true sparingly when exact identity/factual evidence must survive performance budgeting. The
    number of critical scenes should fit the Precision budget for this task; redesign non-critical beats as contextual,
    process or transition shots instead of marking everything critical.
14. Preserve continuity of canonical_subject across close-ups/details. Do not silently change the real subject identity.
15. required_features and forbidden_features must not contradict one another. Do not assert exact counts, hidden geometry,
    mechanisms or branded markings unless supported by narration or available reference metadata.
16. Respect real scale and physical context. No artificial circular/oval viewports, cards, cutouts or collage layouts
    unless the narration explicitly requires them.
17. reference_target describes WHAT ENTITY the selected reference would prove. Use primary_subject only when the visible
    entity is the same real subject as the task identity pack. A photograph, manufactured output, emitted object, result,
    by-product or image produced by the primary subject is output, not primary_subject. A different real entity is
    secondary_subject. Background evidence is environment.
18. Identity references for the primary subject must never be used as evidence for output, secondary_subject or
    environment merely because those things appear in the same story.
19. Perform an observability check before declaring evidence externally_visible: a normal camera at the stated vantage
    must actually be able to see the claimed feature/process. Anything inside an opaque enclosure, beneath a surface,
    between layers, inside tissue/material, or requiring disassembly/cutaway is hidden_internal even when its external
    consequence is visible. Represent the visible consequence instead when hidden evidence is unavailable.
20. Treat mechanically/chemically/biologically specific narration conservatively. Do not turn an asserted cause into a
    visible structure or process unless the narration/reference evidence really makes that view observable. Prefer an
    observable before/after/result/context shot over plausible-looking invented documentary evidence.
21. primary_subject means the actual whole entity represented by the manual identity pack. A cartridge, film sheet,
    reagent pod, roller assembly, internal component, emitted result or produced image is not automatically the
    primary_subject merely because it belongs to that object or shares its brand/model name.
22. If consecutive scenes show temporal stages of the SAME physical instance or produced output, use one continuity_key
    and exactly the same continuity_description in every stage. Keep the underlying depicted content, object identity and
    setting stable; change only the narrated state/progression. Do not silently switch to a different photograph, person,
    room, landscape, object instance or output between stages.

## Manual reference inventory available to this task
Each item may include role=identity/detail/internal/context/other and an optional user description.
Use this only to decide whether a requested view is actually supported; filenames are not factual evidence.
{inventory_text}

## Performance budget
The current task can normally retain about {max(1, int(math.ceil(amount * max(0.0, min(1.0, float(precision_budget_ratio or 0.0))))))} reference-critical Precision scenes out of {amount}.
Do not mark more scenes reference_critical unless the narration genuinely cannot be represented truthfully another way.

## Shared visual language
{shared_visual_style}

## Video subject
{video_subject}

## Timed narration scenes
{json.dumps(scene_context, ensure_ascii=False, indent=2)}

Return exactly {amount} objects and nothing else.
""".strip()

    response = ""
    for i in range(_max_retries):
        try:
            response = _generate_response(prompt) if app_config is None else _generate_response(prompt, app_config=app_config)
            if response.startswith("Error: "):
                logger.error(f"failed to generate structured image scene plan: {response}")
                return []
            payload = json.loads(_strip_code_fence(response))
            if not isinstance(payload, list) or len(payload) != amount:
                raise ValueError(f"expected {amount} scene objects")

            # One cheap text audit before any GPU work. This is deliberately a
            # correction pass, not an image judge: it checks whether the draft has
            # confused an inferred/internal cause with something a camera could
            # actually observe, and it also receives deterministic preflight issues.
            issues = _scene_plan_preflight_issues(
                payload,
                reference_inventory=reference_inventory,
                precision_budget_ratio=precision_budget_ratio,
            )
            runtime_config = app_config if app_config is not None else config.app
            audit_enabled = _coerce_scene_bool(
                runtime_config.get(
                    "openai_image_scene_factual_audit_enabled",
                    runtime_config.get("openai_image_scene_diversity_repair_enabled", True),
                ),
                True,
            )
            factual_audit_status = "disabled"
            if audit_enabled:
                issue_text = "\n- ".join(issues) if issues else "(no deterministic issues)"
                audit_prompt = (
                    prompt
                    + "\n\n## Draft plan to factually audit before GPU generation\n"
                    + json.dumps(payload, ensure_ascii=False, indent=2)
                    + "\n\n## Deterministic pre-GPU QA findings\n- "
                    + issue_text
                    + "\n\n## Factual/observability audit\n"
                      "Return a corrected JSON array with the same scene count and order. Audit every scene, even when "
                      "the deterministic list is empty. Ask whether a normal documentary camera at the stated vantage "
                      "could really see the described feature/process. Internal mechanisms, processes between layers, "
                      "contents behind opaque surfaces, cutaways and inferred hidden causes are hidden_internal. "
                      "An externally visible consequence does not make its hidden cause externally_visible. "
                      "Correct reference_target as well: primary_subject means the whole entity represented by the manual "
                      "identity pack. A cartridge, film sheet, reagent pod, roller assembly, internal component, produced "
                      "result/output or distinct entity is not automatically primary_subject. Never use whole-subject identity "
                      "photos as proof of an internal/subcomponent view. Preserve continuity_key groups so the exact same "
                      "physical instance/output and underlying depicted content remain stable across temporal stages. "
                      "When evidence is unavailable, redesign the scene around an observable consequence, before/after, "
                      "external behavior or context so that the resulting scene is covered; do not merely preserve the "
                      "unsupported hidden scene and label an alternative. Preserve narration meaning, timing, diversity "
                      "and sequence; do not add new mechanical, chemical, biological or branded facts."
                )
                try:
                    audited_response = (
                        _generate_response(audit_prompt)
                        if app_config is None
                        else _generate_response(audit_prompt, app_config=app_config)
                    )
                    audited = json.loads(_strip_code_fence(audited_response))
                    if isinstance(audited, list) and len(audited) == amount:
                        payload = audited
                        factual_audit_status = "applied"
                        issues = _scene_plan_preflight_issues(
                            payload,
                            reference_inventory=reference_inventory,
                            precision_budget_ratio=precision_budget_ratio,
                        )
                        if issues:
                            logger.warning(
                                "scene-plan factual audit left deterministic issues; hard gates will sanitize them: "
                                f"{issues!r}"
                            )
                        else:
                            logger.info("scene-plan factual/observability audit applied cleanly")
                    else:
                        factual_audit_status = "invalid"
                        logger.warning(
                            "scene-plan factual audit returned an invalid scene count; keeping draft plan"
                        )
                except Exception as audit_exc:
                    factual_audit_status = "failed"
                    logger.warning(
                        "scene-plan factual/observability audit failed; deterministic hard gates remain active: "
                        f"{type(audit_exc).__name__}: {audit_exc}"
                    )

            result: list[dict] = []
            for index, item in enumerate(payload):
                if not isinstance(item, dict):
                    raise ValueError(f"scene {index + 1} is not a JSON object")
                narration = str(scene_plan[index].get("narration", "")).strip()
                identity_hint = identity_hints[index]
                subject = str(item.get("subject") or "").strip()
                if not subject:
                    raise ValueError(f"scene {index + 1} has an empty subject")
                canonical_subject = str(item.get("canonical_subject") or subject).strip() or subject
                route = _resolve_semantic_image_route(
                    requested_route=str(item.get("route") or ""),
                    narration=narration,
                    identity_hint=identity_hint,
                    shared_visual_style=shared_visual_style,
                )
                required_features = _normalize_visual_feature_list(item.get("required_features"))
                forbidden_features = _normalize_visual_feature_list(item.get("forbidden_features"))
                shot_type = _normalize_scene_enum(item.get("shot_type"), _SCENE_SHOT_TYPES, "full")
                framing_intent = _normalize_scene_enum(item.get("framing_intent"), _SCENE_FRAMING_INTENTS, "full_subject")
                shot_role = _normalize_scene_enum(item.get("shot_role"), _SCENE_ROLES, "evidence")
                requested_reference_need = _normalize_scene_enum(
                    item.get("reference_need"),
                    _SCENE_REFERENCE_NEEDS,
                    "identity" if route == "precision" else "none",
                )
                evidence_scope = _normalize_scene_enum(
                    item.get("evidence_scope"),
                    _SCENE_EVIDENCE_SCOPES,
                    (
                        "hidden_internal"
                        if requested_reference_need == "internal"
                        else "specialized_visible"
                        if requested_reference_need == "detail"
                        else "contextual"
                        if requested_reference_need in {"none", "context"}
                        else "externally_visible"
                    ),
                )
                hidden_signals = _scene_hidden_evidence_signals(item)
                if hidden_signals:
                    if evidence_scope != "hidden_internal" or requested_reference_need != "internal":
                        logger.warning(
                            "scene-plan observability gate overrode LLM evidence classification: "
                            f"scene={index + 1}, signals={hidden_signals!r}, "
                            f"scope={evidence_scope!r}, need={requested_reference_need!r}"
                        )
                    evidence_scope = "hidden_internal"
                    requested_reference_need = "internal"
                reference_target = _normalize_scene_enum(
                    item.get("reference_target"),
                    _SCENE_REFERENCE_TARGETS,
                    (
                        "primary_subject"
                        if requested_reference_need in {"identity", "detail", "internal"}
                        else "environment"
                        if requested_reference_need == "context"
                        else "none"
                    ),
                )
                reference_critical = _coerce_scene_bool(
                    item.get("reference_critical"),
                    False,
                )
                coverage_status, coverage_reason = _scene_reference_coverage(
                    {
                        **item,
                        "reference_need": requested_reference_need,
                        "reference_target": reference_target,
                        "evidence_scope": evidence_scope,
                        "reference_critical": reference_critical,
                    },
                    reference_inventory,
                )
                safe_visual_alternative = str(
                    item.get("safe_visual_alternative") or ""
                ).strip()
                continuity_key = re.sub(
                    r"[^a-z0-9_]+",
                    "_",
                    str(item.get("continuity_key") or "none").strip().lower(),
                ).strip("_") or "none"
                continuity_description = " ".join(
                    str(item.get("continuity_description") or "").strip().split()
                )
                scene_description = str(item.get("scene_description") or "").strip()
                if continuity_key != "none" and continuity_description:
                    scene_description = (
                        scene_description.rstrip(" .")
                        + ". Continuity requirement: this is the exact same physical instance/content across all "
                        + f"stages of continuity group '{continuity_key}': {continuity_description}. "
                        + "Do not change the underlying depicted subject/content; change only the narrated state."
                    ).strip()
                environment = str(item.get("environment") or "").strip()
                composition = str(item.get("composition") or "").strip()
                lighting = str(item.get("lighting") or "").strip()
                environment_key_source = str(item.get("environment_key") or "context")
                composition_key_source = str(item.get("composition_key") or shot_type)
                reference_need = requested_reference_need
                planner_validation = "pass"

                # Deterministic coverage gate: if the audited plan is still
                # unsupported, discard *all* visual directions that could leak the
                # unverified mechanism. A generic external/context shot is less
                # specific, but it cannot become convincing fabricated evidence.
                if coverage_status == "unsupported":
                    planner_validation = "coverage_fallback"
                    scene_description = (
                        "Show only an externally visible result, behavior, before/after state, "
                        "or surrounding context relevant to this narration. Do not depict or "
                        "reconstruct internal mechanisms, hidden layers, cutaways, transparent "
                        "cross-sections, inferred structures, or an unverified process as directly visible."
                    )
                    subject = "externally visible result or context"
                    canonical_subject = subject
                    required_features = []
                    forbidden_features = []
                    environment = "natural narration-grounded context with no exposed hidden internals"
                    composition = (
                        "clear documentary context view of externally observable evidence; "
                        "no cutaway, disassembly, transparent enclosure, or invented internal view"
                    )
                    lighting = "natural documentary lighting"
                    environment_key_source = "coverage_safe_context"
                    composition_key_source = "coverage_safe_context"
                    shot_type = "context"
                    framing_intent = "context"
                    reference_need = "none"
                    reference_target = "none"
                    evidence_scope = "contextual"
                    continuity_key = "none"
                    continuity_description = ""
                    reference_critical = False
                    route = "standard"
                    logger.warning(
                        "scene-plan coverage gate hard-sanitized unsupported evidence before GPU generation: "
                        f"scene={index + 1}, requested_need={requested_reference_need!r}, "
                        f"reason={coverage_reason!r}"
                    )

                environment_key = re.sub(
                    r"[^a-z0-9_]+",
                    "_",
                    environment_key_source.strip().lower(),
                ).strip("_")[:48] or "context"
                composition_key = re.sub(
                    r"[^a-z0-9_]+",
                    "_",
                    composition_key_source.strip().lower(),
                ).strip("_")[:48] or shot_type
                try:
                    precision_importance = max(0.0, min(1.0, float(item.get("precision_importance", 0.7 if route == "precision" else 0.2))))
                except (TypeError, ValueError):
                    precision_importance = 0.7 if route == "precision" else 0.2

                if reference_critical and coverage_status != "unsupported":
                    route = "precision"

                final_prompt = _build_structured_scene_image_prompt(
                    subject=subject,
                    route=route,
                    narration=narration,
                    scene_description=scene_description,
                    required_features=required_features,
                    forbidden_features=forbidden_features,
                    environment=environment,
                    composition=composition,
                    lighting=lighting,
                    identity_hint=identity_hint,
                    shared_visual_style=shared_visual_style,
                    shot_type=shot_type,
                    framing_intent=framing_intent,
                )
                result.append({
                    "subject": subject,
                    "canonical_subject": canonical_subject,
                    "route": route,
                    "prompt": final_prompt,
                    "required_features": required_features,
                    "forbidden_features": forbidden_features,
                    "environment": environment,
                    "environment_key": environment_key,
                    "composition_key": composition_key,
                    "shot_type": shot_type,
                    "framing_intent": framing_intent,
                    "shot_role": shot_role,
                    "reference_need": reference_need,
                    "requested_reference_need": requested_reference_need,
                    "reference_target": reference_target,
                    "reference_query": str(item.get("reference_query") or "").strip(),
                    "evidence_scope": evidence_scope,
                    "reference_critical": reference_critical,
                    "coverage_status": coverage_status,
                    "coverage_reason": coverage_reason,
                    "safe_visual_alternative": safe_visual_alternative,
                    "planner_validation": planner_validation,
                    "factual_audit_status": factual_audit_status,
                    "continuity_key": continuity_key,
                    "continuity_description": continuity_description,
                    "precision_importance": precision_importance,
                })

            route_counts = {route: sum(1 for item in result if item["route"] == route) for route in {item["route"] for item in result}}
            logger.success(f"generated {amount} structured timed image scenes, routes={route_counts}")
            logger.debug("structured timed image scene plan:\n" + json.dumps(result, ensure_ascii=False, indent=2))
            return result
        except Exception as e:
            logger.warning(f"failed to generate structured timed image scene plan: {type(e).__name__}: {e}")
        if i < _max_retries - 1:
            logger.warning(f"retrying structured timed image scene plan... {i + 1}")
    return []

def generate_scene_image_prompts(
    video_subject: str,
    scene_plan: list[dict],
    app_config=None,
) -> List[str]:
    """Backward-compatible wrapper returning only prompts from the structured plan."""
    structured = generate_scene_image_plan(
        video_subject=video_subject,
        scene_plan=scene_plan,
        app_config=app_config,
    )
    return [str(item.get("prompt") or "") for item in structured if item.get("prompt")]

def _resolve_social_platform(platform: str | None) -> str:
    value = (platform or "").strip().lower()
    return value if value in SOCIAL_PLATFORMS else DEFAULT_SOCIAL_PLATFORM


def _normalize_social_language(language: str | None) -> str:
    value = (language or DEFAULT_SOCIAL_LANGUAGE).strip()
    if len(value) > MAX_SOCIAL_LANGUAGE_LENGTH:
        logger.warning(
            "social metadata language is too long and will be truncated to "
            f"{MAX_SOCIAL_LANGUAGE_LENGTH} characters."
        )
        value = value[:MAX_SOCIAL_LANGUAGE_LENGTH]
    return value or DEFAULT_SOCIAL_LANGUAGE


def _limit_social_text(text: str | None, max_length: int, field_name: str) -> str:
    value = (text or "").strip()
    if len(value) <= max_length:
        return value

    # API 层会限制长度；这里继续兜底，是为了保护内部调用或未来 WebUI
    # 直接调用时不会把超长内容发送给模型，避免 token 成本异常。
    logger.warning(
        f"{field_name} is too long and will be truncated to {max_length} characters."
    )
    return value[:max_length]


def _social_language_instruction(language: str | None) -> str:
    language = _normalize_social_language(language)
    if language.lower() == DEFAULT_SOCIAL_LANGUAGE:
        return (
            "Use the same language as the video subject and script. If the subject "
            "and script use different languages, prefer the script language."
        )

    return f'Write "title" and "caption" in this language: {language}.'


def _clamp_text(text, max_length: int) -> str:
    value = ("" if text is None else str(text)).strip()
    if max_length and len(value) > max_length:
        return value[:max_length].rstrip()
    return value


def _normalize_hashtags(raw, count: int) -> List[str]:
    """
    将 LLM 返回的 hashtag 统一整理成 `#tag` 格式。

    LLM 可能返回字符串、数组、带空格的词组、重复标签或包含标点的内容。
    这里集中清洗，可以让接口响应结构稳定，也避免平台发布时出现空标签、
    重复标签或不符合常见格式的 hashtag。
    """
    if isinstance(raw, str):
        candidates = re.split(r"[\s,]+", raw)
    elif isinstance(raw, (list, tuple)):
        # 数组里的每一项视为一个完整标签，因此 "du lich" 会变成
        # "#dulich"，而不是拆成两个标签。
        candidates = [str(entry) for entry in raw]
    else:
        candidates = []

    seen = set()
    result: List[str] = []
    for item in candidates:
        tag = re.sub(r"[^\w]", "", item, flags=re.UNICODE)
        if not tag:
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(f"#{tag}")
        if count and len(result) >= count:
            break
    return result


def build_social_metadata_prompt(
    video_subject: str,
    video_script: str = "",
    language: str = DEFAULT_SOCIAL_LANGUAGE,
    platform: str = DEFAULT_SOCIAL_PLATFORM,
) -> str:
    video_subject = _limit_social_text(
        video_subject, MAX_SOCIAL_SUBJECT_LENGTH, "video_subject"
    )
    video_script = _limit_social_text(
        video_script, MAX_SOCIAL_SCRIPT_LENGTH, "video_script"
    )
    platform = _resolve_social_platform(platform)
    spec = SOCIAL_PLATFORMS[platform]
    label = SOCIAL_PLATFORM_LABELS.get(platform, platform)
    language_instruction = _social_language_instruction(language)

    prompt = f"""
# Role: Short-Video Social Media Copywriter

## Goal
Write engaging publishing metadata for a short video that will be posted on {label}.

## Constraints
1. Respond ONLY with a single valid minified JSON object. No markdown, no code fences, no commentary.
2. The JSON must contain exactly these keys: "title", "caption", "hashtags".
3. "title": a catchy hook, at most {spec["title_max"]} characters.
4. "caption": an engaging description that ends with a call to action, at most {spec["caption_max"]} characters. Do not put hashtags inside the caption.
5. "hashtags": a JSON array of exactly {spec["hashtag_count"]} strings. Each must start with "#", contain no spaces, and be relevant to the topic and to {label}.
6. {language_instruction}

## Output Example
{{"title":"...","caption":"...","hashtags":["#example","#video"]}}

## Context
### Video Subject
{video_subject}

### Video Script
{video_script}
""".strip()
    return prompt


def _parse_social_metadata(response: str, platform: str) -> dict:
    spec = SOCIAL_PLATFORMS[_resolve_social_platform(platform)]

    data = None
    try:
        data = json.loads(_strip_code_fence(response))
    except Exception:
        # 部分模型会在 JSON 外层包一段说明文字或 markdown fence。
        # API 调用方只需要稳定结构，所以这里尝试提取第一个 JSON object。
        match = re.search(r"\{.*\}", response or "", re.DOTALL)
        if match:
            data = json.loads(match.group())

    if not isinstance(data, dict):
        raise ValueError("social metadata response is not a JSON object")

    title = _clamp_text(data.get("title", ""), spec["title_max"])
    caption = _clamp_text(data.get("caption", ""), spec["caption_max"])
    hashtags = _normalize_hashtags(data.get("hashtags", []), spec["hashtag_count"])

    if not title and not caption:
        raise ValueError("social metadata response is missing both title and caption")

    return {"title": title, "caption": caption, "hashtags": hashtags}


def _fallback_social_metadata(
    video_subject: str, video_script: str, platform: str
) -> dict:
    spec = SOCIAL_PLATFORMS[_resolve_social_platform(platform)]
    subject = (video_subject or "").strip()
    script = (video_script or "").strip()

    title = subject
    if not title and script:
        # 没有主题时，用脚本第一句兜底生成 title，避免接口返回空标题。
        title = re.split(r"(?<=[.!?。！？])\s+", script)[0]

    return {
        "title": _clamp_text(title, spec["title_max"]),
        "caption": _clamp_text(script or subject, spec["caption_max"]),
        "hashtags": _normalize_hashtags(DEFAULT_SOCIAL_HASHTAGS, spec["hashtag_count"]),
    }


def generate_social_metadata(
    video_subject: str,
    video_script: str = "",
    language: str = DEFAULT_SOCIAL_LANGUAGE,
    platform: str = DEFAULT_SOCIAL_PLATFORM,
) -> dict:
    """
    生成短视频发布文案元数据。

    返回结构固定为 `{"title": str, "caption": str, "hashtags": List[str]}`。
    如果 LLM 不可用或返回格式异常，会降级为通用启发式结果，保证 API
    调用方始终拿到可展示、可发布前编辑的数据结构。
    """
    platform = _resolve_social_platform(platform)
    language = _normalize_social_language(language)
    video_subject = _limit_social_text(
        video_subject, MAX_SOCIAL_SUBJECT_LENGTH, "video_subject"
    )
    video_script = _limit_social_text(
        video_script, MAX_SOCIAL_SCRIPT_LENGTH, "video_script"
    )
    prompt = build_social_metadata_prompt(
        video_subject=video_subject,
        video_script=video_script,
        language=language,
        platform=platform,
    )
    logger.info(f"generating social metadata: platform={platform}, language={language}")

    response = ""
    for i in range(_max_retries):
        try:
            response = _generate_response(prompt)
            if isinstance(response, str) and "Error: " in response:
                logger.error(f"failed to generate social metadata: {response}")
                break
            metadata = _parse_social_metadata(response, platform)
            logger.success(f"completed: \n{metadata}")
            return metadata
        except Exception as e:
            logger.warning(f"failed to parse social metadata: {str(e)}")

        if i < _max_retries - 1:
            logger.warning(
                f"failed to generate social metadata, trying again... {i + 1}"
            )

    logger.warning("falling back to heuristic social metadata")
    return _fallback_social_metadata(video_subject, video_script, platform)


if __name__ == "__main__":
    video_subject = "生命的意义是什么"
    script = generate_script(
        video_subject=video_subject, language="zh-CN", paragraph_number=1
    )
    print("######################")
    print(script)
    search_terms = generate_terms(
        video_subject=video_subject, video_script=script, amount=5
    )
    print("######################")
    print(search_terms)
