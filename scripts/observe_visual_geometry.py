"""Experimental single-image inventories; mismatches are hints, never admission."""
import argparse
import base64
import json
import runpy
import socket
import subprocess
import time
from pathlib import Path

H = runpy.run_path(str(Path(__file__).with_name("evaluate_multimodal_judges.py")))
FEATURES = ("openings", "edge_cutouts", "rings_or_collars", "part_junctions")


def schema():
    feature = {"type": "object", "properties": {
        "visibility": {"type": "string", "enum": ["present", "absent", "uncertain"]},
        "observed_count": {"type": ["integer", "null"], "minimum": 0},
        "description": {"type": "string"}},
        "required": ["visibility", "observed_count", "description"], "additionalProperties": False}
    return {"type": "object", "properties": {f: feature for f in FEATURES},
            "required": list(FEATURES), "additionalProperties": False}


def payload(path, sha256, target):
    if H["digest"](path) != sha256:
        raise ValueError("Image changed")
    instruction = (
        "Describe ONLY the target visible in this single image: " + target + ". "
        "Do not compare against another image or infer conventional anatomy from the object name. "
        "Observe these features independently: openings (visible physical holes); edge_cutouts (notches on an edge); "
        "rings_or_collars (bands encircling a component); part_junctions (visible connections between components). "
        "Ignore background objects. Do not invent hidden or occluded parts. Distinguish shadows/reflections from physical features. "
        "For each feature return visibility present/absent/uncertain, observed_count integer or null, and a short description "
        "of actual shape and position. Absent requires count 0; uncertain requires null. Present can use null if count is unclear. "
        "No desired count, prior annotation, reference role, verdict, confidence score or acceptance criterion is supplied. "
        "Return JSON only, one field per named feature. Report concise observations, no deliberation or chain of thought.")
    return {"model": "visual-judge", "messages": [{"role": "user", "content": [
        {"type": "text", "text": instruction}, {"type": "image_url", "image_url": {
         "url": "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()}}]}],
        "temperature": 0, "max_tokens": 512, "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {"type": "json_schema", "json_schema": {"name": "pixel_inventory", "strict": True,
                             "schema": schema()}}}


def validate(answer):
    if not isinstance(answer, dict) or set(answer) != set(FEATURES):
        raise ValueError("Missing or extra inventory fields")
    for feature in FEATURES:
        row = answer[feature]
        if not isinstance(row, dict) or set(row) != {"visibility", "observed_count", "description"}:
            raise ValueError("Malformed feature")
        visibility, count = row["visibility"], row["observed_count"]
        if visibility not in {"present", "absent", "uncertain"}:
            raise ValueError("Invalid visibility")
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError("Invalid count")
        if visibility == "absent" and count != 0 or visibility == "uncertain" and count is not None:
            raise ValueError("Contradictory inventory")
        if visibility == "present" and count == 0:
            raise ValueError("Present feature with zero count")
        if not isinstance(row["description"], str) or not row["description"].strip():
            raise ValueError("Missing pixel description")
    return answer


def compare(reference, candidate):
    """Categorical differences only; no inference that matching inventories prove identity."""
    validate(reference)
    validate(candidate)
    hints = []
    for feature in FEATURES:
        a, b = reference[feature], candidate[feature]
        if "uncertain" in {a["visibility"], b["visibility"]}:
            hints.append({"feature": feature, "kind": "insufficient_observation"})
        elif a["visibility"] != b["visibility"]:
            hints.append({"feature": feature, "kind": "presence_disagreement"})
        elif a["observed_count"] is None or b["observed_count"] is None:
            hints.append({"feature": feature, "kind": "insufficient_count"})
        elif a["observed_count"] != b["observed_count"]:
            hints.append({"feature": feature, "kind": "count_disagreement"})
    return {"status": "uncertain", "admission_allowed": False, "hints": hints,
            "reason": "Inventories are unverified model observations; agreement cannot establish physical identity."}


def validate_plan(plan):
    """Only target/pixels reach the model; comparison metadata stays offline."""
    if not isinstance(plan, dict) or not isinstance(plan.get("target"), str) or not plan["target"].strip():
        raise ValueError("Missing target")
    if not isinstance(plan.get("images"), list) or not plan["images"]:
        raise ValueError("Missing images")
    hashes = []
    for image in plan["images"]:
        if not isinstance(image, dict) or not isinstance(image.get("path"), str) or not image["path"]:
            raise ValueError("Invalid image")
        sha = image.get("sha256")
        if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("Invalid image hash")
        hashes.append(sha)
    if len(hashes) != len(set(hashes)):
        raise ValueError("Deduplicate images by SHA")
    if not isinstance(plan.get("comparisons"), list) or not plan["comparisons"]:
        raise ValueError("Missing comparisons")
    ids = []
    for comparison in plan["comparisons"]:
        if not isinstance(comparison, dict) or not isinstance(comparison.get("id"), str) or not comparison["id"]:
            raise ValueError("Invalid comparison")
        if comparison.get("reference_sha256") not in hashes or comparison.get("candidate_sha256") not in hashes:
            raise ValueError("Comparison references an unknown image")
        ids.append(comparison["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate comparison")
    return plan


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--log-dir", required=True)
    parser.add_argument("--plan", help="Explicit target, unique image hashes and offline comparison metadata")
    args = parser.parse_args()
    output, logs = Path(args.output), Path(args.log_dir)
    if output.exists() or logs.exists():
        raise ValueError("Preserve existing output/logs")
    for port in [8080, 8092]:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise ValueError("Wait for 8080 resource clearance" if port == 8080 else "8092 occupied")
    used = H["gpu_memory"]()
    if used > 5288:
        raise ValueError("Less than 7000MiB free VRAM on the documented RTX3060")
    root = Path(__file__).resolve().parents[1]
    if args.plan:
        plan = validate_plan(json.loads(Path(args.plan).read_text(encoding="utf-8")))
    else:
        dataset = json.loads((root / "docs/validation/visual-qa-dataset-2026-10-08.json").read_text(encoding="utf-8"))
        cases = [c for c in dataset["cases"] if c["id"] in {
            "valid_cloth_edit", "continuity_factual_768", "qwen_continuity_factual_768"}]
        images = {}
        comparisons = []
        for c in cases:
            ref = c["contract"]["reference_image"]
            ref_sha = H["digest"](ref)
            for path, sha in [(ref, ref_sha), (c["artifact"], c["sha256"])]:
                images.setdefault(sha, {"path": path, "sha256": sha})
            comparisons.append({"id": c["id"], "original_label": c["expected_verdict"],
                                "reference_sha256": ref_sha, "candidate_sha256": c["sha256"]})
        plan = validate_plan({"target": "silver key", "images": list(images.values()), "comparisons": comparisons})
    images = {image["sha256"]: image for image in plan["images"]}
    for image in images.values():
        payload(image["path"], image["sha256"], plan["target"])
    target_dir = root / "local_image_stack/experiments/bridge/target"
    manifest = json.loads((root / "docs/validation/visual-judge-candidates-assets-2026-10-08.json").read_text(encoding="utf-8"))
    model = next(m for m in manifest["models"] if m["repo"] == "unsloth/Qwen3.5-9B-GGUF")
    weights = [target_dir / "visual-judge-models/Qwen3.5-9B-GGUF" / f["file"] for f in model["files"]]
    for path, artifact in zip(weights, model["files"]):
        if H["digest"](path) != artifact["sha256"]:
            raise ValueError("Model changed")
    logs.mkdir(parents=True)
    log_path = logs / "inventories.log"
    report = {"execution_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "harness_sha256": H["digest"](__file__), "model": model, "runtime": manifest["runtime"],
        "generation_requests": 0, "automatic_retries": 0, "target": plan["target"], "rows": [], "comparisons": [],
        "plan_sha256": H["digest"](args.plan) if args.plan else None,
        "log": str(log_path.resolve()), "policy": {"one_image_per_request": True, "labels_sent": False,
        "reference_role_sent": False, "desired_counts_sent": False, "verdict_requested": False,
        "max_tokens": 512, "timeout_seconds": 60, "context": 8192, "reasoning": "off",
        "flash_attention": "on", "image_min_tokens": 1024, "image_max_tokens": 1536}}
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    server = None
    save()
    command = [str(target_dir / "visual-judge-runtime/b11497/llama-server.exe"), "-m", str(weights[0]),
        "--mmproj", str(weights[1]), "--host", "127.0.0.1", "--port", "8092", "-ngl", "99", "-c", "8192",
        "-np", "1", "-b", "2048", "-ub", "512", "--jinja", "--no-warmup", "--flash-attn", "on",
        "--image-min-tokens", "1024", "--image-max-tokens", "1536", "--reasoning", "off"]
    try:
        started = time.perf_counter()
        with log_path.open("x", encoding="utf-8") as log:
            server = subprocess.Popen(command, stdout=log, stderr=log,
                                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            report["owned_pid"] = server.pid
            while time.perf_counter() - started < 90:
                if server.poll() is not None:
                    raise RuntimeError("Owned server exited during load")
                try:
                    H["request"]("http://127.0.0.1:8092/health", timeout=2)
                    break
                except (OSError, ValueError):
                    time.sleep(1)
            else:
                raise TimeoutError("Readiness timeout")
            report["load_seconds"] = time.perf_counter() - started
            for image in images.values():
                row = {**image, "transport_status": "unavailable"}
                began = time.perf_counter()
                try:
                    response = H["request"]("http://127.0.0.1:8092/v1/chat/completions",
                        payload(image["path"], image["sha256"], report["target"]), timeout=60)
                    choice = response["choices"][0]
                    message = choice["message"]
                    row.update(final_content=message.get("content"), finish_reason=choice["finish_reason"],
                               reasoning_characters=len(message.get("reasoning_content") or ""),
                               usage=response.get("usage"), server_timings=response.get("timings"))
                    if row["finish_reason"] != "stop" or row["reasoning_characters"]:
                        raise ValueError("Incomplete output or reasoning")
                    row["inventory"] = validate(json.loads(row["final_content"]))
                    row["transport_status"] = "completed"
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    row["error_type"] = type(exc).__name__
                finally:
                    row["seconds"] = time.perf_counter() - began
                    report["rows"].append(row)
                    save()
                    print(json.dumps({k: row[k] for k in ["sha256", "transport_status", "seconds"]}), flush=True)
                if row["transport_status"] != "completed":
                    report["stopped_reason"] = "Invalid/unavailable observation; no automatic retry"
                    break
            inventories = {r["sha256"]: r["inventory"] for r in report["rows"] if "inventory" in r}
            for comparison in plan["comparisons"]:
                ref_sha, candidate_sha = comparison["reference_sha256"], comparison["candidate_sha256"]
                if ref_sha in inventories and candidate_sha in inventories:
                    result = compare(inventories[ref_sha], inventories[candidate_sha])
                else:
                    result = {"status": "unavailable", "admission_allowed": False, "hints": []}
                report["comparisons"].append({**comparison, **result})
    except (OSError, ValueError, RuntimeError) as exc:
        report["runtime_error_type"] = type(exc).__name__
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
        report["owned_server_closed"] = server is None or server.poll() is not None
        save()


if __name__ == "__main__":
    main()
