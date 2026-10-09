"""Bounded experimental paired-shape runner; no MPT integration or generation."""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path, PurePosixPath
import socket
import subprocess
import time
import zipfile

from scripts import evaluate_multimodal_judges as base
from scripts.observe_visual_geometry import select_model
from scripts import paired_shape_observations as observer
from scripts import paired_shape_preflight as input_checks

def command(server, weights):
    return [str(server), "-m", str(weights[0]), "--mmproj", str(weights[1]),
            "--host", "127.0.0.1", "--port", "8092", "-ngl", "99", "-c", "8192", "-np", "1",
            "-b", "2048", "-ub", "512", "--jinja", "--no-warmup", "--flash-attn", "on",
            "--image-min-tokens", "1024", "--image-max-tokens", "1536", "--reasoning", "off",
            "--chat-template-kwargs", '{"enable_thinking":false}']

def validate_plan(plan):
    if plan.get("protocol") not in {"paired-major-shape-probe-plan-1", "paired-major-shape-probe-plan-2"}:
        raise ValueError("Unknown paired protocol")
    expected = {"maximum_requests_total": 6, "requests_per_model": 3, "automatic_retries": 0,
                "port": 8092, "context": 8192, "temperature": 0, "max_tokens": 256, "thinking": False,
                "json_schema": True, "http_timeout_seconds": 60, "min_image_tokens": 1024,
                "max_image_tokens": 1536, "new_generation_requests": 0, "new_downloads": 0,
                "separate_sequential_owned_servers": True, "stop_model_cohort_at_first_invalid_or_unavailable": True}
    execution = plan.get("execution", {})
    for key, value in expected.items():
        if type(execution.get(key)) is not type(value) or execution[key] != value:
            raise ValueError("Changed experimental budget or decoding contract")
    cases = plan.get("cases")
    if not isinstance(cases, list) or len(cases) != 3:
        raise ValueError("Expected three declared pairs")
    ids = [case.get("case_id") for case in cases]
    if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != 3 or ids != execution.get("case_order"):
        raise ValueError("Duplicate or reordered cases")
    if plan.get("model_prompt") != observer.prompt(plan.get("subject")) or plan.get("response_schema") != observer.schema():
        raise ValueError("Changed public prompt or response schema")
    if plan["protocol"] == "paired-major-shape-probe-plan-2":
        input_checks.validate_evidence(plan)
    return plan


def preflight_plan(plan, root):
    validate_plan(plan)
    input_checks.checked_bytes(plan["assets_manifest"], root)
    if plan["protocol"] == "paired-major-shape-probe-plan-2":
        result = input_checks.preflight(plan, root)
    else:
        input_checks.checked_bytes(plan["human_review"], root)
        result = {"gold_origin": "bound_human_review"}
    for case in plan["cases"]:
        observer.payload(case["reference"], case["candidate"], plan["subject"])
    return {"plan_protocol": plan["protocol"], **result}

def verify_runtime(runtime_root, runtime):
    runtime_root = Path(runtime_root)
    if Path(runtime["tag"]).name != runtime["tag"]:
        raise ValueError("Invalid runtime tag")
    folder = (runtime_root / runtime["tag"]).resolve()
    verified, count = [], 0
    for artifact in runtime["assets"]:
        if Path(artifact["name"]).name != artifact["name"]:
            raise ValueError("Invalid archive filename")
        archive = runtime_root / artifact["name"]
        actual = base.digest(archive)
        if "sha256:" + actual != artifact["digest"]:
            raise ValueError("Runtime archive changed")
        with zipfile.ZipFile(archive) as compressed:
            for entry in compressed.infolist():
                if entry.is_dir() or not entry.filename.lower().endswith((".dll", ".exe")):
                    continue
                member = PurePosixPath(entry.filename)
                destination = (folder / entry.filename).resolve()
                if member.is_absolute() or ".." in member.parts or not destination.is_relative_to(folder):
                    raise ValueError("Unsafe runtime member")
                with compressed.open(entry) as stream:
                    expected = hashlib.file_digest(stream, "sha256").hexdigest()
                if base.digest(destination) != expected:
                    raise ValueError("Extracted runtime changed")
                count += 1
        verified.append({"name": artifact["name"], "sha256": actual})
    return {"archives": verified, "extracted_files_checked": count,
            "server_sha256": base.digest(folder / "llama-server.exe")}

