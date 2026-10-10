"""Fixed native ROI contrast on the retained fused key; never generates images."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import prepare_visual_regions as native
from scripts import scoped_structure_observations as observer
from scripts import paired_shape_preflight as checks
from scripts import observe_paired_shape as shared

BASE = "3579f6531cddbb7163bbc7e932a773d0440c5c41"
PLAN = ROOT / "docs/validation/scoped-fusion-roi-plan-2026-10-11.json"
RESULT = ROOT / "docs/validation/scoped-fusion-roi-preparation-2026-10-11.json"
FOLDER = ROOT / "local_image_stack/experiments/bridge/target/scoped-fusion-roi-2026-10-11"
BOX = [430, 530, 720, 970]
MARGIN = 8
BUDGET = {"requests_per_model": 2, "maximum_requests_total": 4, "automatic_retries": 0,
          "generation_requests": 0, "downloads": 0, "max_tokens": 512, "temperature": 0,
          "thinking": False, "context": 8192, "min_image_tokens": 1024,
          "max_image_tokens": 1536, "http_timeout_seconds": 60, "port": 8092}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(observer.canonical(value).encode()).hexdigest()


def binding(path):
    return {"path": str(path), "sha256": sha(path)}


def save_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parent():
    recipe = ROOT / "docs/validation/scoped-structure-execution-recipe-2026-10-10.py"
    return runpy.run_path(str(recipe))["verify"]()


def prepare():
    if any(p.exists() for p in [PLAN, RESULT, FOLDER]):
        raise ValueError("Preserve existing preparation")
    execution, old, assets = parent()
    source = next(c for c in old["cases"] if c["case_id"] == "human_reported_key_fusion")
    preparation = {"protocol": "visual-region-preparation-plan-1", "margin_pixels": MARGIN,
                   "regions": [{"id": role, "source": source[role], "box": BOX,
                                "required_box": BOX} for role in ["reference", "candidate"]]}
    manifest = native.prepare(preparation, FOLDER, workspace_root=ROOT)
    images = {r["id"]: {key: r["crop"][key] for key in ["path", "sha256", "size"]} for r in manifest["regions"]}
    cases = [{"case_id": "identical_key_roi_control", "reference": images["reference"], "candidate": images["reference"], "scope": source["scope"]},
             {"case_id": "fused_key_roi", "reference": images["reference"], "candidate": images["candidate"], "scope": source["scope"]}]
    pin_names = ["docs/validation/scoped-structure-execution-recipe-2026-10-10.py",
                 "docs/validation/scoped-structure-execution-plan-2026-10-10.json",
                 "docs/validation/scoped-structure-plan-2026-10-10.json",
                 "docs/validation/scoped-structure-qwen35-2026-10-10.json",
                 "docs/validation/scoped-structure-qwen3vl-2026-10-10.json",
                 "docs/validation/clock-visible-count-human-review-2026-10-10.json",
                 "scripts/scoped_structure_observations.py", "scripts/prepare_visual_regions.py",
                 "scripts/observe_paired_shape.py", "docs/validation/adjacent-cue-recipe-2026-10-09.py"]
    value = {"protocol": "scoped-fusion-roi-plan-1", "declared_utc": datetime.now(timezone.utc).isoformat(),
             "base_head": BASE, "budget": BUDGET, "models": old["models"], "cases": cases,
             "recipe": binding(Path(__file__).resolve()), "pins": {n: binding(ROOT / n) for n in pin_names},
             "source_pair": source, "preparation": preparation, "manifest": binding(FOLDER / "manifest.json"),
             "response_schema": observer.schema(), "request_bindings": [{"case_id": c["case_id"],
               "scope_sha256": fingerprint(c["scope"]), "request_sha256": fingerprint(observer.payload(c["reference"], c["candidate"], c["scope"]))} for c in cases],
             "offline_expected": {"identical_key_roi_control": "not_observed", "fused_key_roi": "human fullframe reports fusion; crop coverage reviewed only by assistant"},
             "coverage_provenance": "Assistant inspected the original fullframes before ROI inference; same source box and margin includes rod ends, bit ends and shared head. Rectangle alone is not physical coverage gold.",
             "limitations": ["Selected after fullframe failures, exploratory, no held-out accuracy or independent crop review.",
                             "Same pixels/scope/prompt/schema/decoding; context and effective resolution change together.",
                             "No labels, boxes, expected counts or fusion description sent to the judge; no new human labels.",
                             "Closed fullframe cohort not repeated or rewritten; no retries or production authority."],
             "outputs": {repo: {"report": "docs/validation/scoped-fusion-roi-" + key + "-2026-10-11.json",
                                "logs": "local_image_stack/experiments/bridge/target/scoped-fusion-roi-" + key + "-2026-10-11"}
                         for repo, key in zip(old["models"], ["qwen35", "qwen3vl"], strict=True)}}
    save_new(PLAN, value)
    verify()
    save_new(RESULT, {"protocol": "scoped-fusion-roi-preparation-1", "checked_utc": datetime.now(timezone.utc).isoformat(),
                      "plan": binding(PLAN), "manifest": value["manifest"], "effective_boxes": [r["effective_box"] for r in manifest["regions"]],
                      "native_pixel_subsets_reconstructed": True, "resize_or_color_transform": False,
                      "independent_human_crop_review": False, "model_requests": 0, "generations": 0})
    print(json.dumps({"prepared": True, "pairs": 2, "size": images["reference"]["size"], "model_requests": 0}))


def verify():
    value = json.loads(PLAN.read_text(encoding="utf-8"))
    checks.checked_bytes(value["recipe"], ROOT)
    for pin in value["pins"].values():
        checks.checked_bytes(pin, ROOT)
    execution, old, assets = parent()
    source = next(c for c in old["cases"] if c["case_id"] == "human_reported_key_fusion")
    if value["source_pair"] != source or value["budget"] != BUDGET or value["models"] != old["models"]:
        raise ValueError("Changed source, candidates or fixed budget")
    expected = {"protocol": "visual-region-preparation-plan-1", "margin_pixels": MARGIN,
                "regions": [{"id": role, "source": source[role], "box": BOX, "required_box": BOX} for role in ["reference", "candidate"]]}
    if value["preparation"] != expected or value["response_schema"] != observer.schema():
        raise ValueError("Changed boxes, margin or schema")
    manifest = checks.checked_json(value["manifest"], ROOT)
    if len(manifest["regions"]) != 2:
        raise ValueError("Missing source regions")
    images = {}
    for item, kept in zip(expected["regions"], manifest["regions"], strict=True):
        record, encoded = native.render(item, MARGIN)
        if encoded != checks.checked_bytes(kept["crop"], ROOT) or record["effective_box"] != kept["effective_box"]:
            raise ValueError("ROI pixels or coverage box changed")
        images[item["id"]] = {key: kept["crop"][key] for key in ["path", "sha256", "size"]}
    cases = [{"case_id": "identical_key_roi_control", "reference": images["reference"], "candidate": images["reference"], "scope": source["scope"]},
             {"case_id": "fused_key_roi", "reference": images["reference"], "candidate": images["candidate"], "scope": source["scope"]}]
    if value["cases"] != cases or len(value["request_bindings"]) != 2:
        raise ValueError("Changed pair roles/order/scope")
    for case, kept in zip(cases, value["request_bindings"], strict=True):
        if (kept["case_id"] != case["case_id"] or kept["scope_sha256"] != fingerprint(case["scope"])
                or kept["request_sha256"] != fingerprint(observer.payload(case["reference"], case["candidate"], case["scope"]))):
            raise ValueError("Changed request")
    return value, assets


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--model-repo")
    args = parser.parse_args()
    if args.prepare:
        prepare()
        return
    plan_hash = sha(PLAN)
    plan, assets = verify()
    if args.verify_only:
        print(json.dumps({"verified": True, "pairs": 2, "model_requests": 0}))
        return
    if args.model_repo not in plan["models"]:
        raise ValueError("Choose a declared installed judge")
    paths = plan["outputs"][args.model_repo]
    output, logs = [(ROOT / paths[key]).resolve() for key in ["report", "logs"]]
    if any(p == ROOT or not p.is_relative_to(ROOT) or p.exists() for p in [output, logs]):
        raise ValueError("Only fresh declared outputs; never repeat cohort")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if head != BASE:
        raise ValueError("Execution HEAD changed")
    snapshot = runpy.run_path(str(ROOT / "docs/validation/adjacent-cue-recipe-2026-10-09.py"))["resources"]()
    if (any(snapshot["ports_open"].values()) or snapshot["ram_free_gib"] < 12
            or snapshot["gpu"]["used_mib"] > 5288 or snapshot["gpu"]["utilization_percent"] > 30):
        raise ValueError("Resource/port preflight prevents bounded queries")
    model = shared.select_model(assets, args.model_repo)
    target = ROOT / "local_image_stack/experiments/bridge/target"
    runtime_root = target / "visual-judge-runtime"
    runtime = shared.verify_runtime(runtime_root, assets["runtime"])
    weights = [target / "visual-judge-models" / model["repo"].split("/")[-1] / r["file"] for r in model["files"]]
    if any(sha(path) != row["sha256"] for path, row in zip(weights, model["files"], strict=True)):
        raise ValueError("Judge/projector changed")
    logs.mkdir(parents=True, exist_ok=False)
    report = {"protocol": "scoped-fusion-roi-result-1", "started_utc": datetime.now(timezone.utc).isoformat(),
              "execution_head": head, "plan": binding(PLAN), "recipe": plan["recipe"], "model": model,
              "runtime": runtime, "resource_preflight": snapshot, "rows": [], "http_model_requests_attempted": 0,
              "automatic_retries": 0, "generations": 0, "downloads": 0, "admission_allowed": False, "owned_server_closed": True}
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    def send(body):
        if sha(PLAN) != plan_hash:
            raise ValueError("ROI plan changed")
        verify()
        i = report["http_model_requests_attempted"]
        if i >= 2 or fingerprint(body) != plan["request_bindings"][i]["request_sha256"]:
            raise ValueError("Changed request or exhausted budget")
        report["http_model_requests_attempted"] += 1
        save()
        return shared.base.request("http://127.0.0.1:8092/v1/chat/completions", body, timeout=60)
    def done(row):
        report["rows"].append(row)
        save()
        print(json.dumps({key: row[key] for key in ["case_id", "transport_status", "prepare_seconds", "request_parse_seconds"]}), flush=True)
    save_new(output, report)
    try:
        with shared.owned_server(shared.command(runtime_root / assets["runtime"]["tag"] / "llama-server.exe", weights),
                                 logs / "server.log", shared.base.request, subprocess.Popen, report):
            save()
            observer.collect(plan["cases"], send, done)
    except (OSError, ValueError, RuntimeError) as exc:
        report["runtime_error_type"] = type(exc).__name__
    finally:
        with socket.socket() as connection:
            connection.settimeout(1)
            report["port_8092_open_after"] = connection.connect_ex(("127.0.0.1", 8092)) == 0
        report["unattempted_cases"] = [c["case_id"] for c in plan["cases"][len(report["rows"]):]]
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == "__main__":
    main()
