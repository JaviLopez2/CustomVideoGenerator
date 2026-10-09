"""Frozen CPU integration audit: no inference, generation or service control."""
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd().resolve()
sys.path.insert(0, str(ROOT))
from app.services import visual_observation_diagnostics as retained
from app.services import visual_qa as qa
from app.services import klein4b_experimental as klein
from scripts import observe_pairwise_cue as cue_runner
from scripts import pairwise_cue_observations as cue

PLAN = ROOT / "docs/validation/paired-observer-integration-audit-plan-2026-10-09.json"
OUTPUT = ROOT / "docs/validation/paired-observer-integration-audit-result-2026-10-09.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked(binding):
    path = (ROOT / binding["path"]).resolve()
    assert path.is_relative_to(ROOT)
    assert sha(path) == binding["sha256"], binding["path"]
    return path


def main():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    assert plan["protocol"] == "paired-observer-integration-audit-plan-1"
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() == plan["execution_base_head"]
    assert not OUTPUT.exists()
    assert checked(plan["recipe"]) == Path(__file__).resolve()
    paths = {name: checked(binding) for name, binding in plan["sources"].items()}
    for path in paths.values():
        ast.parse(path.read_text(encoding="utf-8"))
    inputs = {name: checked(binding) for name, binding in plan["retained_inputs"].items()}
    frozen = json.loads(inputs["cue_plan"].read_text(encoding="utf-8"))
    preflight = cue_runner.preflight_plan(frozen, ROOT)
    method = preflight["method"]
    prep = json.loads(checked(method["source_preparation"]).read_text(encoding="utf-8"))
    manifest = json.loads(checked(method["artifact_manifest"]).read_text(encoding="utf-8"))
    frame_mapping = []
    for row in manifest["regions"]:
        assert row["coverage_relation"] == "contained"
        frame_mapping.append({"region_id": row["id"], "source_sha256": row["source"]["sha256"],
                              "prepared_sha256": row["crop"]["sha256"], "native_size": row["source"]["size"],
                              "same_file_bytes": row["source"]["sha256"] == row["crop"]["sha256"],
                              "same_native_pixels_verified_by_preflight": True})
    assert any(not row["same_file_bytes"] for row in frame_mapping)
    rejection = []
    for name in ("cue_qwen35", "cue_qwen3vl"):
        report = json.loads(inputs[name].read_text(encoding="utf-8"))
        try:
            retained.RetainedVisualObservations.from_file(inputs[name], sha(inputs[name]))
        except ValueError as exc:
            assert str(exc) == "Unsupported observation protocol"
            rejection.append({"raw_name": name, "protocol": report["protocol"],
                              "single_image_store_result": "rejected_unsupported_protocol"})
        else:
            raise AssertionError("Paired report unexpectedly accepted as single-image inventory")
    invalid = json.loads(inputs["cue_qwen3vl"].read_text(encoding="utf-8"))["rows"][0]
    try:
        cue.validate(json.loads(invalid["final_content"]))
    except ValueError as exc:
        invalid_reason = str(exc)
    else:
        raise AssertionError("Archived invalid cue unexpectedly valid")
    assert invalid_reason == "Cue visibility requires established subject"
    # These are code-interface controls, not new visual measurements or gold.
    control_image = Path(method["cases"][0]["current"]["path"])
    class NoEvidence:
        model_identity = "integration-control-no-runtime"
        def read(self, *args, **kwargs):
            raise AssertionError("Empty contract must not load vision")
    empty = qa.VisualQA(NoEvidence()).assess(control_image, {"subject": "mug"})
    assert empty["status"] == "not_required" and empty["verdict"] == "pass"
    assert not klein.qa_verified(empty)
    valid_row = json.loads(inputs["cue_qwen35"].read_text(encoding="utf-8"))["rows"][1]
    diagnostic = valid_row["diagnostic"]
    assert diagnostic["verdict"] == "uncertain" and not klein.qa_verified(diagnostic)
    assert all(diagnostic[k] is None for k in ("identity_score", "state_score", "progression_score"))
    material_ast = ast.parse(paths["material"].read_text(encoding="utf-8"))
    callers = []
    for node in ast.walk(material_ast):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names = [arg.arg for arg in node.args.args + node.args.kwonlyargs]
            if "visual_observation_store" in names or "scene_qa_contracts" in names:
                callers.append({"function": node.name, "line": node.lineno,
                                "parameters": [p for p in names if p in {"visual_observation_store", "scene_qa_contracts"}]})
    assert len(callers) == 1, callers
    dataset = json.loads(inputs["historical_dataset"].read_text(encoding="utf-8"))
    label_counts = {label: sum(case["expected_verdict"] == label for case in dataset["cases"])
                    for label in ("pass", "fail", "uncertain")}
    result = {"protocol": "paired-observer-integration-audit-result-1", "execution_base_head": plan["execution_base_head"],
              "plan_sha256": sha(PLAN), "source_bindings": plan["sources"], "retained_input_bindings": plan["retained_inputs"],
              "sources_ast_parsed": len(paths), "input_preflight": preflight["preflight"],
              "source_preparation_binding": method["source_preparation"], "frame_mapping": frame_mapping,
              "single_image_store_incompatibility": rejection,
              "invalid_archived_cue_validation": invalid_reason, "empty_contract_control": empty,
              "empty_contract_qa_verified": False, "valid_cue_diagnostic_qa_verified": False,
              "private_injection_points": callers,
              "historical_dataset_labels": {"cases": len(dataset["cases"]), "counts": label_counts,
                                             "independent_human_gold": False, "labels_modified": False},
              "control_scope": "Interface/provenance controls; existing archived observations, no new visual inference",
              "model_requests": 0, "generation_requests": 0, "downloads": 0, "service_changes": 0,
              "application_or_models_or_qa_changed": False, "admission_allowed": False,
              "physical_identity_established": False, "physical_temperature_measured": False,
              "next": "Implement/test experimental offline pair-aware replay with source/role/subject/query bindings; preserve single-image store and MPT admission. No live inference/default wiring."}
    for binding in plan["sources"].values():
        checked(binding)
    for binding in plan["retained_inputs"].values():
        checked(binding)
    with OUTPUT.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2); stream.write("\n")
    print(json.dumps({"result_written": True, "sources_ast_parsed": len(paths),
                      "frames_source_bound": len(frame_mapping), "unsupported_new_reports": len(rejection),
                      "private_injection_points": callers, "new_model_or_generation_requests": 0}))


if __name__ == "__main__":
    main()
