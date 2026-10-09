"""One fixed retained adjacent pair; reuse the published observer unchanged."""
import argparse
import ctypes
import json
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import observe_pairwise_cue as prior
from scripts import pairwise_cue_observations as observer

checks, shared = prior.checks, prior.shared
BUDGET = {"requests_per_model": 1, "maximum_requests_total": 2,
          "automatic_retries": 0, "new_generation_requests": 0,
          "new_downloads": 0, "stop_at_first_invalid_or_unavailable": True}


def verify(plan_path):
    plan = checks.checked_json({"path": str(plan_path), "sha256": shared.base.digest(plan_path)}, ROOT)
    if plan.get("protocol") != "retained-adjacent-cue-plan-1" or plan.get("budget") != BUDGET:
        raise ValueError("Changed fixed adjacent-pair protocol/budget")
    if checks.binding_path(plan["recipe"], ROOT) != Path(__file__).resolve():
        raise ValueError("Recipe path differs")
    checks.checked_bytes(plan["recipe"], ROOT)
    old_plan = checks.checked_json(plan["published_source_plan"], ROOT)
    verified = prior.preflight_plan(old_plan, ROOT)
    method = verified["method"]
    warm = next(c for c in method["cases"] if c["case_id"] == "retained_warm_512")
    hot = next(c for c in method["cases"] if c["case_id"] == "retained_hot_768")
    expected = {"case_id": "retained_warm_to_hot_adjacent",
                "previous_region_id": warm["current_region_id"],
                "current_region_id": hot["current_region_id"],
                "previous": warm["current"], "current": hot["current"]}
    if plan.get("cases") != [expected] or plan.get("comparison_candidates") != method["comparison_candidates"]:
        raise ValueError("Pair/model differs from the declared retained sources")
    if plan.get("human_gold") is not False or plan.get("expected_cue_visibility") is not None:
        raise ValueError("No independent cue labels established")
    body = observer.payload(expected["previous"], expected["current"], method["subject"], method["cue_query"])
    if body["messages"][0]["content"][0]["text"] != method["model_prompt"]:
        raise ValueError("Changed generic cue prompt")
    return plan, old_plan, method, verified["preflight"]


def resources():
    class Memory(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                    ("total_physical", ctypes.c_ulonglong), ("available_physical", ctypes.c_ulonglong),
                    ("total_page", ctypes.c_ulonglong), ("available_page", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong), ("available_virtual", ctypes.c_ulonglong),
                    ("available_extended", ctypes.c_ulonglong)]
    memory = Memory(); memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise OSError("RAM snapshot unavailable")
    gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                                   "--format=csv,noheader,nounits"], text=True, timeout=5).strip().splitlines()
    if len(gpu) != 1:
        raise ValueError("Expected one documented GPU")
    fields = [part.strip() for part in gpu[0].split(",")]
    ports = {}
    for port in (8080, 8092):
        with socket.socket() as connection:
            connection.settimeout(1)
            ports[str(port)] = connection.connect_ex(("127.0.0.1", port)) == 0
    return {"ram_free_gib": memory.available_physical / 1024**3,
            "gpu": {"name": fields[0], "used_mib": int(fields[1]), "total_mib": int(fields[2]),
                    "utilization_percent": int(fields[3]), "temperature_c": int(fields[4])},
            "ports_open": ports}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--verify-only", action="store_true")
    for name in ("model-repo", "output", "log-dir"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    plan_path = Path(args.plan).resolve()
    plan, old_plan, method, input_preflight = verify(plan_path)
    if args.verify_only:
        print(json.dumps({"verified": True, "requests": 0, "pair": plan["cases"][0],
                          "input_preflight": input_preflight}))
        return
    if args.model_repo not in plan["comparison_candidates"] or not args.output or not args.log_dir:
        raise ValueError("Declare one existing model and fresh output/log paths")
    output, logs = Path(args.output).resolve(), Path(args.log_dir).resolve()
    if any(not p.is_relative_to(ROOT) or p == ROOT or p.exists() for p in (output, logs)):
        raise ValueError("Preserve prior files; outputs must be fresh within the worktree")
    snapshot = resources()
    if (any(snapshot["ports_open"].values()) or snapshot["ram_free_gib"] < 12
            or snapshot["gpu"]["used_mib"] > 5288 or snapshot["gpu"]["utilization_percent"] > 30):
        raise ValueError("Port/RAM/VRAM/GPU-load preflight prevents this bounded query")
    assets = checks.checked_json(method["assets_manifest"], ROOT)
    model = shared.select_model(assets, args.model_repo)
    target = ROOT / "local_image_stack/experiments/bridge/target"
    runtime_root = target / "visual-judge-runtime"
    runtime = shared.verify_runtime(runtime_root, assets["runtime"])
    weights = [target / "visual-judge-models" / model["repo"].split("/")[-1] / item["file"] for item in model["files"]]
    for path, item in zip(weights, model["files"]):
        if shared.base.digest(path) != item["sha256"]:
            raise ValueError("Model bytes changed")
    verify(plan_path)
    logs.mkdir(parents=True, exist_ok=False)
    report = {"protocol": "retained-adjacent-cue-result-1", "observer_version": observer.VERSION,
              "execution_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "plan": {"path": str(plan_path), "sha256": shared.base.digest(plan_path)},
              "source_plan": plan["published_source_plan"], "implementation": old_plan["implementation"],
              "recipe": plan["recipe"], "model": model, "runtime": runtime,
              "input_preflight": input_preflight, "resource_preflight": snapshot,
              "subject": method["subject"], "cue_query": method["cue_query"],
              "rows": [], "http_model_requests_attempted": 0, "automatic_retries": 0,
              "generation_requests": 0, "human_gold": False, "admission_allowed": False,
              "physical_identity_established": False, "physical_temperature_measured": False,
              "owned_server_closed": False}
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    def done(row):
        report["rows"].append(row); save()
        print(json.dumps({k: row[k] for k in ("case_id", "transport_status", "seconds")}), flush=True)
    def request(body):
        verify(plan_path)
        if report["http_model_requests_attempted"] >= 1:
            raise ValueError("One model request per candidate, no retry")
        report["http_model_requests_attempted"] += 1
        return shared.base.request("http://127.0.0.1:8092/v1/chat/completions", body, timeout=60)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write("\n")
    try:
        with shared.owned_server(shared.command(runtime_root / assets["runtime"]["tag"] / "llama-server.exe", weights),
                                 logs / "server.log", shared.base.request, subprocess.Popen, report):
            save()
            observer.collect(plan["cases"], method["subject"], method["cue_query"], request, done)
    except (OSError, ValueError, RuntimeError) as exc:
        report["runtime_error_type"] = type(exc).__name__
    finally:
        with socket.socket() as connection:
            connection.settimeout(1)
            report["port_8092_open_after"] = connection.connect_ex(("127.0.0.1", 8092)) == 0
        report["unattempted_cases"] = [c["case_id"] for c in plan["cases"][len(report["rows"]):]]
        save()


if __name__ == "__main__":
    main()
