"""Bounded comparison of two local VLMs on retained artifacts, no generation."""
import argparse
import base64
import hashlib
import json
import os
import socket
import statistics
import subprocess
import threading
import time
import urllib.request
from pathlib import Path


STATUSES = {"pass", "fail", "uncertain", "unavailable"}


def response_schema(contract, concise=False):
    status = {"type": "string", "enum": sorted(STATUSES)}
    reason = {"type": "string"}
    if concise:
        reason["maxLength"] = 120
    check = {"type": "object", "properties": {"status": status, "reason": reason},
             "required": ["status", "reason"], "additionalProperties": False}
    count = {"type": "object", "properties": {"subject": {"type": "string"},
        "observed_count": {"type": ["integer", "null"]}, "uncertain": {"type": "boolean"}, "reason": reason},
        "required": ["subject", "observed_count", "uncertain", "reason"], "additionalProperties": False}
    properties = {"counts": {"type": "array", "items": count,
                             "minItems": len(contract.get("counts", [])), "maxItems": len(contract.get("counts", []))}}
    if contract.get("geometry_constraints"):
        properties["geometry"] = check
    if contract.get("forbid_text"):
        properties["text"] = check
    if contract.get("temporal"):
        temporal = {"type": "object", "properties": {"status": status, "reason": reason,
            "score": {"type": ["number", "null"]}}, "required": ["status", "score", "reason"], "additionalProperties": False}
        properties.update({name: temporal for name in ["identity", "state", "progression"]})
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def normalize(answer, contract):
    """Count verdict comes from observed cardinality, never from expected-count echo."""
    checks = []
    observed = answer.get("counts")
    if not isinstance(observed, list) or len(observed) != len(contract.get("counts", [])):
        raise ValueError("Incomplete count response")
    for expected, actual in zip(contract.get("counts", []), observed):
        if not isinstance(actual, dict) or type(actual.get("uncertain", False)) is not bool:
            raise ValueError("Invalid count response")
        if actual.get("subject") != expected["subject"]:
            raise ValueError("Count subject mismatch")
        count = actual.get("observed_count")
        reason = actual.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Missing count evidence")
        if count is None or actual.get("uncertain") is True:
            status = "uncertain"
        elif type(count) is not int or count < 0:
            raise ValueError("Invalid observed count")
        else:
            status = "pass" if abs(count - expected["expected_count"]) <= expected.get("tolerance", 0) else "fail"
        checks.append({"kind": "quantity", "subject": expected["subject"], "observed_count": count,
                       "status": status, "reason": reason})
    required = []
    if contract.get("geometry_constraints"):
        required.append("geometry")
    if contract.get("forbid_text"):
        required.append("text")
    if contract.get("temporal"):
        required += ["identity", "state", "progression"]
    for kind in required:
        check = answer.get(kind)
        if not isinstance(check, dict) or check.get("status") not in STATUSES or not str(check.get("reason") or "").strip():
            raise ValueError("Incomplete required visual check")
        if kind in {"identity", "state", "progression"}:
            score = check.get("score")
            if score is not None and (type(score) not in {int, float} or not 0 <= score <= 1):
                raise ValueError("Invalid temporal score")
        checks.append({"kind": kind, **check})
    statuses = [c["status"] for c in checks]
    verdict = next((s for s in ["fail", "unavailable", "uncertain"] if s in statuses), "pass")
    return {"verdict": verdict, "checks": checks}


