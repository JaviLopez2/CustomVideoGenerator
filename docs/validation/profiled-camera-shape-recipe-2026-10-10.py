"""Source/ICC/alpha-bound camera diagnostic on retained full frames; no generation."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import paired_shape_preflight as checks
from scripts import prepare_profiled_visual_inputs as color
from scripts import prepare_visual_regions as native
from scripts import observe_paired_shape as shared
from scripts import paired_shape_observations as observer

RESOURCE_RECIPE = ROOT / "docs/validation/adjacent-cue-recipe-2026-10-09.py"
MODELS = ["unsloth/Qwen3.5-9B-GGUF", "Qwen/Qwen3-VL-8B-Instruct-GGUF"]
BUDGET = {"requests_per_model": 1, "maximum_requests_total": 2, "automatic_retries": 0,
          "generation_requests": 0, "downloads": 0, "photo_whole_object_requests": 0}


def fingerprint(value):
    return hashlib.sha256(checks.canonical(value).encode()).hexdigest()


def verify(plan_path):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    budget = plan.get("budget")
    if (plan.get("protocol") != "profiled-camera-shape-plan-1" or not isinstance(budget, dict)
            or set(budget) != set(BUDGET) or any(type(budget[k]) is not type(v) or budget[k] != v for k, v in BUDGET.items())
            or plan.get("comparison_candidates") != MODELS or plan.get("human_gold") is not False
            or plan.get("expected_major_shape_change") is not None):
        raise ValueError("Changed protocol, candidates, fixed budget or unadjudicated evidence")
    for field, path in (("recipe", Path(__file__)), ("color_helper", Path(color.__file__)),
                        ("native_helper", Path(native.__file__)), ("shared_runner", Path(shared.__file__)),
                        ("observer", Path(observer.__file__)), ("input_checks", Path(checks.__file__)),
                        ("resource_recipe", RESOURCE_RECIPE)):
        if checks.binding_path(plan[field], ROOT) != path.resolve():
            raise ValueError("Unknown implementation path")
        checks.checked_bytes(plan[field], ROOT)
    preparation = checks.checked_json(plan["color_preparation"], ROOT)
    result = checks.checked_json(plan["color_result"], ROOT)
    if (not checks.same_binding(preparation["helper"], plan["color_helper"], ROOT)
            or not checks.same_binding(result["plan"], plan["color_preparation"], ROOT)
            or not checks.same_binding(result["manifest"], plan["color_manifest"], ROOT)):
        raise ValueError("Color preparation/result/manifest chain differs")
    manifest = checks.checked_json(plan["color_manifest"], ROOT)
    if (manifest.get("protocol") != "profiled-visual-input-artifacts-1"
            or manifest.get("pillow_version") != color.pillow_version
            or manifest.get("littlecms_version") != color.ImageCms.core.littlecms_version
            or manifest.get("helper_sha256") != plan["color_helper"]["sha256"]
            or manifest.get("plan_canonical_sha256") != fingerprint(preparation["preparation"])
            or manifest.get("admission_allowed") is not False or manifest.get("physical_identity_established") is not False
            or type(manifest.get("model_requests")) is not int or manifest["model_requests"] != 0
            or type(manifest.get("generation_requests")) is not int or manifest["generation_requests"] != 0):
        raise ValueError("Changed color policy or runtime/authority")
    audit = checks.checked_json(preparation["source_audit"], ROOT)
    if not checks.same_binding(preparation["source_audit"], plan["source_audit"], ROOT):
        raise ValueError("Different Factory source audit")
    diagnostics = checks.checked_json(audit["bindings"]["diagnostics"], ROOT)
    artifacts = checks.checked_json(audit["bindings"]["artifact_manifest"], ROOT)
    checks.checked_bytes(audit["bindings"]["reference_manifest"], ROOT)
    items, records = preparation["preparation"]["images"], manifest["images"]
    if (len(items) != 4 or len(records) != 4 or result["prepared_images"] != records
            or [r["id"] for r in records] != ["camera_anchor", "camera_candidate", "print_root", "print_candidate"]):
        raise ValueError("Missing/reordered retained color inputs")
    by_id = {}
    coverage = []
    for item, record, audited in zip(items, records, audit["sources"]):
        expected, encoded = color.render(item)
        actual = {**record, "prepared": {k: v for k, v in record["prepared"].items() if k != "path"}}
        if checks.canonical(actual) != checks.canonical(expected) or record["source"] != audited["source"]:
            raise ValueError("Color/alpha claims differ from the actual Factory source")
        if checks.checked_bytes(record["prepared"], ROOT) != encoded:
            raise ValueError("Prepared image differs from explicit source reconstruction")
        source_entries = [a for a in artifacts if Path(a["path"]).resolve() == Path(item["source"]["path"]).resolve()]
        if len(source_entries) != 1 or source_entries[0]["sha256"] != item["source"]["sha256"]:
            raise ValueError("Source not bound to the Factory artifact manifest")
        image = {k: record["prepared"][k] for k in ("path", "sha256", "size")}
        full = [0, 0, *image["size"]]
        rectangle, same_png = native.render({"id": record["id"], "source": image, "box": full, "required_box": full}, 0)
        if (rectangle["coverage_relation"] != "contained" or same_png != encoded
                or rectangle["resize_or_color_transform"] is not False):
            raise ValueError("Prepared full frame is not an exact native input")
        coverage.append({"id": record["id"], "source_sha256": item["source"]["sha256"],
                         "prepared_sha256": image["sha256"], "fullframe_rectangle_relation": "contained",
                         "prepared_pixels_exact": True, "original_rgb_samples_unchanged": record["rgb_samples_unchanged"],
                         "semantic_whole_object_coverage": "not_established_by_rectangle"})
        by_id[record["id"]] = image
    # Re-derive the recorded source selection. selected_index is a candidate identifier, not a list offset.
    for number, candidate, reference_ids in ((3, "camera_candidate", ["camera_anchor"]),
                                             (9, "print_candidate", ["print_root", "camera_anchor"])):
        scene = next(s for s in diagnostics["scenes"] if s["scene"] == number)
        selected = [c for c in scene["candidates"] if c["index"] == scene["selected_index"]]
        source_by_id = {r["id"]: r["source"] for r in records}
        if (len(selected) != 1 or selected[0]["original_file"] != Path(source_by_id[candidate]["path"]).name
                or scene["selected_original_file"] != selected[0]["original_file"]
                or [r["local_file"] for r in scene["reference"]["reference_pack"]]
                   != [Path(source_by_id[r]["path"]).name for r in reference_ids]):
            raise ValueError("Selected Factory candidate or ordered pack differs")
    expected_case = {"case_id": "retained_camera_body_pair", "reference": by_id["camera_anchor"],
                     "candidate": by_id["camera_candidate"]}
    if (plan.get("cases") != [expected_case] or plan.get("subject") != "instant camera"
            or plan.get("model_prompt") != observer.prompt("instant camera") or plan.get("response_schema") != observer.schema()
            or plan.get("request_sha256") != fingerprint(observer.payload(expected_case["reference"], expected_case["candidate"], "instant camera"))
            or plan.get("excluded_photo") != {"reference_id": "print_root", "candidate_id": "print_candidate",
               "reason": "candidate_right_border_clipped_assistant_inspection", "human_gold": False,
               "whole_object_comparison_eligible": False, "model_requests": 0}):
        raise ValueError("Requested context/prompt or conservative photo exclusion differs")
    assets = checks.checked_json(plan["assets_manifest"], ROOT)
    return plan, assets, {"protocol": "profiled-camera-transitive-preflight-1", "images": coverage,
                          "source_selection_rederived": True, "historic_http_capture_claimed": False,
                          "original_pixel_identity_claimed_for_transformed_inputs": False,
                          "human_gold": False, "physical_identity_established": False, "admission_allowed": False}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--verify-only", action="store_true")
    for name in ("model-repo", "output", "log-dir"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    plan_path = Path(args.plan).resolve()
    plan, assets, input_preflight = verify(plan_path)
    if args.verify_only:
        print(json.dumps({"verified": True, "model_requests": 0, "input_preflight": input_preflight}))
        return
    if args.model_repo not in MODELS or not args.output or not args.log_dir:
        raise ValueError("Declare one pinned model and fresh outputs")
    output, logs = Path(args.output).resolve(), Path(args.log_dir).resolve()
    declared = plan["outputs"][args.model_repo]
    if (output != (ROOT / declared["report"]).resolve() or logs != (ROOT / declared["logs"]).resolve()
            or any(p == ROOT or not p.is_relative_to(ROOT) or p.exists() for p in (output, logs))):
        raise ValueError("Only the declared fresh outputs are eligible; no repeats")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if head != plan["execution_base_head"]:
        raise ValueError("Execution HEAD changed")
    snapshot = runpy.run_path(str(RESOURCE_RECIPE))["resources"]()
    if (any(snapshot["ports_open"].values()) or snapshot["ram_free_gib"] < 12
            or snapshot["gpu"]["used_mib"] > 5288 or snapshot["gpu"]["utilization_percent"] > 30):
        raise ValueError("Port/RAM/VRAM/GPU-load preflight prevents this bounded query")
    model = shared.select_model(assets, args.model_repo)
    target = ROOT / "local_image_stack/experiments/bridge/target"
    runtime_root = target / "visual-judge-runtime"
    runtime = shared.verify_runtime(runtime_root, assets["runtime"])
    weights = [target / "visual-judge-models" / model["repo"].split("/")[-1] / r["file"] for r in model["files"]]
    if any(shared.base.digest(p) != r["sha256"] for p, r in zip(weights, model["files"])):
        raise ValueError("Model/projector bytes differ")
    logs.mkdir(parents=True, exist_ok=False)
    report = {"protocol": "profiled-camera-shape-result-1", "execution_head": head,
              "plan": {"path": str(plan_path), "sha256": shared.base.digest(plan_path)}, "recipe": plan["recipe"],
              "observer_version": observer.VERSION, "model": model, "runtime": runtime,
              "input_preflight": input_preflight, "resource_preflight": snapshot, "rows": [],
              "http_model_requests_attempted": 0, "automatic_retries": 0, "generation_requests": 0,
              "downloads": 0, "excluded_photo_requests": 0, "human_gold": False,
              "admission_allowed": False, "physical_identity_established": False, "owned_server_closed": True}
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    def send(body):
        if shared.base.digest(plan_path) != report["plan"]["sha256"]:
            raise ValueError("Plan changed during execution")
        verify(plan_path)
        if report["http_model_requests_attempted"] >= 1 or fingerprint(body) != plan["request_sha256"]:
            raise ValueError("Changed request or exhausted fixed budget")
        report["http_model_requests_attempted"] += 1; save()
        return shared.base.request("http://127.0.0.1:8092/v1/chat/completions", body, timeout=60)
    def done(row):
        report["rows"].append(row); save()
        print(json.dumps({k: row[k] for k in ("case_id", "transport_status", "seconds")}), flush=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write("\n")
    try:
        with shared.owned_server(shared.command(runtime_root / assets["runtime"]["tag"] / "llama-server.exe", weights),
                                 logs / "server.log", shared.base.request, subprocess.Popen, report):
            save(); observer.collect(plan["cases"], plan["subject"], send, done)
    except (OSError, ValueError, RuntimeError) as exc:
        report["runtime_error_type"] = type(exc).__name__
    finally:
        with socket.socket() as connection:
            connection.settimeout(1)
            report["port_8092_open_after"] = connection.connect_ex(("127.0.0.1", 8092)) == 0
        report["unattempted_cases"] = [r["case_id"] for r in plan["cases"][len(report["rows"]):]]
        save()


if __name__ == "__main__":
    main()
