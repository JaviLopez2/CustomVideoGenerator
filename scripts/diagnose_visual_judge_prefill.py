"""Fresh-server controls for visual prefill; retained pixels only, no admission."""
import argparse
import base64
import json
import runpy
import socket
import subprocess
import time
from pathlib import Path

H = runpy.run_path(str(Path(__file__).with_name("evaluate_multimodal_judges.py")))
REPO = "unsloth/Qwen3.5-9B-GGUF"


def probe_plan(dataset, regions):
    cases = {case["id"]: case for case in dataset["cases"]}
    plan = [{"id": "text_control", "case_id": None, "images": []}]
    for case_id, prefix in [("valid_cloth_edit", "positive"),
                            ("mpt_t2i_text_contract_768", "negative")]:
        case = cases[case_id]
        crops = [r for r in regions[case_id] if r["query"] in {"pocket watch", "watch hands"}]
        if len(crops) != 1 or crops[0]["source_sha256"] != case["sha256"]:
            raise ValueError("Missing or unrelated watch region")
        full = {"path": case["artifact"], "sha256": case["sha256"], "role": "full candidate"}
        crop = {**crops[0], "role": "detail of the same candidate"}
        for mode, images in [("full", [full]), ("crop", [crop])]:
            plan.append({"id": prefix + "_" + mode, "case_id": case_id, "images": images})
        if prefix == "positive":
            plan.append({"id": prefix + "_full_crop", "case_id": case_id, "images": [full, crop]})
    return plan


def payload(probe):
    contract = {"counts": [{"subject": "watch hands", "expected_count": 2}]}
    text = ("Count every distinct visible hand radiating from the watch dial center, including a seconds hand. "
            "Report observed_count without assuming a conventional number. If obscured, use null and uncertain=true. "
            "Multiple views depict the SAME watch, not additional objects. Return only JSON with counts containing "
            "one object: subject=watch hands, observed_count, uncertain, reason. Give brief pixel evidence. "
            "Do not provide chain of thought.")
    if not probe["images"]:
        text = ("Text-only transport/schema control, not a visual judgment. Return counts with one object: "
                "subject=watch hands, observed_count=null, uncertain=true, reason=no image supplied.")
    parts = [{"type": "text", "text": text}]
    for image in probe["images"]:
        if H["digest"](image["path"]) != image["sha256"]:
            raise ValueError("Input image changed")
        parts += [{"type": "text", "text": image["role"]},
                  {"type": "image_url", "image_url": {"url": "data:image/png;base64," +
                   base64.b64encode(Path(image["path"]).read_bytes()).decode()}}]
    return {"model": "visual-judge", "messages": [{"role": "user", "content": parts}],
            "temperature": 0, "max_tokens": 192,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema", "json_schema": {"name": "observed_parts", "strict": True,
                                "schema": H["response_schema"](contract)}}}


