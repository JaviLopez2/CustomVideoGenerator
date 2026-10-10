"""One declared blind cohort and a new human-reviewed fusion pair; no generation."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import runpy
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import evaluate_multimodal_judges as qa
from scripts import observe_paired_shape as shared
from scripts import paired_shape_observations as shape
from scripts import paired_shape_preflight as checks

VL = "Qwen/Qwen3-VL-8B-Instruct-GGUF"
Q35 = "unsloth/Qwen3.5-9B-GGUF"
IDS = ["valid_cloth_edit", "mpt_t2i_text_contract_768", "mpt_explicit_quantity_seed43", "z_image_t2i_768"]
BUDGET = {"new_blind_requests": 4, "new_pair_requests_per_model": 1, "maximum_requests_total": 6,
          "automatic_retries": 0, "generation_requests": 0, "downloads": 0,
          "stop_each_cohort_at_first_invalid_or_unavailable": True}
RESOURCE_RECIPE = ROOT / "docs/validation/adjacent-cue-recipe-2026-10-09.py"


def fingerprint(value):
    return hashlib.sha256(checks.canonical(value).encode()).hexdigest()


def blind_payload(case):
    parts, inputs = qa.content(case, blind_counts=True)
    body = {"model": "visual-judge", "messages": [{"role": "user", "content": parts}],
            "max_tokens": 768, "temperature": 0,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "visual_qa", "strict": True, "schema": qa.response_schema(case["contract"], concise=False)}},
            "chat_template_kwargs": {"enable_thinking": False}}
    return body, inputs


def verify(plan_path):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    if plan.get("protocol") != "clock-blind-and-fusion-plan-1" or plan.get("case_order") != IDS:
        raise ValueError("Unknown or reordered cohort")
    budget = plan.get("budget")
    if (not isinstance(budget, dict) or set(budget) != set(BUDGET)
            or any(type(budget[k]) is not type(v) or budget[k] != v for k, v in BUDGET.items())):
        raise ValueError("Changed fixed budget")
    if plan.get("comparison_candidates") != [VL, Q35] or plan.get("new_blind_candidate") != VL:
        raise ValueError("New blind cohort belongs exclusively to the pinned Qwen3-VL")
    for field, path in (("recipe", Path(__file__)), ("qa_implementation", Path(qa.__file__)),
                        ("shape_implementation", Path(shape.__file__)), ("shared_runner", Path(shared.__file__)),
                        ("input_checks", Path(checks.__file__)), ("resource_recipe", RESOURCE_RECIPE)):
        if checks.binding_path(plan[field], ROOT) != path.resolve():
            raise ValueError("Unknown implementation path")
        checks.checked_bytes(plan[field], ROOT)
    dataset = checks.checked_json(plan["dataset"], ROOT)
    archive = checks.checked_json(plan["archived_qwen35"], ROOT)
    review = checks.checked_json(plan["human_review"], ROOT)
    assets = checks.checked_json(plan["assets_manifest"], ROOT)
    if archive["harness_sha256"] != plan["qa_implementation"]["sha256"]:
        raise ValueError("Historic request implementation changed")
    if (archive["policy"] != plan["blind_policy"] or archive["runtime"] != assets["runtime"]
            or plan.get("shape_prompt") != shape.prompt("silver key") or plan.get("shape_schema") != shape.schema()):
        raise ValueError("Changed decoding/prompt/runtime")
    cases = [c for c in dataset["cases"] if c["id"] in IDS]
    if [c["id"] for c in cases] != IDS:
        raise ValueError("Missing clock sources")
    old = next(m for m in archive["models"] if m["repo"] == Q35)
    model = shared.select_model(assets, Q35)
    if old["revision"] != model["revision"]:
        raise ValueError("Archived model revision differs")
    for case, declared in zip(cases, plan["blind_inputs"]):
        body, inputs = blind_payload(case)
        row = next(r for r in old["rows"] if r["id"] == case["id"])
        if (declared != {"case_id": case["id"], "request_sha256": fingerprint(body), "inputs": inputs}
                or row["inputs"] != inputs or row["finish_reason"] != "stop" or row["reasoning_characters"] != 0):
            raise ValueError("Historic source roles or reconstructed request differ")
    pair = plan["fusion_pair"]
    expected = {"case_id": "clock_human_fusion_pair", "reference": plan["reviewed_sources"][0],
                "candidate": plan["reviewed_sources"][2]}
    if pair != expected:
        raise ValueError("Fusion pair source/order differs")
    # Human labels remain offline. Only the generic target/prompt and two PNGs are sent.
    for case, source in zip(cases, plan["reviewed_sources"]):
        if case["artifact"] != source["path"] or case["sha256"] != source["sha256"]:
            raise ValueError("Reviewed candidate differs")
        from PIL import Image
        with Image.open(source["path"]) as image:
            if image.format != "PNG" or list(image.size) != source["size"]:
                raise ValueError("Reviewed PNG dimensions differ")
    body = shape.payload(pair["reference"], pair["candidate"], "silver key")
    if fingerprint(body) != plan["fusion_request_sha256"]:
        raise ValueError("Changed generic paired request")
    if (review.get("protocol") != "independent-clock-visible-count-human-review-1"
            or review.get("human_review_status") != "received"
            or [{"case_id": r["case_id"], "source": r["source"]} for r in review["rows"]]
                != [{"case_id": c["id"], "source": s} for c, s in zip(cases, plan["reviewed_sources"]) ]):
        raise ValueError("Unknown independent review")
    return plan, cases, assets


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--verify-only", action="store_true")
    for field in ("model-repo", "output", "log-dir"):
        parser.add_argument("--" + field)
    args = parser.parse_args()
    plan_path = Path(args.plan).resolve()
    plan, cases, assets = verify(plan_path)
    if args.verify_only:
        print(json.dumps({"verified": True, "blind_cases": len(cases), "new_pair_contexts": 1, "http_requests": 0}))
        return
    if args.model_repo not in plan["comparison_candidates"] or not args.output or not args.log_dir:
        raise ValueError("Declare an existing model and fresh output/logs")
    output, logs = Path(args.output).resolve(), Path(args.log_dir).resolve()
    declared_output = plan["outputs"][args.model_repo]
    if output != (ROOT / declared_output["report"]).resolve() or logs != (ROOT / declared_output["logs"]).resolve():
        raise ValueError("Execution paths differ from the one declared cohort per candidate")
    if any(p == ROOT or not p.is_relative_to(ROOT) or p.exists() for p in (output, logs)):
        raise ValueError("Preserve previous outputs/logs")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if head != plan["execution_base_head"]:
        raise ValueError("Execution HEAD changed since declaration")
    snapshot = runpy.run_path(str(RESOURCE_RECIPE))["resources"]()
    if (any(snapshot["ports_open"].values()) or snapshot["ram_free_gib"] < 12
            or snapshot["gpu"]["used_mib"] > 5288 or snapshot["gpu"]["utilization_percent"] > 30):
        raise ValueError("Port/RAM/VRAM/GPU-load preflight prevents the bounded queries")
    model = shared.select_model(assets, args.model_repo)
    target = ROOT / "local_image_stack/experiments/bridge/target"
    runtime_root = target / "visual-judge-runtime"
    runtime = shared.verify_runtime(runtime_root, assets["runtime"])
    weights = [target / "visual-judge-models" / model["repo"].split("/")[-1] / item["file"] for item in model["files"]]
    if any(qa.digest(p) != item["sha256"] for p, item in zip(weights, model["files"])):
        raise ValueError("Pinned model/projector changed")
    logs.mkdir(parents=True, exist_ok=False)
    report = {"protocol": "clock-blind-and-fusion-result-1", "execution_head": head,
              "plan": {"path": str(plan_path), "sha256": qa.digest(plan_path)},
              "recipe": plan["recipe"], "model": model, "runtime": runtime,
              "resource_preflight": snapshot, "blind_policy": plan["blind_policy"],
              "blind_rows": [], "pair_rows": [], "http_model_requests_attempted": 0,
              "automatic_retries": 0, "generation_requests": 0, "downloads": 0,
              "admission_allowed": False, "physical_identity_established": False,
              "human_labels_sent": False, "owned_server_closed": True}
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    def send(body):
        if qa.digest(plan_path) != report["plan"]["sha256"]:
            raise ValueError("Declared plan changed during execution")
        verify(plan_path)
        maximum = 5 if args.model_repo == VL else 1
        if report["http_model_requests_attempted"] >= maximum:
            raise ValueError("Fixed no-retry query budget exhausted")
        report["http_model_requests_attempted"] += 1
        save()
        return qa.request("http://127.0.0.1:8092/v1/chat/completions", body, timeout=60)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write("\n")
    try:
        with shared.owned_server(shared.command(runtime_root / assets["runtime"]["tag"] / "llama-server.exe", weights),
                                 logs / "server.log", qa.request, subprocess.Popen, report):
            save()
            if args.model_repo == VL:
                for case in cases:
                    body, inputs = blind_payload(case)
                    row = {"case_id": case["id"], "inputs": inputs, "request_sha256": fingerprint(body),
                           "transport_status": "unavailable"}
                    started = time.perf_counter()
                    try:
                        reply = send(body)
                        row["raw_response"] = copy.deepcopy(reply)
                        if not isinstance(reply, dict):
                            raise ValueError("Expected one response object")
                        choices = reply.get("choices")
                        if not isinstance(choices, list) or len(choices) != 1:
                            raise ValueError("Expected one completed choice")
                        choice = choices[0]; message = choice["message"]
                        row.update(final_content=message.get("content"), finish_reason=choice.get("finish_reason"),
                                   reasoning_characters=len(message.get("reasoning_content") or ""),
                                   usage=reply.get("usage"), server_timings=reply.get("timings"))
                        if row["finish_reason"] != "stop" or row["reasoning_characters"]:
                            raise ValueError("Incomplete final output or unexpected reasoning")
                        row["historical_contract_result"] = qa.normalize(json.loads(row["final_content"]), case["contract"])
                        row["transport_status"] = "completed"
                    except (OSError, ValueError, KeyError, TypeError) as exc:
                        row["error_type"] = type(exc).__name__
                    finally:
                        row["seconds"] = time.perf_counter() - started
                        report["blind_rows"].append(row); save()
                        print(json.dumps({k: row[k] for k in ("case_id", "transport_status", "seconds")}), flush=True)
                    if row["transport_status"] != "completed":
                        report["blind_stop_reason"] = "First invalid/unavailable; no retry or tuning"
                        break
            # Separate predeclared paired cohort, same existing generic shape protocol.
            def done(row):
                report["pair_rows"].append(row); save()
                print(json.dumps({k: row[k] for k in ("case_id", "transport_status", "seconds")}), flush=True)
            shape.collect([plan["fusion_pair"]], "silver key", send, done)
    except (OSError, ValueError, RuntimeError) as exc:
        report["runtime_error_type"] = type(exc).__name__
    finally:
        with socket.socket() as connection:
            connection.settimeout(1)
            report["port_8092_open_after"] = connection.connect_ex(("127.0.0.1", 8092)) == 0
        report["unattempted_blind_cases"] = [c["id"] for c in cases[len(report["blind_rows"]):]] if args.model_repo == VL else []
        report["unattempted_pair_cases"] = [] if report["pair_rows"] else [plan["fusion_pair"]["case_id"]]
        save()


if __name__ == "__main__":
    main()
