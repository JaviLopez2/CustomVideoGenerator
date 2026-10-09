"""Offline, provenance-bound PNG regions; no model or admission authority."""
import hashlib
import io
import json
from pathlib import Path
import re

from PIL import Image, __version__ as pillow_version


def box(value, size):
    if (not isinstance(value, list) or len(value) != 4 or
            any(type(n) is not int for n in value) or
            not (0 <= value[0] < value[2] <= size[0] and 0 <= value[1] < value[3] <= size[1])):
        raise ValueError("Invalid source-coordinate box")
    return list(value)


def render(row, margin):
    if not isinstance(row, dict) or not {"id", "source", "box"} <= row.keys() or row.keys() - {"id", "source", "box", "required_box"}:
        raise ValueError("Invalid region record")
    if not isinstance(row["id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", row["id"]):
        raise ValueError("Invalid region identifier")
    src = row["source"]
    if not isinstance(src, dict) or set(src) != {"path", "sha256", "size"}:
        raise ValueError("Invalid source descriptor")
    if not isinstance(src["path"], str) or not src["path"] or not isinstance(src["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", src["sha256"]):
        raise ValueError("Invalid source path/hash")
    size = src["size"]
    if not isinstance(size, list) or len(size) != 2 or any(type(n) is not int or n <= 0 for n in size):
        raise ValueError("Invalid source dimensions")
    requested = box(row["box"], size)
    required = box(row["required_box"], size) if "required_box" in row else None
    raw = Path(src["path"]).read_bytes()  # One snapshot for hash and decoding.
    if hashlib.sha256(raw).hexdigest() != src["sha256"]:
        raise ValueError("Source bytes changed")
    with Image.open(io.BytesIO(raw)) as image:
        if image.format != "PNG" or image.mode not in {"RGB", "RGBA"} or list(image.size) != size:
            raise ValueError("Expected pinned RGB/RGBA PNG and dimensions")
        if image.info.get("icc_profile") or image.getexif().get(274) not in {None, 1}:
            raise ValueError("Unsupported profile/orientation; do not silently transform")
        if "transparency" in image.info:
            raise ValueError("Unsupported PNG transparency metadata; do not silently drop alpha")
        image.load()
        expanded = [requested[0] - margin, requested[1] - margin, requested[2] + margin, requested[3] + margin]
        effective = [max(0, expanded[0]), max(0, expanded[1]), min(size[0], expanded[2]), min(size[1], expanded[3])]
        crop = image.crop(effective)
        pixels = crop.tobytes()
        crop.info.clear()  # Never copy prompt/workflow/private text metadata.
        buffer = io.BytesIO()
        crop.save(buffer, format="PNG")
        encoded = buffer.getvalue()
        with Image.open(io.BytesIO(encoded)) as decoded:
            assert decoded.mode == image.mode and decoded.size == crop.size and decoded.tobytes() == pixels
        mode = image.mode
        dimensions = list(crop.size)
    relation = "not_declared"
    if required is not None:
        if effective[0] <= required[0] and effective[1] <= required[1] and effective[2] >= required[2] and effective[3] >= required[3]:
            relation = "contained"
        elif max(effective[0], required[0]) < min(effective[2], required[2]) and max(effective[1], required[1]) < min(effective[3], required[3]):
            relation = "partial"
        else:
            relation = "disjoint"
    result = {"id": row["id"], "source": {**src, "size": list(size)}, "source_mode": mode,
              "requested_box": requested, "effective_box": effective, "margin_pixels": margin,
              "margin_clipped": expanded != effective, "required_box": required,
              "coverage_relation": relation, "whole_declared_region_eligible": relation == "contained",
              "semantic_coverage_review": "pending", "pixel_subset_verified": True,
              "resize_or_color_transform": False, "ancillary_metadata_copied": False,
              "crop": {"sha256": hashlib.sha256(encoded).hexdigest(), "size": dimensions, "mode": mode}}
    return result, encoded


def prepare(plan, output_dir, *, workspace_root):
    if not isinstance(plan, dict) or set(plan) != {"protocol", "margin_pixels", "regions"} or plan["protocol"] != "visual-region-preparation-plan-1":
        raise ValueError("Unknown or ambiguous preparation plan")
    margin, items = plan["margin_pixels"], plan["regions"]
    if type(margin) is not int or not 0 <= margin <= 4096 or not isinstance(items, list) or not 1 <= len(items) <= 16:
        raise ValueError("Invalid margin or region budget")
    root, folder = Path(workspace_root).resolve(), Path(output_dir).resolve()
    if not root.is_dir() or not folder.is_relative_to(root) or folder == root:
        raise ValueError("Output escapes supplied workspace")
    if folder.exists():
        raise FileExistsError("Preserve existing region artifacts")
    # Complete all byte/coordinate checks before creating any output directory.
    prepared = [render(row, margin) for row in items]
    ids = [result["id"] for result, _ in prepared]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate region identifiers")
    manifest = {"protocol": "visual-region-artifacts-1", "pillow_version": pillow_version,
                "plan_canonical_sha256": hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False,
                                                                     separators=(",", ":")).encode()).hexdigest(),
                "admission_allowed": False, "physical_identity_established": False,
                "generation_or_model_requests": 0, "regions": []}
    folder.mkdir(parents=True, exist_ok=False)
    for i, (record, encoded) in enumerate(prepared):
        destination = folder / f"image_{i:02d}.png"
        with destination.open("xb") as stream:
            stream.write(encoded)
        record["crop"]["path"] = str(destination)
        manifest["regions"].append(record)
    with (folder / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return manifest