def content(case, blind_counts=False, regions=None):
    contract = case["contract"]
    public = {k: v for k, v in contract.items() if k not in {"reference_image", "temporal"}}
    if blind_counts:
        public["counts"] = [{k: v for k, v in count.items() if k not in {"expected_count", "tolerance"}}
                            for count in contract.get("counts", [])]
    if contract.get("temporal"):
        public["temporal"] = {k: v for k, v in contract["temporal"].items() if k != "previous_image"}
    instructions = (
        "Inspect the actual candidate pixels and supplied reference pixels. Judge ONLY the structured requirements. "
        "Count small parts as well as whole objects when requested. "
        + ("Include every visible instance of each named component; do not omit a component because it has a different conventional role. " if blind_counts else "")
        + "Report observed counts independently of expected counts; "
        "if obscured or ambiguous use null and uncertain=true. Do not infer visual compliance from the wording of the request. "
        "Allow changes named in allowed_changes; distinguish physical identity from visible temporal state. "
        "Lighting alone is not physical state progression. A deformed or fused major component can violate structure even "
        "if its object name remains recognizable. No prior review verdict is supplied. "
        "For temporal scenes compare the previous image, not just its narrated state; if comparison cannot establish change, uncertain. "
        "Return ONLY a compact JSON object. counts is an array in contract order, each {subject,observed_count,uncertain,reason}. "
        "For each requested geometry or text check include {status,reason}; text pass means no forbidden visible text. "
        "For temporal include separate identity,state,progression objects each {status,score,reason}; score is 0..1 or null. "
        "Statuses are pass/fail/uncertain/unavailable. Give short concrete visual evidence. Do not output chain of thought. "
        "All check objects are TOP-LEVEL fields, not nested in temporal or forbid_text. "
        "Contract: " + json.dumps(public, ensure_ascii=False)
    )
    parts = [{"type": "text", "text": instructions}]
    inputs = [(case["artifact"], "CANDIDATE", case["sha256"])]
    seen = {str(Path(case["artifact"]).resolve())}
    for ref in case.get("references", []):
        path = str(Path(ref["path"]).resolve())
        if path not in seen:
            inputs.append((path, f"REFERENCE slot {ref['slot']} role {ref['role']}", ref["sha256"]))
            seen.add(path)
    for path, role in [(contract.get("reference_image"), "GEOMETRY REFERENCE"),
                       (contract.get("temporal", {}).get("previous_image"), "PREVIOUS TEMPORAL STATE")]:
        if path and str(Path(path).resolve()) not in seen:
            inputs.append((path, role, digest(path)))
            seen.add(str(Path(path).resolve()))
    for region in (regions or []):
        if region.get("source_sha256") != case["sha256"]:
            raise ValueError("Supplementary region belongs to another candidate")
        inputs.append((region["path"], "CANDIDATE DETAIL: " + region["query"], region["sha256"]))
    for path, role, expected in inputs:
        if digest(path) != expected:
            raise ValueError("Artifact changed")
        parts.append({"type": "text", "text": role})
        parts.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()}})
    return parts, [{"role": role, "sha256": expected} for _, role, expected in inputs]


def gpu_memory():
    result = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                            capture_output=True, text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return int(result.stdout.strip().splitlines()[0])


