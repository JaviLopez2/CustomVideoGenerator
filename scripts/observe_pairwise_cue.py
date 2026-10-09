"""Fixed experimental visible-cue cohort; no MPT integration/generation."""
import argparse
import json
from pathlib import Path
import socket
import subprocess
from scripts import pairwise_cue_observations as observer
from scripts import observe_paired_shape as shared
from scripts import paired_shape_preflight as checks
from scripts import observe_visual_geometry as selector

def workspace_root():
    return Path(__file__).resolve().parents[1]

def implementation_modules():
    return {"runner": __file__, "observer": observer.__file__, "shared_runner": shared.__file__,
            "region_checks": checks.__file__, "region_helper": checks.regions.__file__, "png_loader": observer.images.__file__,
            "transport": shared.base.__file__, "model_selector": selector.__file__}

def validate_plan(plan, root):
    if not isinstance(plan, dict) or plan.get("protocol") != "pairwise-visible-cue-probe-plan-1":
        raise ValueError("Unknown visible-cue plan")
    bindings = plan.get("implementation")
    modules = implementation_modules()
    if not isinstance(bindings, dict) or set(bindings) != set(modules):
        raise ValueError("Missing implementation bindings")
    for name, path in modules.items():
        binding = bindings[name]
        if checks.binding_path(binding, root) != Path(path).resolve():
            raise ValueError("Implementation path changed")
        checks.checked_bytes(binding, root)
    method = checks.checked_json(plan.get("design"), root)
    if not isinstance(method, dict) or method.get("protocol") != "pairwise-visible-cue-design-1" or "human_review" in method:
        raise ValueError("Unknown or fabricated cue design")
    expected = {"requests_per_model": 4, "maximum_requests_total": 8, "automatic_retries": 0,
                "port": 8092, "context": 8192, "parallel": 1, "max_tokens": 256, "temperature": 0,
                "thinking": False, "min_image_tokens": 1024, "max_image_tokens": 1536, "http_timeout_seconds": 60,
                "separate_sequential_owned_servers": True, "stop_at_first_invalid_or_unavailable": True,
                "new_generation_requests": 0, "new_downloads": 0}
    execution = method.get("execution", {})
    for name, value in expected.items():
        if type(execution.get(name)) is not type(value) or execution[name] != value:
            raise ValueError("Changed fixed cue budget/decoding")
    cases = method.get("cases")
    if not isinstance(cases, list) or len(cases) != 4 or any(not isinstance(c, dict) for c in cases):
        raise ValueError("Four declared cases required")
    ids = [case.get("case_id") for case in cases]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != 4 or ids != execution.get("case_order"):
        raise ValueError("Duplicate or reordered cue cases")
    for i, case in enumerate(cases):
        origin = "exact_input_control" if i == 0 else "unlabelled_retained_transition"
        if (case.get("evidence_origin") != origin or case.get("human_gold") is not False
                or "expected_cue_visibility" not in case or case["expected_cue_visibility"] is not None
                or "expected_visible_transition" not in case
                or case["expected_visible_transition"] != ("no_visible_change" if i == 0 else None)
                or case.get("historical_temperature_or_identity_label_sent") is not False):
            raise ValueError("Invalid cue evidence origin")
    if method.get("comparison_candidates") != list(selector.MODEL_REPOS):
        raise ValueError("Only the two existing candidates allowed")
    if method.get("model_prompt") != observer.prompt(method.get("subject"), method.get("cue_query")) or method.get("response_schema") != observer.schema():
        raise ValueError("Changed declared generic prompt/schema")
    return method

def preflight_plan(plan, root):
    method = validate_plan(plan, root)
    checks.checked_json(method["assets_manifest"], root)
    result = checks.checked_json(method["source_preparation"], root)
    if (not checks.same_binding(result["plan"], method["region_preparation"], root)
            or not checks.same_binding(result["manifest"], method["artifact_manifest"], root)):
        raise ValueError("Cue frames differ from preparation result")
    verified = checks.verify_regions({"region_preparation": method["region_preparation"],
                                      "region_manifest": method["artifact_manifest"]}, root)
    for row in verified.values():
        full = [0, 0, *row["source"]["size"]]
        if (row["effective_box"] != full or row["required_box"] != full or row["requested_box"] != full
                or row["coverage_relation"] != "contained" or row["whole_declared_region_eligible"] is not True):
            raise ValueError("Cue protocol requires native full frames")
    for i, case in enumerate(method["cases"]):
        for role in ("previous", "current"):
            row = verified.get(case.get(role + "_region_id"))
            image = case.get(role)
            if (row is None or not isinstance(image, dict)
                    or checks.binding_path(image, root) != checks.binding_path(row["crop"], root)
                    or image["sha256"] != row["crop"]["sha256"]
                    or checks.canonical(image["size"]) != checks.canonical(row["crop"]["size"])):
                raise ValueError("Cue case differs from pinned full frame")
        if i == 0 and case["previous"]["sha256"] != case["current"]["sha256"]:
            raise ValueError("Exact-input control differs")
        observer.payload(case["previous"], case["current"], method["subject"], method["cue_query"])
    return {"method": method, "preflight": {"protocol": "pairwise-cue-input-preflight-1",
            "regions_verified": len(verified), "native_fullframe_pixels_verified": True,
            "human_gold": False, "semantic_human_coverage": "pending", "admission_allowed": False,
            "physical_identity_established": False, "physical_temperature_measured": False}}

