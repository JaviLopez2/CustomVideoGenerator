"""Explicit full-frame color/alpha preparation, with no model/admission authority."""
import hashlib
import io
import json
from pathlib import Path
import re

from PIL import Image, ImageCms, __version__ as pillow_version

BACKGROUND = [255, 255, 255]
MAX_BYTES = 64 * 1024 * 1024
MAX_PIXELS = 16 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def render(row):
    if not isinstance(row, dict) or set(row) != {"id", "source"}:
        raise ValueError("Unknown profiled-input record")
    if not isinstance(row["id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", row["id"]):
        raise ValueError("Invalid input identifier")
    source = row["source"]
    if not isinstance(source, dict) or set(source) != {"path", "sha256", "size"}:
        raise ValueError("Invalid source binding")
    size = source["size"]
    if (not isinstance(source["path"], str) or not Path(source["path"]).is_absolute()
            or not isinstance(source["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", source["sha256"])
            or not isinstance(size, list) or len(size) != 2
            or any(type(n) is not int or n <= 0 for n in size) or size[0] * size[1] > MAX_PIXELS):
        raise ValueError("Invalid absolute source/hash/dimensions")
    with Path(source["path"]).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES or digest(data) != source["sha256"]:
        raise ValueError("Oversized or changed source")
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR" or data[24] != 8:
        # Pillow's RGB/RGBA mode can conceal reduction of 16-bit PNG samples.
        raise ValueError("Expected native eight-bit PNG samples")
    with Image.open(io.BytesIO(data)) as image:
        if (image.format != "PNG" or image.mode not in {"RGB", "RGBA"} or list(image.size) != size
                or getattr(image, "n_frames", 1) != 1 or image.getexif().get(274) not in {None, 1}
                or any(k in image.info for k in ("transparency", "gamma", "chromaticity", "srgb"))):
            raise ValueError("Unsupported format/mode/orientation/color/transparency metadata")
        image.load()
        rgb = image.convert("RGB")
        original_rgb = rgb.tobytes()
        alpha = image.getchannel("A") if image.mode == "RGBA" else None
        icc = image.info.get("icc_profile")
        policy = "untagged_assumed_srgb"
        if "icc_profile" in image.info:
            if not isinstance(icc, bytes) or not icc:
                raise ValueError("Invalid embedded ICC")
            try:
                profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
                if profile.profile.xcolor_space.strip() != "RGB":
                    raise ValueError("Expected an RGB ICC profile")
                rgb = ImageCms.profileToProfile(rgb, profile, ImageCms.createProfile("sRGB"),
                       renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC, outputMode="RGB", flags=ImageCms.Flags.NONE)
            except (OSError, TypeError, ValueError, ImageCms.PyCMSError) as exc:
                raise ValueError("Unsupported embedded RGB ICC transform") from exc
            policy = "embedded_icc_to_srgb_relative_colorimetric"
        if alpha is not None:
            rgba = rgb.convert("RGBA"); rgba.putalpha(alpha)
            rgb = Image.alpha_composite(Image.new("RGBA", image.size, (*BACKGROUND, 255)), rgba).convert("RGB")
        pixels = rgb.tobytes()
        # Fresh object carries neither text nor any hidden EXIF/profile state.
        output = Image.frombytes("RGB", image.size, pixels)
        buffer = io.BytesIO(); output.save(buffer, format="PNG")
        encoded = buffer.getvalue()
        with Image.open(io.BytesIO(encoded)) as decoded:
            if decoded.mode != "RGB" or decoded.size != image.size or decoded.tobytes() != pixels or decoded.info:
                raise ValueError("Prepared PNG did not preserve the declared output")
        record = {"id": row["id"], "source": {**source, "size": list(size)}, "source_mode": image.mode, "source_bit_depth": 8,
                  "source_icc_sha256": digest(icc) if icc else None, "color_policy": policy,
                  "alpha_extrema": list(alpha.getextrema()) if alpha else None,
                  "source_alpha_sha256": digest(alpha.tobytes()) if alpha else None,
                  "background_srgb": list(BACKGROUND), "alpha_blending": "encoded_srgb_channels",
                  "rgb_samples_unchanged": pixels == original_rgb, "spatial_resampling": False,
                  "ancillary_metadata_copied": False, "semantic_human_review": "pending",
                  "prepared": {"sha256": digest(encoded), "pixel_sha256": digest(pixels), "size": list(size), "mode": "RGB"}}
    return record, encoded


def prepare(plan, output_dir, *, workspace_root):
    if (not isinstance(plan, dict) or set(plan) != {"protocol", "background_srgb", "images"}
            or plan["protocol"] != "profiled-visual-input-plan-1"
            or plan["background_srgb"] != BACKGROUND
            or any(type(n) is not int for n in plan["background_srgb"])
            or not isinstance(plan["images"], list) or not 1 <= len(plan["images"]) <= 16):
        raise ValueError("Unknown or changed preparation policy/budget")
    root, folder = Path(workspace_root).resolve(), Path(output_dir).resolve()
    if not root.is_dir() or folder == root or not folder.is_relative_to(root):
        raise ValueError("Output escapes supplied workspace")
    if folder.exists():
        raise FileExistsError("Preserve existing artifacts")
    prepared = [render(row) for row in plan["images"]]
    if len({record["id"] for record, _ in prepared}) != len(prepared):
        raise ValueError("Duplicate input identifiers")
    manifest = {"protocol": "profiled-visual-input-artifacts-1", "pillow_version": pillow_version,
                "littlecms_version": ImageCms.core.littlecms_version,
                "helper_sha256": digest(Path(__file__).read_bytes()),
                "plan_canonical_sha256": digest(json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()),
                "admission_allowed": False, "physical_identity_established": False,
                "model_requests": 0, "generation_requests": 0, "images": []}
    folder.mkdir(parents=True, exist_ok=False)
    for index, (record, encoded) in enumerate(prepared):
        destination = folder / f"image_{index:02d}.png"
        with destination.open("xb") as stream:
            stream.write(encoded)
        record["prepared"]["path"] = str(destination)
        manifest["images"].append(record)
    with (folder / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2); stream.write("\n")
    return manifest
