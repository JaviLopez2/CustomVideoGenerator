"""Neutral evidence provenance and region exclusion before model dispatch."""
import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image
import pytest

from scripts import observe_paired_shape as runner
from scripts import prepare_visual_regions as regions


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.fixture
def prepared(tmp_path):
    sources = []
    for name, color in [("red", "red"), ("blue", "blue")]:
        path = tmp_path / f"{name}.png"
        Image.new("RGB", (9, 8), color).save(path)
        sources.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size": [9, 8]})
    prep = {"protocol": "visual-region-preparation-plan-1", "margin_pixels": 0, "regions": [
        {"id": "red", "source": sources[0], "box": [2, 2, 7, 7], "required_box": [2, 2, 7, 7]},
        {"id": "blue", "source": sources[1], "box": [2, 2, 7, 7], "required_box": [2, 2, 7, 7]},
        {"id": "partial", "source": sources[0], "box": [2, 2, 5, 7], "required_box": [2, 2, 7, 7]},
        {"id": "background", "source": sources[0], "box": [0, 0, 1, 1], "required_box": [2, 2, 7, 7]},
    ]}
    manifest = regions.prepare(prep, tmp_path / "crops", workspace_root=tmp_path)
    helper = Path(regions.__file__)
    preparation = write_json(tmp_path / "preparation.json", {"preparation": prep,
        "helper": {"path": str(helper), "sha256": hashlib.sha256(helper.read_bytes()).hexdigest()}})
    manifest_binding = {"path": str(tmp_path / "crops/manifest.json"),
                        "sha256": hashlib.sha256((tmp_path / "crops/manifest.json").read_bytes()).hexdigest()}
    return prep, manifest, preparation, manifest_binding


@pytest.fixture
def plan(tmp_path, prepared):
    _, manifest, preparation, manifest_binding = prepared
    template = Path(__file__).parents[1] / "docs/validation/paired-shape-probe-plan-2026-10-09.json"
    value = json.loads(template.read_text(encoding="utf-8"))
    value["protocol"] = "paired-major-shape-probe-plan-2"
    value.pop("human_review")
    by_id = {row["id"]: row for row in manifest["regions"]}
    value["cases"], declared = [], []
    for case_id, reference, candidate, origin, expected in [
        ("red_self", "red", "red", "byte_identity_control", "not_observed"),
        ("blue_self", "blue", "blue", "byte_identity_control", "not_observed"),
        ("color_pair", "red", "blue", "unlabelled_pair", None),
    ]:
        value["cases"].append({"case_id": case_id,
            "reference": {k: by_id[reference]["crop"][k] for k in ("path", "sha256", "size")},
            "candidate": {k: by_id[candidate]["crop"][k] for k in ("path", "sha256", "size")},
            "reference_region_id": reference, "candidate_region_id": candidate,
            "offline_expectation": {"origin": origin, "expected_major_shape_change": expected, "human_gold": False}})
        declared.append({"id": case_id, "reference_region": reference, "candidate_region": candidate,
                         "expected_major_shape_change": expected})
    excluded = [{"region_id": "partial", "expected_relation": "partial"},
                {"region_id": "background", "expected_relation": "disjoint"}]
    source_result = write_json(tmp_path / "preparation-result.json", {"plan": preparation, "manifest": manifest_binding})
    design = {"protocol": "cross-family-paired-shape-design-1", "planned_cases": declared,
              "artifact_manifest": manifest_binding, "source_preparation": source_result,
              "pre_request_exclusion_controls": [{"region": row["region_id"],
                  "expected_relation": row["expected_relation"], "model_requests": 0} for row in excluded]}
    value.update(evidence_provenance=write_json(tmp_path / "design.json", design),
                 region_preparation=preparation, region_manifest=manifest_binding,
                 excluded_region_controls=excluded, subject="mug")
    from scripts import paired_shape_observations as observer
    value["model_prompt"], value["response_schema"] = observer.prompt("mug"), observer.schema()
    value["execution"]["case_order"] = [row["case_id"] for row in value["cases"]]
    value["assets_manifest"] = write_json(tmp_path / "assets.json", {"models": []})
    return value