def main():
    parser = argparse.ArgumentParser(__doc__)
    for name in ("plan", "model-repo", "output", "log-dir"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    root = workspace_root().resolve()
    output, logs = Path(args.output).resolve(), Path(args.log_dir).resolve()
    if any(not p.is_relative_to(root) or p == root for p in (output, logs)):
        raise ValueError("Output/logs escape workspace")
    if output.exists() or logs.exists():
        raise FileExistsError("Preserve existing reports/logs; no retry")
    plan = checks.checked_json({"path": str(Path(args.plan).resolve()), "sha256": shared.base.digest(args.plan)}, root)
    inputs = preflight_plan(plan, root); method = inputs["method"]
    if args.model_repo not in method["comparison_candidates"]:
        raise ValueError("Undeclared cue model")
    for port in (8080, 8092):
        with socket.socket() as s:
            s.settimeout(1)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                raise ValueError("8080/8092 must be free")
    if shared.base.gpu_memory() > 5288:
        raise ValueError("Less than7000MiB free on documented RTX3060")
    assets = checks.checked_json(method["assets_manifest"], root)
    model = shared.select_model(assets, args.model_repo)
    target = root / "local_image_stack/experiments/bridge/target"
    runtime_root = target / "visual-judge-runtime"
    runtime = shared.verify_runtime(runtime_root, assets["runtime"])
    weights = [target / "visual-judge-models" / model["repo"].split("/")[-1] / item["file"] for item in model["files"]]
    for path, artifact in zip(weights, model["files"]):
        if shared.base.digest(path) != artifact["sha256"]:
            raise ValueError("Model bytes changed")
    logs.mkdir(parents=True, exist_ok=False)
    report = {"protocol": observer.VERSION, "execution_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "plan_sha256": shared.base.digest(args.plan), "design": plan["design"], "implementation": plan["implementation"],
              "model": model, "runtime": runtime, "input_preflight": inputs["preflight"], "subject": method["subject"],
              "cue_query": method["cue_query"], "rows": [], "http_model_requests_attempted": 0,
              "automatic_retries": 0, "generation_requests": 0, "owned_server_closed": False,
              "admission_allowed": False, "physical_identity_established": False, "physical_temperature_measured": False,
              "policy": {"labels_sent": False, "case_names_sent": False, "full_native_frames": True,
                         "max_tokens": 256, "thinking": False, "scores_separate_and_null": True}}
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with output.open("x", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2); f.write("\n")
    def done(row):
        report["rows"].append(row); save()
        print(json.dumps({k: row[k] for k in ("case_id", "transport_status", "seconds")}), flush=True)
    def request(body):
        preflight_plan(plan, root)
        report["http_model_requests_attempted"] += 1
        return shared.base.request("http://127.0.0.1:8092/v1/chat/completions", body, timeout=60)
    try:
        with shared.owned_server(shared.command(runtime_root / assets["runtime"]["tag"] / "llama-server.exe", weights),
                                 logs / "server.log", shared.base.request, subprocess.Popen, report):
            save()
            observer.collect(method["cases"], method["subject"], method["cue_query"], request, done)
    except (OSError, ValueError, RuntimeError) as exc:
        report["runtime_error_type"] = type(exc).__name__
    finally:
        with socket.socket() as s:
            s.settimeout(1); report["port_8092_open_after"] = s.connect_ex(("127.0.0.1", 8092)) == 0
        report["requests_attempted"] = sum(row["request_attempted"] for row in report["rows"])
        report["unattempted_cases"] = [c["case_id"] for c in method["cases"][len(report["rows"]):]]
        save()


if __name__ == "__main__":
    main()
