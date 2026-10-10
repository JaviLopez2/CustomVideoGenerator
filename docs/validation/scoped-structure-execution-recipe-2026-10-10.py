"""One frozen scoped-structure cohort per installed judge; no image generation."""
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
from scripts import scoped_structure_observations as observer
from scripts import paired_shape_preflight as checks
from scripts import observe_paired_shape as shared
from scripts import prepare_visual_regions as native

EXECUTION_PLAN = ROOT / "docs/validation/scoped-structure-execution-plan-2026-10-10.json"


def fingerprint(value):
    return hashlib.sha256(observer.canonical(value).encode()).hexdigest()


def verify():
    execution = json.loads(EXECUTION_PLAN.read_text(encoding="utf-8"))
    if checks.binding_path(execution["recipe"], ROOT) != Path(__file__).resolve():
        raise ValueError("Unexpected execution recipe")
    checks.checked_bytes(execution["recipe"], ROOT)
    plan = checks.checked_json(execution["probe_plan"], ROOT)
    for binding in plan["bindings"].values():
        checks.checked_bytes(binding, ROOT)
    checks.checked_bytes(plan["recipe"], ROOT)
    inventory = checks.checked_json(plan["inventory"], ROOT)
    manifest = checks.checked_json({"path": inventory["native_key_preparation"]["manifest_path"],
                                    "sha256": inventory["native_key_preparation"]["manifest_sha256"]}, ROOT)
    for row, retained in zip(inventory["native_key_preparation"]["plan"]["regions"], manifest["regions"], strict=True):
        record, encoded = native.render(row, 0)
        if encoded != checks.checked_bytes(retained["crop"], ROOT) or record["source"] != retained["source"]:
            raise ValueError("Native fullframe source reconstruction differs")
    recipe = ROOT / "docs/validation/profiled-camera-shape-recipe-2026-10-10.py"
    camera, assets, _ = runpy.run_path(str(recipe))["verify"](ROOT / "docs/validation/profiled-camera-shape-plan-2026-10-10.json")
    if plan["models"] != ["unsloth/Qwen3.5-9B-GGUF", "Qwen/Qwen3-VL-8B-Instruct-GGUF"] or plan["assets_manifest"] != camera["assets_manifest"]:
        raise ValueError("Unexpected judge assets")
    expected_budget = {"requests_per_model": 3, "maximum_requests_total": 6, "automatic_retries": 0, "generation_requests": 0,
                       "downloads": 0, "max_tokens": 512, "temperature": 0, "thinking": False, "http_timeout_seconds": 60,
                       "context": 8192, "min_image_tokens": 1024, "max_image_tokens": 1536, "port": 8092,
                       "owned_sequential_servers_only": True, "stop_each_cohort_at_first_invalid_or_unavailable": True}
    if plan["budget"] != expected_budget or execution["models"] != plan["models"]:
        raise ValueError("Changed fixed budget or candidates")
    if (len(plan["cases"]) != 3 or len(plan["request_bindings"]) != 3
            or [case["case_id"] for case in plan["cases"]] != plan["case_order"]):
        raise ValueError("Changed case order")
    for case, binding in zip(plan["cases"], plan["request_bindings"], strict=True):
        if (binding["case_id"] != case["case_id"] or fingerprint(case["scope"]) != binding["scope_sha256"]
                or fingerprint(observer.payload(case["reference"], case["candidate"], case["scope"])) != binding["request_sha256"]):
            raise ValueError("Changed scoped request")
    return execution, plan, assets


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--model-repo")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    execution_hash = shared.base.digest(EXECUTION_PLAN)
    execution, plan, assets = verify()
    if args.verify_only:
        print(json.dumps({"verified": True, "pairs": len(plan["cases"]), "model_requests": 0}))
        return
    if args.model_repo not in plan["models"]:
        raise ValueError("Choose one frozen judge")
    declared = execution["outputs"][args.model_repo]
    output, logs = [(ROOT / declared[key]).resolve() for key in ["report", "logs"]]
    if any(p == ROOT or not p.is_relative_to(ROOT) or p.exists() for p in (output, logs)):
        raise ValueError("Declared fresh outputs required; do not repeat cohort")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if head != execution["base_head"]:
        raise ValueError("Execution HEAD changed")
    resource_recipe = runpy.run_path(str(ROOT / "docs/validation/adjacent-cue-recipe-2026-10-09.py"))
    snapshot = resource_recipe["resources"]()
    if (any(snapshot["ports_open"].values()) or snapshot["ram_free_gib"] < 12
            or snapshot["gpu"]["used_mib"] > 5288 or snapshot["gpu"]["utilization_percent"] > 30):
        raise ValueError("Port/RAM/VRAM/GPU load prevents bounded queries")
    model = shared.select_model(assets, args.model_repo)
    target = ROOT / "local_image_stack/experiments/bridge/target"
    runtime_root = target / "visual-judge-runtime"
    runtime = shared.verify_runtime(runtime_root, assets["runtime"])
    weights = [target / "visual-judge-models" / model["repo"].split("/")[-1] / row["file"] for row in model["files"]]
    if any(shared.base.digest(path) != row["sha256"] for path, row in zip(weights, model["files"], strict=True)):
        raise ValueError("Judge/projector changed")
    logs.mkdir(parents=True, exist_ok=False)
    report = {"protocol": "scoped-structure-state-probe-result-1", "started_utc": datetime.now(timezone.utc).isoformat(),
              "execution_head": head, "execution_plan": {"path": str(EXECUTION_PLAN), "sha256": execution_hash},
              "probe_plan": execution["probe_plan"], "recipe": execution["recipe"], "observer": plan["observer"],
              "model": model, "runtime": runtime, "resource_preflight": snapshot, "rows": [],
              "http_model_requests_attempted": 0, "automatic_retries": 0, "generation_requests": 0, "downloads": 0,
              "admission_allowed": False, "physical_identity_established": False, "owned_server_closed": True}
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    def send(body):
        if shared.base.digest(EXECUTION_PLAN) != execution_hash:
            raise ValueError("Execution plan changed")
        verify()
        index = report["http_model_requests_attempted"]
        if index >= 3 or fingerprint(body) != plan["request_bindings"][index]["request_sha256"]:
            raise ValueError("Changed request or exhausted budget")
        report["http_model_requests_attempted"] += 1
        save()
        return shared.base.request("http://127.0.0.1:8092/v1/chat/completions", body, timeout=60)
    def done(row):
        report["rows"].append(row)
        save()
        print(json.dumps({key: row[key] for key in ["case_id", "transport_status", "prepare_seconds", "request_parse_seconds"]}), flush=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
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
        report["unattempted_cases"] = [case["case_id"] for case in plan["cases"][len(report["rows"]):]]
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == "__main__":
    main()