def test_v2_accepts_neutral_expectations_without_inventing_human_gold(plan, tmp_path):
    before = copy.deepcopy(plan)
    assert runner.validate_plan(plan) == plan
    result = runner.preflight_plan(plan, tmp_path)
    assert plan == before
    assert result["human_gold"] is False and result["admission_allowed"] is False
    assert result["semantic_human_coverage"] == "pending"
    assert [row["origin"] for row in result["case_expectations"]] == ["byte_identity_control", "byte_identity_control", "unlabelled_pair"]
    assert [row["coverage_relation"] for row in result["excluded_regions"]] == ["partial", "disjoint"]
    assert result["excluded_model_requests"] == 0


@pytest.mark.parametrize("fault", ["human_gold", "control_label", "unlabelled_label", "origin", "missing_expectation", "legacy_review", "legacy_case_label", "missing_regions", "missing_provenance"])
def test_v2_rejects_ambiguous_or_fabricated_evidence(plan, fault):
    runner.validate_plan(plan)  # Ensure a rejection is not just unsupported v2.
    if fault == "human_gold": plan["cases"][2]["offline_expectation"]["human_gold"] = True
    elif fault == "control_label": plan["cases"][0]["offline_expectation"]["expected_major_shape_change"] = "observed"
    elif fault == "unlabelled_label": plan["cases"][2]["offline_expectation"]["expected_major_shape_change"] = "not_observed"
    elif fault == "origin": plan["cases"][0]["offline_expectation"]["origin"] = "assistant_gold"
    elif fault == "missing_expectation": plan["cases"][1].pop("offline_expectation")
    elif fault == "legacy_review": plan["human_review"] = {"path": "pretend-human.json", "sha256": "a" * 64}
    elif fault == "legacy_case_label": plan["cases"][2]["offline_human_review_verbatim"] = "pretend human"
    elif fault == "missing_regions": plan.pop("region_manifest")
    else: plan.pop("evidence_provenance")
    with pytest.raises(ValueError): runner.validate_plan(plan)


def test_byte_control_requires_same_pinned_input(plan, tmp_path):
    runner.preflight_plan(plan, tmp_path)
    plan["cases"][0]["candidate"] = copy.deepcopy(plan["cases"][1]["candidate"])
    plan["cases"][0]["candidate_region_id"] = "blue"
    with pytest.raises(ValueError): runner.preflight_plan(plan, tmp_path)


@pytest.mark.parametrize("binding", ["evidence_provenance", "region_preparation", "region_manifest", "assets_manifest"])
def test_changed_binding_rejected_before_any_request(plan, tmp_path, binding):
    runner.preflight_plan(plan, tmp_path)
    Path(plan[binding]["path"]).write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError): runner.preflight_plan(plan, tmp_path)


def test_changed_original_is_detected_even_if_crop_stays_pinned(plan, tmp_path, prepared):
    runner.preflight_plan(plan, tmp_path)
    Path(prepared[0]["regions"][0]["source"]["path"]).write_bytes(b"changed source")
    with pytest.raises(ValueError): runner.preflight_plan(plan, tmp_path)


@pytest.mark.parametrize("fault", ["wrong_box", "duplicate_id", "false_eligibility", "wrong_plan_hash"])
def test_manifest_claims_are_recomputed_not_trusted(plan, tmp_path, fault):
    runner.preflight_plan(plan, tmp_path)
    path = Path(plan["region_manifest"]["path"])
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if fault == "wrong_box": manifest["regions"][0]["effective_box"] = [0, 0, 5, 5]
    elif fault == "duplicate_id": manifest["regions"][1]["id"] = manifest["regions"][0]["id"]
    elif fault == "false_eligibility": manifest["regions"][2]["whole_declared_region_eligible"] = True
    else: manifest["plan_canonical_sha256"] = "a" * 64
    plan["region_manifest"] = write_json(path, manifest)
    with pytest.raises(ValueError): runner.input_checks.verify_regions(plan, tmp_path)
    with pytest.raises(ValueError): runner.preflight_plan(plan, tmp_path)


