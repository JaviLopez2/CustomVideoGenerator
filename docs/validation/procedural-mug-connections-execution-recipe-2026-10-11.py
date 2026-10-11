"""One fixed cohort per installed judge; no generation, retry or admission."""
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

BASE = "66d019b91884909be909eb40cbb548386af8527c"
PLAN = ROOT / "docs/validation/procedural-mug-connections-execution-plan-2026-10-11.json"
PREPARE_RECIPE = ROOT / "docs/validation/procedural-mug-connections-recipe-v2-2026-10-11.py"
SOURCE = ROOT / "docs/validation/procedural-mug-connections-plan-v2-2026-10-11.json"
RESULT = ROOT / "docs/validation/procedural-mug-connections-preparation-v2-2026-10-11.json"
ASSETS = {"path": "docs/validation/visual-judge-candidates-assets-2026-10-08.json",
          "sha256": "b8cd3dc4b4703ceab84449bff34c502ea414eeb7e2b17d7e1a39b5313cbc9391"}
RESOURCE_RECIPE = ROOT / "docs/validation/adjacent-cue-recipe-2026-10-09.py"
PIN_NAMES = ["scripts/scoped_structure_observations.py", "scripts/paired_shape_observations.py",
             "scripts/observe_paired_shape.py", "scripts/paired_shape_preflight.py",
             "scripts/evaluate_multimodal_judges.py", "scripts/observe_visual_geometry.py",
             "docs/validation/adjacent-cue-recipe-2026-10-09.py"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def binding(path):
    return {"path": str(path), "sha256": sha(path)}


def fingerprint(value):
    return hashlib.sha256(observer.canonical(value).encode()).hexdigest()


def outputs(models):
    return {repo: {"report": f"docs/validation/procedural-mug-connections-{name}-2026-10-11.json",
                   "logs": f"local_image_stack/experiments/bridge/target/procedural-mug-connections-{name}-2026-10-11"}
            for repo, name in zip(models, ["qwen35", "qwen3vl"], strict=True)}


def declare():
    if PLAN.exists():
        raise ValueError("Preserve existing execution declaration")
    prepared = runpy.run_path(str(PREPARE_RECIPE))["verify"]()
    checks.checked_json(ASSETS, ROOT)
    value = {"protocol": "procedural-mug-connections-execution-plan-1",
             "declared_utc": datetime.now(timezone.utc).isoformat(), "base_head": BASE,
             "source": binding(SOURCE), "preparation": binding(RESULT), "prepare_recipe": binding(PREPARE_RECIPE),
             "recipe": binding(Path(__file__).resolve()), "assets": ASSETS,
             "pins": {name: binding(ROOT / name) for name in PIN_NAMES},
             "models": prepared["models"], "budget": prepared["future_request_budget"],
             "outputs": outputs(prepared["models"]), "sequential_owned_servers": True,
             "stop_at_first_invalid_or_unavailable": True, "admission_allowed": False}
    if any((ROOT / path).exists() for pair in value["outputs"].values() for path in pair.values()):
        raise ValueError("No repeated or overwritten cohort")
    with PLAN.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    verify()
    print(json.dumps({"declared": True, "maximum_model_requests": 6, "model_requests": 0}))


def verify():
    execution = json.loads(PLAN.read_bytes())
    required = {"protocol", "declared_utc", "base_head", "source", "preparation", "prepare_recipe",
                "recipe", "assets", "pins", "models", "budget", "outputs", "sequential_owned_servers",
                "stop_at_first_invalid_or_unavailable", "admission_allowed"}
    if (set(execution) != required or execution["protocol"] != "procedural-mug-connections-execution-plan-1"
            or execution["base_head"] != BASE or execution["recipe"] != binding(Path(__file__).resolve())
            or execution["prepare_recipe"] != binding(PREPARE_RECIPE) or execution["source"] != binding(SOURCE)
            or execution["preparation"] != binding(RESULT) or execution["assets"] != ASSETS
            or execution["pins"] != {name: binding(ROOT / name) for name in PIN_NAMES}
            or execution["sequential_owned_servers"] is not True
            or execution["stop_at_first_invalid_or_unavailable"] is not True or execution["admission_allowed"] is not False):
        raise ValueError("Changed execution provenance, policy or bound bytes")
    source = runpy.run_path(str(PREPARE_RECIPE))["verify"]()
    if (execution["models"] != source["models"] or fingerprint(execution["budget"]) != fingerprint(source["future_request_budget"])
            or execution["outputs"] != outputs(source["models"])):
        raise ValueError("Changed candidates, budget or outputs")
    return execution, source, checks.checked_json(ASSETS, ROOT)


def execute(repo):
    frozen = sha(PLAN)
    execution, source, assets = verify()
    if repo not in execution["models"]:
        raise ValueError("Choose a declared installed judge")
    paths = execution["outputs"][repo]
    output, logs = [(ROOT / paths[key]).resolve() for key in ["report", "logs"]]
    if any(not p.is_relative_to(ROOT) or p == ROOT or p.exists() for p in [output, logs]):
        raise ValueError("Fresh outputs only; no retries")
    if subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != BASE:
        raise ValueError("Execution HEAD changed")
    resource_snapshot = runpy.run_path(str(RESOURCE_RECIPE))["resources"]()
    if (any(resource_snapshot["ports_open"].values()) or resource_snapshot["ram_free_gib"] < 12
            or resource_snapshot["gpu"]["used_mib"] > 5288 or resource_snapshot["gpu"]["utilization_percent"] > 30
            or resource_snapshot["gpu"]["name"] != "NVIDIA GeForce RTX 3060" or resource_snapshot["gpu"]["total_mib"] != 12288):
        raise ValueError("Port/RAM/VRAM/GPU-load preflight prevents execution")
    model = shared.select_model(assets, repo)
    target = ROOT / "local_image_stack/experiments/bridge/target"
    runtime_root = target / "visual-judge-runtime"
    runtime = shared.verify_runtime(runtime_root, assets["runtime"])
    weights = [target / "visual-judge-models" / repo.split("/")[-1] / row["file"] for row in model["files"]]
    if any(sha(path) != row["sha256"] for path, row in zip(weights, model["files"], strict=True)):
        raise ValueError("Installed judge/projector changed")
    verify()
    logs.mkdir(parents=True, exist_ok=False)
    report = {"protocol": "procedural-mug-connections-result-1", "started_utc": datetime.now(timezone.utc).isoformat(),
              "execution_head": BASE, "execution_plan": binding(PLAN), "source_plan": execution["source"],
              "recipe": execution["recipe"], "model": model, "runtime": runtime, "resource_preflight": resource_snapshot,
              "rows": [], "http_model_requests_attempted": 0, "automatic_retries": 0, "generations": 0,
              "downloads": 0, "human_gold": False, "admission_allowed": False, "owned_server_closed": True}
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    def send(body):
        if sha(PLAN) != frozen:
            raise ValueError("Execution plan changed")
        verify()
        index = report["http_model_requests_attempted"]
        if index >= 3 or fingerprint(body) != source["request_bindings"][index]["request_sha256"]:
            raise ValueError("Changed request or exhausted budget")
        report["http_model_requests_attempted"] += 1
        save()
        return shared.base.request("http://127.0.0.1:8092/v1/chat/completions", body, timeout=60)
    def done(row):
        report["rows"].append(row)
        save()
        print(json.dumps({key: row[key] for key in ["case_id", "transport_status", "prepare_seconds", "request_parse_seconds"]}), flush=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    try:
        with shared.owned_server(shared.command(runtime_root / assets["runtime"]["tag"] / "llama-server.exe", weights),
                                 logs / "server.log", shared.base.request, subprocess.Popen, report):
            save()
            observer.collect(source["cases"], send, done)
    except (OSError, ValueError, RuntimeError) as exc:
        report["runtime_error_type"] = type(exc).__name__
    finally:
        with socket.socket() as connection:
            connection.settimeout(1)
            report["port_8092_open_after"] = connection.connect_ex(("127.0.0.1", 8092)) == 0
        report["unattempted_cases"] = [c["case_id"] for c in source["cases"][len(report["rows"]):]]
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--declare", action="store_true")
    group.add_argument("--verify-only", action="store_true")
    group.add_argument("--model-repo")
    args = parser.parse_args()
    if args.declare:
        declare()
    elif args.verify_only:
        verify()
        print(json.dumps({"verified": True, "model_requests": 0, "pairs": 3}))
    else:
        execute(args.model_repo)