def memory():
    result = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used,memory.total",
                                      "--format=csv,noheader,nounits"], text=True,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=5)
    used, total = map(int, result.strip().split(","))
    return {"used_mib": used, "total_mib": total}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--log-dir", required=True)
    parser.add_argument("--execute", action="store_true", help="Without this, save only an offline plan")
    parser.add_argument("--probe-ids", help="Select explicit controls; no retries within a run")
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Output exists; preserve evidence")
    root = Path(__file__).resolve().parents[1]
    validation = root / "docs/validation"
    dataset = json.loads((validation / "visual-qa-dataset-2026-10-08.json").read_text(encoding="utf-8"))
    regions = json.loads((validation / "visual-judge-regions-2026-10-08.json").read_text(encoding="utf-8"))
    plan = probe_plan(dataset, regions)
    if args.probe_ids:
        wanted = args.probe_ids.split(",")
        if len(wanted) != len(set(wanted)) or set(wanted) - {p["id"] for p in plan}:
            raise ValueError("Invalid selection")
        plan = [p for p in plan if p["id"] in wanted]
    for probe in plan:
        payload(probe)  # Verify hashes before creating any server; payload never persisted.
    manifest = json.loads((validation / "visual-judge-candidates-assets-2026-10-08.json").read_text(encoding="utf-8"))
    model = next(m for m in manifest["models"] if m["repo"] == REPO)
    target = root / "local_image_stack/experiments/bridge/target"
    files = [target / "visual-judge-models" / REPO.split("/")[-1] / f["file"] for f in model["files"]]
    report = {"execution_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "harness_sha256": H["digest"](__file__), "executed": args.execute, "generation_requests": 0,
              "automatic_retries": 0, "model": model, "runtime": manifest["runtime"], "plan": plan, "rows": [],
              "policy": {"fresh_server_per_request": True, "timeout_seconds": 60, "max_tokens": 192,
                         "context": 8192, "image_min_tokens": 1024, "image_max_tokens": 1536,
                         "flash_attention": "on", "reasoning": "off", "blind_counts": True,
                         "references": False, "production_admission": False}}
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.execute:
        save()
        print(json.dumps({"executed": False, "controls": len(plan)}))
        return
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", 8080)) == 0:
            raise ValueError("Shared 8080 still open: wait for user resource clearance")
    for path, artifact in zip(files, model["files"]):
        if H["digest"](path) != artifact["sha256"]:
            raise ValueError("Model hash mismatch")
    logs = Path(args.log_dir)
    logs.mkdir(parents=True, exist_ok=False)
    server_path = target / "visual-judge-runtime/b11497/llama-server.exe"
    report["runtime_version"] = subprocess.check_output([str(server_path), "--version"], text=True,
                                                       stderr=subprocess.STDOUT).strip()
    save()
    for probe in plan:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", 8092)) == 0:
                raise ValueError("Experimental port occupied")
        baseline = memory()
        if baseline["total_mib"] - baseline["used_mib"] < 7000:
            report["stopped_reason"] = "Less than 7000 MiB free global VRAM"
            save()
            break
        command = [str(server_path), "-m", str(files[0]), "--mmproj", str(files[1]), "--host", "127.0.0.1",
                   "--port", "8092", "-ngl", "99", "-c", "8192", "-np", "1", "-b", "2048", "-ub", "512",
                   "--jinja", "--no-warmup", "--image-min-tokens", "1024", "--image-max-tokens", "1536",
                   "--flash-attn", "on", "--reasoning", "off"]
        row = {"id": probe["id"], "transport_status": "unavailable", "baseline_global_vram": baseline, "inputs": probe["images"],
               "log": str((logs / (probe["id"] + ".log")).resolve())}
        server = None
        try:
            started = time.perf_counter()
            with Path(row["log"]).open("x", encoding="utf-8") as log:
                server = subprocess.Popen(command, stdout=log, stderr=log,
                                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                row["owned_pid"] = server.pid
                while time.perf_counter() - started < 90:
                    if server.poll() is not None:
                        raise RuntimeError("Owned server exited during load")
                    try:
                        H["request"]("http://127.0.0.1:8092/health", timeout=2)
                        break
                    except (OSError, ValueError):
                        time.sleep(1)
                else:
                    raise TimeoutError("Load timeout")
                row["load_seconds"] = time.perf_counter() - started
                began = time.perf_counter()
                try:
                    response = H["request"]("http://127.0.0.1:8092/v1/chat/completions", payload(probe), timeout=60)
                    choice = response["choices"][0]
                    message = choice["message"]
                    row.update(final_content=message.get("content"), finish_reason=choice["finish_reason"],
                               reasoning_characters=len(message.get("reasoning_content") or ""),
                               usage=response.get("usage"), server_timings=response.get("timings"))
                    if choice["finish_reason"] != "stop" or row["reasoning_characters"]:
                        raise ValueError("Incomplete response or thinking")
                    answer = json.loads(row["final_content"])
                    H["normalize"](answer, {"counts": [{"subject": "watch hands", "expected_count": 2}]})
                    row["observed"] = answer["counts"][0]
                    row["transport_status"] = "completed"
                finally:
                    row["request_seconds"] = time.perf_counter() - began
                    row["post_request_global_vram"] = memory()
        except (OSError, ValueError, RuntimeError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            row.update(transport_status="unavailable", error_type=type(exc).__name__)
        finally:
            if server is not None and server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=10)
            row["owned_server_closed"] = server is None or server.poll() is not None
            report["rows"].append(row)
            save()
            print(json.dumps({k: row[k] for k in ["id", "transport_status", "owned_server_closed"]}), flush=True)
        if probe["id"] == "text_control" and row["transport_status"] != "completed":
            report["stopped_reason"] = "Text control failed; do not attempt visual requests"
            save()
            break


if __name__ == "__main__":
    main()