def test_forged_crop_hash_cannot_hide_wrong_source_pixels(plan, tmp_path):
    runner.preflight_plan(plan, tmp_path)
    path = Path(plan["region_manifest"]["path"])
    manifest = json.loads(path.read_text(encoding="utf-8"))
    row = manifest["regions"][0]
    Image.new("RGB", (5, 5), "green").save(row["crop"]["path"])
    new_hash = hashlib.sha256(Path(row["crop"]["path"]).read_bytes()).hexdigest()
    row["crop"]["sha256"] = new_hash
    plan["region_manifest"] = write_json(path, manifest)
    for case in plan["cases"]:
        for role in ("reference", "candidate"):
            if case[role + "_region_id"] == "red": case[role]["sha256"] = new_hash
    with pytest.raises(ValueError): runner.input_checks.verify_regions(plan, tmp_path)
    with pytest.raises(ValueError): runner.preflight_plan(plan, tmp_path)


@pytest.mark.parametrize("region_id", ["partial", "background"])
def test_incomplete_region_rejected_before_ports_gpu_or_processes(plan, tmp_path, monkeypatch, region_id):
    runner.preflight_plan(plan, tmp_path)
    manifest = json.loads(Path(plan["region_manifest"]["path"]).read_text(encoding="utf-8"))
    crop = next(row["crop"] for row in manifest["regions"] if row["id"] == region_id)
    plan["cases"][2]["candidate_region_id"] = region_id
    plan["cases"][2]["candidate"] = {k: crop[k] for k in ("path", "sha256", "size")}
    p = tmp_path / "bad-plan.json"; write_json(p, plan)
    output, logs = tmp_path / "report.json", tmp_path / "logs"
    monkeypatch.setattr(sys, "argv", ["runner", "--plan", str(p), "--model-repo", plan["comparison_candidates"][0], "--output", str(output), "--log-dir", str(logs)])
    def forbidden(*args, **kwargs): raise AssertionError("No service/GPU/process before offline preflight")
    monkeypatch.setattr(runner.socket, "socket", forbidden)
    monkeypatch.setattr(runner.base, "gpu_memory", forbidden)
    monkeypatch.setattr(runner.subprocess, "Popen", forbidden)
    with pytest.raises(ValueError): runner.main()
    assert not output.exists() and not logs.exists()


def test_exclusion_controls_cannot_be_silently_dropped(plan, tmp_path):
    runner.preflight_plan(plan, tmp_path)
    plan["excluded_region_controls"] = plan["excluded_region_controls"][:1]
    with pytest.raises(ValueError): runner.preflight_plan(plan, tmp_path)


def test_v1_human_protocol_remains_separate(plan, tmp_path):
    plan["protocol"] = "paired-major-shape-probe-plan-1"
    plan["human_review"] = write_json(tmp_path / "human.json", {"origin": "existing human labels fixture"})
    result = runner.preflight_plan(plan, tmp_path)
    assert result["gold_origin"] == "bound_human_review"
    assert "case_expectations" not in result


def test_neutral_expectations_and_coordinates_never_enter_payload(plan, tmp_path):
    runner.preflight_plan(plan, tmp_path)
    from scripts import paired_shape_observations as observer
    for case in plan["cases"]:
        case["offline_note"] = "OFFLINE_PROVENANCE_SENTINEL"
        body = observer.payload(case["reference"], case["candidate"], plan["subject"])
        encoded = json.dumps(body)
        assert "OFFLINE_PROVENANCE_SENTINEL" not in encoded
        assert "offline_expectation" not in encoded and "region_id" not in encoded


def test_duplicate_json_fields_cannot_redefine_pinned_design(plan, tmp_path):
    runner.preflight_plan(plan, tmp_path)
    path = Path(plan["evidence_provenance"]["path"])
    path.write_text('{"protocol":"cross-family-paired-shape-design-1","protocol":"other"}', encoding="utf-8")
    plan["evidence_provenance"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError): runner.preflight_plan(plan, tmp_path)