@contextmanager
def owned_server(command, log_path, request_fn, process_factory, state=None):
    server = None
    info = state if state is not None else {}
    info["owned_server_closed"] = True
    log_path = Path(log_path)
    try:
        with log_path.open("x", encoding="utf-8") as log:
            started = time.perf_counter()
            server = process_factory(command, stdout=log, stderr=log,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            info.update(owned_pid=server.pid, owned_server_closed=False)
            while time.perf_counter() - started < 90:
                if server.poll() is not None:
                    raise RuntimeError("Owned server exited during load")
                # Confirm binding in our process's log before trusting a health
                # response; a competing listener cannot satisfy readiness.
                if "listening on http://127.0.0.1:8092" in log_path.read_text(encoding="utf-8", errors="replace"):
                    try:
                        request_fn("http://127.0.0.1:8092/health", timeout=2)
                        break
                    except (OSError, ValueError):
                        pass
                time.sleep(1)
            else:
                raise TimeoutError("Owned server readiness timeout")
            props = request_fn("http://127.0.0.1:8092/props", timeout=3)
            if not props.get("modalities", {}).get("vision") or server.poll() is not None:
                raise ValueError("Owned vision service unavailable")
            info.update(load_seconds=time.perf_counter() - started, modalities=props["modalities"])
            yield info
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill(); server.wait(timeout=10)
        info["owned_server_closed"] = server is None or server.poll() is not None


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--model-repo", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--log-dir", required=True)
    args = parser.parse_args()
    output, logs = Path(args.output), Path(args.log_dir)
    if output.exists() or logs.exists():
        raise ValueError("Preserve existing report/logs; no retry")
    root = Path(__file__).resolve().parents[1]
    plan = validate_plan(json.loads(Path(args.plan).read_text(encoding="utf-8")))
    if args.model_repo not in plan["comparison_candidates"]:
        raise ValueError("Model not declared in plan")
    input_preflight = preflight_plan(plan, root)
    for port in [8080, 8092]:
        with socket.socket() as connection:
            connection.settimeout(1)
            if connection.connect_ex(("127.0.0.1", port)) == 0:
                raise ValueError("8080/8092 must be free")
    if base.gpu_memory() > 5288:
        raise ValueError("Less than7000MiB free on the documented RTX3060")
    manifest = json.loads((root / plan["assets_manifest"]["path"]).read_text())
    model = select_model(manifest, args.model_repo)
    target = root / "local_image_stack/experiments/bridge/target"
    runtime_root = target / "visual-judge-runtime"
    runtime = verify_runtime(runtime_root, manifest["runtime"])
    weights = [target / "visual-judge-models" / model["repo"].split("/")[-1] / artifact["file"]
               for artifact in model["files"]]
    for path, artifact in zip(weights, model["files"]):
        if base.digest(path) != artifact["sha256"]:
            raise ValueError("Model bytes changed")
    logs.mkdir(parents=True)
    report = {"protocol": observer.VERSION, "execution_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "harness_sha256": base.digest(__file__), "observer_sha256": base.digest(observer.__file__),
              "input_checks_sha256": base.digest(input_checks.__file__),
              "plan_sha256": base.digest(args.plan), "model": model, "runtime": runtime,
              "input_preflight": input_preflight, "http_model_requests_attempted": 0,
              "generation_requests": 0, "automatic_retries": 0, "subject": plan["subject"], "rows": [],
              "policy": {"labels_sent": False, "case_names_sent": False, "mask_used": False,
                         "max_tokens": 256, "timeout_seconds": 60, "thinking": False},
              "owned_server_closed": False, "admission_allowed": False, "automatic_rejection": False,
              "physical_identity_established": False}
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    def row_done(row):
        report["rows"].append(row); save()
        print(json.dumps({key: row[key] for key in ["case_id", "transport_status", "seconds"]}), flush=True)
    def model_request(body):
        if plan["protocol"] == "paired-major-shape-probe-plan-2":
            preflight_plan(plan, root)
        report["http_model_requests_attempted"] += 1
        return base.request("http://127.0.0.1:8092/v1/chat/completions", body, timeout=60)
    save()
    try:
        with owned_server(command(runtime_root / manifest["runtime"]["tag"] / "llama-server.exe", weights),
                          logs / "server.log", base.request, subprocess.Popen, report):
            save()
            observer.collect(plan["cases"], plan["subject"], model_request, row_done)
    except (OSError, ValueError, RuntimeError) as exc:
        report["runtime_error_type"] = type(exc).__name__
    finally:
        # owned_server finishes termination/wait before this block; a port still
        # occupied may belong to someone else and is never killed here.
        with socket.socket() as connection:
            connection.settimeout(1); report["port_8092_open_after"] = connection.connect_ex(("127.0.0.1", 8092)) == 0
        report["requests_attempted"] = sum(row["request_attempted"] for row in report["rows"])
        report["unattempted_cases"] = [case["case_id"] for case in plan["cases"][len(report["rows"]):]]
        save()


if __name__ == "__main__":
    main()
