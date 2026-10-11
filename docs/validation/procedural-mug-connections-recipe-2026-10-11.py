"""CPU-only construction controls; no real-image gold or model execution."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, __version__ as pillow_version
from scipy import __version__ as scipy_version
from scipy.ndimage import label

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import scoped_structure_observations as observer

PLAN = ROOT / "docs/validation/procedural-mug-connections-plan-2026-10-11.json"
RESULT = ROOT / "docs/validation/procedural-mug-connections-preparation-2026-10-11.json"
FOLDER = ROOT / "local_image_stack/experiments/bridge/target/procedural-mug-connections-2026-10-11"
BASE = "76acc31257a5e915e7f6cf118ed203cb53ff7c5b"
SCOPE = {"subject": "ceramic mug", "protected_structure": "The mug body, handle, and their permanent physical connections.",
         "allowed_state_changes": ["visible vapor above the mug rim"]}
VARIANTS = ["intact", "intact_vapor", "lower_connection_gap_vapor"]
MODELS = ["unsloth/Qwen3.5-9B-GGUF", "Qwen/Qwen3-VL-8B-Instruct-GGUF"]
PIN_NAMES = ["scripts/scoped_structure_observations.py", "scripts/paired_shape_observations.py",
             "scripts/observe_paired_shape.py", "docs/validation/camera-print-human-review-2026-10-11.json",
             "docs/validation/scoped-fusion-roi-qwen35-2026-10-11.json",
             "docs/validation/scoped-fusion-roi-qwen3vl-2026-10-11.json"]
FUTURE_BUDGET = {"requests_per_model": 3, "maximum_requests_total": 6,
                 "automatic_retries": 0, "max_tokens": 512, "temperature": 0,
                 "thinking": False, "context": 8192, "min_image_tokens": 1024,
                 "max_image_tokens": 1536, "http_timeout_seconds": 60, "port": 8092,
                 "generation_requests": 0, "downloads": 0}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def binding(path):
    return {"path": str(path), "sha256": sha(path)}


def fingerprint(value):
    return hashlib.sha256(observer.canonical(value).encode()).hexdigest()


def save_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def render(variant):
    if variant not in VARIANTS:
        raise ValueError("Unknown declared construction")
    canvas = Image.new("RGB", (512, 512), "white")
    handle = Image.new("L", canvas.size, 0)
    draw = ImageDraw.Draw(handle)
    points = [(330, 290), (397, 290), (440, 318), (455, 352), (440, 389), (397, 420), (330, 420)]
    draw.line(points, fill=255, width=22, joint="curve")
    for x, y in points:
        draw.ellipse((x - 11, y - 11, x + 11, y + 11), fill=255)
    if variant == "lower_connection_gap_vapor":
        # Remove only the lower terminal segment; the upper connection remains.
        draw.rectangle((322, 402, 384, 438), fill=0)
    canvas.paste((95, 102, 114), mask=handle)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((130, 250, 340, 465), radius=20, fill=(221, 225, 232), outline=(70, 78, 92), width=3)
    draw.ellipse((130, 240, 340, 272), fill=(198, 204, 215), outline=(70, 78, 92), width=3)
    if variant != "intact":
        for x in (185, 235, 285):
            draw.line([(x, 208), (x - 8, 182), (x + 8, 154), (x - 8, 126), (x, 96)], fill=(154, 164, 178), width=7, joint="curve")
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def pixels(encoded):
    with Image.open(io.BytesIO(encoded)) as image:
        image.load()
        if image.mode != "RGB" or image.size != (512, 512) or image.info:
            raise ValueError("Expected metadata-free native RGB fixture")
        return np.asarray(image).copy()


def connected_at(array, box, first, second):
    x0, y0, x1, y1 = box
    foreground = np.any(array[y0:y1, x0:x1] != 255, axis=2)
    components, _ = label(foreground, structure=np.ones((3, 3), dtype=np.uint8))
    a, b = [int(components[y - y0, x - x0]) for x, y in (first, second)]
    if a <= 0 or b <= 0:
        raise ValueError("Both connection probe endpoints must be visible foreground")
    return a == b


def pixel_proof(encoded):
    frames = [pixels(blob) for blob in encoded]
    top = [connected_at(frame, (328, 278, 409, 308), (335, 290), (397, 290)) for frame in frames]
    lower = [connected_at(frame, (328, 408, 409, 434), (335, 420), (397, 420)) for frame in frames]
    vapor = [bool(np.any(frame[:220] != 255)) for frame in frames]
    body_equal = all(np.array_equal(frames[0][240:466, 130:341], frame[240:466, 130:341]) for frame in frames[1:])
    vapor_equal = np.array_equal(frames[1][:220], frames[2][:220])
    difference = np.any(frames[1] != frames[2], axis=2)
    y, x = np.where(difference)
    changed_box = [int(x.min()), int(y.min()), int(x.max()) + 1, int(y.max()) + 1]
    if top != [True, True, True] or lower != [True, True, False] or vapor != [False, True, True]:
        raise ValueError("Construction did not produce declared visible controls")
    if not body_equal or not vapor_equal or not (341 <= changed_box[0] < changed_box[2] <= 385 and 402 <= changed_box[1] < changed_box[3] <= 439):
        raise ValueError("Defect changed protected body or allowed-state pixels")
    return {"measurement": "8-connected foreground paths in fixed local windows, derived from actual RGB pixels",
            "top_connection": top, "lower_connection": lower, "visible_vapor": vapor,
            "body_pixel_region_equal": body_equal, "vapor_pixels_equal_for_defect_pair": vapor_equal,
            "defect_changed_box": changed_box, "defect_changed_pixels": int(difference.sum()),
            "meaning": "Construction proof for these diagrams only; not a physical truth detector for photographs"}


def cases(images):
    return [{"case_id": "identical_procedural_mug", "reference": images[0], "candidate": images[0], "scope": SCOPE},
            {"case_id": "allowed_vapor_only", "reference": images[0], "candidate": images[1], "scope": SCOPE},
            {"case_id": "connection_gap_same_vapor", "reference": images[1], "candidate": images[2], "scope": SCOPE}]


def expected():
    return [{"case_id": "identical_procedural_mug", "structure": "not_observed", "connections": "not_observed", "state": "not_observed"},
            {"case_id": "allowed_vapor_only", "structure": "not_observed", "connections": "not_observed", "state": "observed"},
            {"case_id": "connection_gap_same_vapor", "structure": "observed", "connections": "observed", "state": "not_observed"}]


def prepare():
    if any(path.exists() for path in [PLAN, RESULT, FOLDER]):
        raise ValueError("Preserve previous construction and preparation")
    encoded = [render(variant) for variant in VARIANTS]
    proof = pixel_proof(encoded)  # No output created unless the visible invariants hold.
    images = [{"path": str(FOLDER / f"image_{index:02d}.png"),
               "sha256": hashlib.sha256(blob).hexdigest(), "size": [512, 512]} for index, blob in enumerate(encoded)]
    pairs = cases(images)
    FOLDER.mkdir(parents=True, exist_ok=False)
    for image, blob in zip(images, encoded, strict=True):
        with Path(image["path"]).open("xb") as handle:
            handle.write(blob)
    requests = [{"case_id": case["case_id"], "scope_sha256": fingerprint(case["scope"]),
                 "request_sha256": fingerprint(observer.payload(case["reference"], case["candidate"], case["scope"]))} for case in pairs]
    plan = {"protocol": "procedural-mug-connections-plan-1", "declared_utc": datetime.now(timezone.utc).isoformat(),
            "base_head": BASE, "stage": "prepared_cpu_not_executed", "models": MODELS,
            "future_request_budget": FUTURE_BUDGET, "current_model_requests": 0, "recipe": binding(Path(__file__).resolve()),
            "pins": {name: binding(ROOT / name) for name in PIN_NAMES},
            "render_environment": {"pillow": pillow_version, "numpy": np.__version__, "scipy": scipy_version},
            "images": images, "variants": VARIANTS, "cases": pairs, "request_bindings": requests,
            "response_schema": observer.schema(), "pixel_proof": proof,
            "offline_expected": expected(),
            "limitations": ["Labels by construction, not human-adjudicated real images, natural-image accuracy or identity approval.",
                            "One procedural family and one declared defect; selected after prior failures, not held-out validation.",
                            "Subject/parts/state scope names no expected outcome, coordinates or lower-connection defect.",
                            "Synthetic steam is a visible-state symbol, not evidence of physical temperature.",
                            "No model execution in this recipe; future execution must separately verify resources, weights, own-process lifecycle and immutable requests."],
            "admission_allowed": False, "physical_identity_established": False}
    save_new(PLAN, plan)
    verify()
    save_new(RESULT, {"protocol": "procedural-mug-connections-preparation-1", "checked_utc": datetime.now(timezone.utc).isoformat(),
                      "plan": binding(PLAN), "pixel_proof": proof, "images_reconstructed_exactly": 3,
                      "requests_prepared": 3, "model_requests": 0, "generations": 0, "human_gold": False})
    print(json.dumps({"prepared": True, "images": 3, "pairs": 3, "model_requests": 0, "proof": proof}))


def verify():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if (plan["protocol"] != "procedural-mug-connections-plan-1" or plan["base_head"] != BASE
            or plan["recipe"]["path"] != str(Path(__file__).resolve()) or set(plan["pins"]) != set(PIN_NAMES)
            or any(plan["pins"][name]["path"] != str(ROOT / name) for name in PIN_NAMES)
            or plan["render_environment"] != {"pillow": pillow_version, "numpy": np.__version__, "scipy": scipy_version}
            or plan["offline_expected"] != expected() or plan["stage"] != "prepared_cpu_not_executed"
            or type(plan["current_model_requests"]) is not int or plan["current_model_requests"] != 0
            or plan["admission_allowed"] is not False or plan["physical_identity_established"] is not False):
        raise ValueError("Changed provenance, construction labels, preparation stage or authority")
    for item in [plan["recipe"], *plan["pins"].values()]:
        if sha(item["path"]) != item["sha256"]:
            raise ValueError("Changed bound source")
    if fingerprint(plan["future_request_budget"]) != fingerprint(FUTURE_BUDGET) or plan["models"] != MODELS or plan["variants"] != VARIANTS:
        raise ValueError("Changed fixed candidates, budget or construction")
    encoded = [render(variant) for variant in VARIANTS]
    expected_images = [{"path": str(FOLDER / f"image_{index:02d}.png"), "sha256": hashlib.sha256(blob).hexdigest(), "size": [512, 512]}
                       for index, blob in enumerate(encoded)]
    if plan["images"] != expected_images or plan["cases"] != cases(expected_images) or plan["response_schema"] != observer.schema():
        raise ValueError("Changed fixture bytes, roles, scope or schema")
    for image, blob in zip(expected_images, encoded, strict=True):
        if Path(image["path"]).read_bytes() != blob:
            raise ValueError("Changed prepared PNG")
    if pixel_proof(encoded) != plan["pixel_proof"]:
        raise ValueError("Changed actual pixel proof")
    expected_requests = [{"case_id": c["case_id"], "scope_sha256": fingerprint(c["scope"]),
                          "request_sha256": fingerprint(observer.payload(c["reference"], c["candidate"], c["scope"]))} for c in plan["cases"]]
    if plan["request_bindings"] != expected_requests:
        raise ValueError("Changed request")
    return plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.prepare == args.verify_only:
        parser.error("Choose exactly one CPU operation")
    if args.prepare:
        prepare()
    else:
        verify()
        print(json.dumps({"verified": True, "pairs": 3, "model_requests": 0}))