@pytest.mark.parametrize("field", ["region_preparation", "region_manifest"])
def test_bindings_must_match_the_frozen_design_not_just_be_internally_valid(plan, tmp_path, field):
    runner.preflight_plan(plan, tmp_path)
    original = Path(plan[field]["path"])
    alias = tmp_path / ("other-" + original.name)
    alias.write_bytes(original.read_bytes())
    plan[field] = {"path": str(alias), "sha256": hashlib.sha256(alias.read_bytes()).hexdigest()}
    with pytest.raises(ValueError): runner.preflight_plan(plan, tmp_path)


@pytest.mark.parametrize("mutation,requests", [(None, 3), ("source_on_load", 0), ("source_after_first", 1), ("crop_after_first", 1)])
def test_main_rechecks_inputs_and_records_actual_http_calls(plan, tmp_path, prepared, monkeypatch, mutation, requests):
    root = tmp_path
    fake_script = root / "scripts/observe_paired_shape.py"
    fake_script.parent.mkdir()
    fake_script.write_text("fixture path binding", encoding="utf-8")
    monkeypatch.setattr(runner, "__file__", str(fake_script))
    target = root / "local_image_stack/experiments/bridge/target"
    repo = plan["comparison_candidates"][0]
    weights = target / "visual-judge-models" / repo.split("/")[-1]
    weights.mkdir(parents=True)
    artifacts = []
    for name in ("model.gguf", "projector.gguf"):
        path = weights / name; path.write_bytes(b"tiny fixture, no model")
        artifacts.append({"file": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    model = {"repo": repo, "files": artifacts}
    plan["assets_manifest"] = write_json(root / "assets.json", {"models": [model], "runtime": {"tag": "fixture"}})
    monkeypatch.setattr(runner, "verify_runtime", lambda *a: {"fixture": True})
    monkeypatch.setattr(runner.base, "gpu_memory", lambda: 0)
    class Port:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def settimeout(self, *a): pass
        def connect_ex(self, *a): return 111
    monkeypatch.setattr(runner.socket, "socket", lambda *a: Port())
    source = Path(prepared[0]["regions"][0]["source"]["path"])
    blue_crop = Path(prepared[1]["regions"][1]["crop"]["path"])
    state, calls = {}, []
    @contextmanager
    def owned(command, log, request_fn, factory, report):
        state["entered"] = True
        report.update(owned_pid=12345, owned_server_closed=False)
        if mutation == "source_on_load": source.write_bytes(b"changed after initial preflight")
        try: yield report
        finally:
            report["owned_server_closed"] = True
            state["closed"] = True
    monkeypatch.setattr(runner, "owned_server", owned)
    def request(url, payload, timeout):
        assert url == "http://127.0.0.1:8092/v1/chat/completions" and timeout == 60
        calls.append(payload)
        if len(calls) == 1:
            if mutation == "source_after_first": source.write_bytes(b"changed between cases")
            elif mutation == "crop_after_first": blue_crop.write_bytes(b"changed between cases")
        answer = {"reference_subject_presence": "present", "candidate_subject_presence": "present",
                  "major_shape_change": "not_observed", "difference_evidence": "Same visible major form"}
        return {"choices": [{"message": {"content": json.dumps(answer)}, "finish_reason": "stop"}]}
    monkeypatch.setattr(runner.base, "request", request)
    p = root / "run-plan.json"; write_json(p, plan)
    output, logs = root / "report.json", root / "logs"
    monkeypatch.setattr(sys, "argv", ["runner", "--plan", str(p), "--model-repo", repo, "--output", str(output), "--log-dir", str(logs)])
    runner.main()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert len(calls) == report["http_model_requests_attempted"] == requests
    assert report["owned_server_closed"] is True and state == {"entered": True, "closed": True}
    assert report["input_preflight"]["human_gold"] is False
    assert report["admission_allowed"] is False and report["physical_identity_established"] is False
    assert report["automatic_retries"] == 0
    assert all("offline_expectation" not in json.dumps(body) for body in calls)
    if mutation:
        assert report["rows"][-1]["transport_status"] == "unavailable"
        assert report["rows"][-1]["error_type"] == "ValueError"
    else:
        assert len(report["rows"]) == 3 and report["unattempted_cases"] == []