def request(url, payload=None, timeout=60):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--models", required=True)
    parser.add_argument("--server", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--log-dir", required=True)
    parser.add_argument("--gpu-layers", type=int, default=99)
    parser.add_argument("--port", type=int, default=8092)
    parser.add_argument("--model-repo", help="Evaluate only this pinned repository")
    parser.add_argument("--case-ids", help="Comma-separated previously unattempted cases")
    parser.add_argument("--blind-counts", action="store_true", help="Diagnostic: withhold expected cardinality from model")
    parser.add_argument("--regions", help="Diagnostic: previously measured candidate regions, supplementary to full images")
    parser.add_argument("--unbounded-schema-strings", action="store_true", help="Diagnostic: omit JSON grammar string-length bounds")
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Evidence output already exists")
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", args.port)) == 0:
            raise ValueError("Experimental port already occupied")
    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    regions = json.loads(Path(args.regions).read_text(encoding="utf-8")) if args.regions else {}
    if args.model_repo:
        manifest["models"] = [m for m in manifest["models"] if m["repo"] == args.model_repo]
        if not manifest["models"]:
            raise ValueError("Model not in pinned manifest")
    if args.case_ids:
        selected = args.case_ids.split(",")
        known = {case["id"] for case in dataset["cases"]}
        if len(selected) != len(set(selected)) or set(selected) - known:
            raise ValueError("Unknown/duplicate case selection")
        dataset["cases"] = [case for case in dataset["cases"] if case["id"] in selected]
    logs = Path(args.log_dir)
    logs.mkdir(parents=True, exist_ok=True)
    report = {"base_head": manifest["base_head"], "runtime": manifest["runtime"], "generation_requests": 0,
              "inference_retries": 0, "policy": {"max_tokens": 768, "timeout_seconds": 60,
              "temperature": 0, "context": 8192, "gpu_layers": args.gpu_layers, "image_max_tokens": 1536,
              "thinking": False, "response_format": "json_schema", "flash_attention": "on",
              "image_min_tokens": 1024, "evaluation_version": 2}, "models": []}
    report["case_ids"] = [case["id"] for case in dataset["cases"]]
    report["execution_head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    report["harness_sha256"] = digest(__file__)
    report["policy"]["blind_counts"] = args.blind_counts
    report["policy"]["supplementary_regions"] = bool(args.regions)
    if args.blind_counts or args.regions:
        report["policy"]["evaluation_version"] = 3
    report["policy"]["schema_reason_max_length"] = 120 if args.blind_counts and not args.unbounded_schema_strings else None
    if args.unbounded_schema_strings:
        report["policy"]["evaluation_version"] = 4
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save()
    for model in manifest["models"]:
        folder = Path(args.models) / model["repo"].split("/")[-1]
        files = [folder / artifact["file"] for artifact in model["files"]]
        for path, artifact in zip(files, model["files"]):
            if digest(path) != artifact["sha256"]:
                raise ValueError("Model hash mismatch")
        record = {"repo": model["repo"], "revision": model["revision"], "rows": [],
                  "baseline_global_vram_mib": gpu_memory(), "log": str((logs / (folder.name + ".log")).resolve())}
        report["models"].append(record)
        save()
        command = [str(Path(args.server).resolve()), "-m", str(files[0].resolve()), "--mmproj", str(files[1].resolve()),
                   "--host", "127.0.0.1", "--port", str(args.port), "-ngl", str(args.gpu_layers), "-c", "8192", "-np", "1",
                   "-b", "2048", "-ub", "512", "--jinja", "--no-warmup", "--image-max-tokens", "1536",
                   "--image-min-tokens", "1024", "--flash-attn", "on",
                   "--reasoning", "off", "--chat-template-kwargs", '{"enable_thinking":false}']
        server = None
        try:
            started = time.perf_counter()
            with Path(record["log"]).open("x", encoding="utf-8") as log:
                server = subprocess.Popen(command, stdout=log, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                record["owned_pid"] = server.pid
                base = f"http://127.0.0.1:{args.port}"
                while time.perf_counter() - started < 90:
                    if server.poll() is not None:
                        raise RuntimeError("Owned server exited during load")
                    try:
                        request(base + "/health", timeout=2)
                        break
                    except (OSError, ValueError):
                        time.sleep(1)
                else:
                    raise TimeoutError("Owned server readiness timeout")
                record["load_seconds"] = time.perf_counter() - started
                props = request(base + "/props", timeout=3)
                record["modalities"] = props.get("modalities")
                if not props.get("modalities", {}).get("vision"):
                    raise ValueError("Vision not available")
                for case in dataset["cases"]:
                    parts, inputs = content(case, args.blind_counts, regions.get(case["id"]))
                    baseline = gpu_memory()
                    samples, stop = [baseline], threading.Event()
                    def monitor():
                        while not stop.wait(1):
                            try:
                                samples.append(gpu_memory())
                            except (OSError, ValueError, subprocess.TimeoutExpired):
                                pass
                    worker = threading.Thread(target=monitor, daemon=True)
                    worker.start()
                    began = time.perf_counter()
                    row = {"id": case["id"], "expected": case["expected_verdict"], "inputs": inputs}
                    try:
                        response = request(base + "/v1/chat/completions", {"model": "visual-judge", "messages": [{"role": "user", "content": parts}],
                            "max_tokens": 768, "temperature": 0, "response_format": {"type": "json_schema",
                            "json_schema": {"name": "visual_qa", "strict": True,
                            "schema": response_schema(case["contract"], args.blind_counts and not args.unbounded_schema_strings)}},
                            "chat_template_kwargs": {"enable_thinking": False}}, timeout=60)
                        choice = response["choices"][0]
                        message = choice["message"]
                        row.update(finish_reason=choice["finish_reason"], usage=response.get("usage"), server_timings=response.get("timings"),
                                   reasoning_characters=len(message.get("reasoning_content") or ""))
                        final = message.get("content") or ""
                        row["final_content"] = final
                        if choice["finish_reason"] != "stop" or row["reasoning_characters"]:
                            raise ValueError("Incomplete response or thinking unexpectedly active")
                        row.update(normalize(json.loads(final), case["contract"]))
                    except (OSError, ValueError, KeyError, TypeError) as exc:
                        row.update(verdict="unavailable", error_type=type(exc).__name__)
                    finally:
                        row["seconds"] = time.perf_counter() - began
                        stop.set()
                        worker.join(timeout=6)
                        row["baseline_global_vram_mib"] = baseline
                        row["peak_global_vram_mib"] = max(samples)
                        row["vram_samples"] = len(samples)
                    record["rows"].append(row)
                    save()
                    print(json.dumps({"model": folder.name, "id": row["id"], "verdict": row["verdict"],
                                      "seconds": round(row["seconds"], 3), "peak_mib": row["peak_global_vram_mib"]}), flush=True)
                    if len(record["rows"]) >= 2 and all(r["verdict"] == "unavailable" for r in record["rows"][-2:]):
                        record["stopped_reason"] = "Two consecutive unavailable results; no automatic retry"
                        break
        except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
            record["runtime_error_type"] = type(exc).__name__
            print(json.dumps({"model": folder.name, "runtime_error_type": type(exc).__name__}), flush=True)
        finally:
            if server is not None and server.poll() is None:
                server.terminate()  # ONLY the process launched above, never shared services.
                try:
                    server.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=10)
            record["owned_server_closed"] = server is None or server.poll() is not None
            save()
        times = [r["seconds"] for r in record["rows"]]
        if times:
            record["mean_seconds"] = statistics.mean(times)
            record["median_seconds"] = statistics.median(times)
        save()


if __name__ == "__main__":
    main()
