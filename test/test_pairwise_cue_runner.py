"""Pinned cue design/source reconstruction and actual HTTP budget, fake runtime."""
import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image
import pytest

from scripts import observe_pairwise_cue as runner
from scripts import prepare_visual_regions as regions


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.fixture
def plan(tmp_path):
    source_rows = []
    for i, color in enumerate(["red", "blue"]):
        path = tmp_path / f"source{i}.png"; Image.new("RGB", (8, 12), color).save(path)
        src = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size": [8, 12]}
        source_rows.append({"id": f"frame{i}", "source": src, "box": [0, 0, 8, 12], "required_box": [0, 0, 8, 12]})
    preparation = {"protocol": "visual-region-preparation-plan-1", "margin_pixels": 0, "regions": source_rows}
    manifest = regions.prepare(preparation, tmp_path / "frames", workspace_root=tmp_path)
    helper = Path(regions.__file__)
    prep_binding = write_json(tmp_path / "prep.json", {"preparation": preparation,
        "helper": {"path": str(helper), "sha256": hashlib.sha256(helper.read_bytes()).hexdigest()}})
    manifest_binding = {"path": str(tmp_path / "frames/manifest.json"), "sha256": hashlib.sha256((tmp_path / "frames/manifest.json").read_bytes()).hexdigest()}
    result_binding = write_json(tmp_path / "result.json", {"plan": prep_binding, "manifest": manifest_binding})
    d = json.loads((Path(__file__).parents[1] / "docs/validation/pairwise-visible-cue-design-2026-10-09.json").read_text(encoding="utf-8"))
    d.update(source_preparation=result_binding, region_preparation=prep_binding, artifact_manifest=manifest_binding)
    d["assets_manifest"] = write_json(tmp_path / "assets.json", {"models": []})
    for i, c in enumerate(d["cases"]):
        previous, current = (1, 0) if i == 3 else (0, 0 if i == 0 else 1)
        for role, index in [("previous", previous), ("current", current)]:
            c[role + "_region_id"] = f"frame{index}"
            c[role] = {key: manifest["regions"][index]["crop"][key] for key in ("path", "sha256", "size")}
    p = {"protocol": "pairwise-visible-cue-probe-plan-1", "design": write_json(tmp_path / "design.json", d),
         "implementation": {key: {"path": str(Path(path).resolve()), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
                            for key, path in runner.implementation_modules().items()}}
    return p


def change_method(plan, mutator):
    p = Path(plan["design"]["path"]); d = json.loads(p.read_text(encoding="utf-8")); mutator(d)
    plan["design"] = write_json(p, d)


def test_fixed_design_validates_without_mutating_sources_or_inventing_gold(plan, tmp_path):
    before = copy.deepcopy(plan)
    method = runner.validate_plan(plan, tmp_path)
    result = runner.preflight_plan(plan, tmp_path)
    assert plan == before and result["method"] == method
    assert result["preflight"]["regions_verified"] == 2
    assert result["preflight"]["human_gold"] is False and result["preflight"]["admission_allowed"] is False


@pytest.mark.parametrize("fault", ["version", "budget", "retry", "tokens", "thinking", "case_order", "human_gold", "cue_gold", "prompt", "schema", "first_control"])
def test_invalid_method_rejected_before_runtime(plan, tmp_path, fault):
    runner.preflight_plan(plan, tmp_path)
    def mutate(d):
        if fault == "version": d["protocol"] = "other"
        elif fault == "budget": d["execution"]["requests_per_model"] = 5
        elif fault == "retry": d["execution"]["automatic_retries"] = 1
        elif fault == "tokens": d["execution"]["max_tokens"] = 512
        elif fault == "thinking": d["execution"]["thinking"] = True
        elif fault == "case_order": d["cases"][0], d["cases"][1] = d["cases"][1], d["cases"][0]
        elif fault == "human_gold": d["cases"][2]["human_gold"] = True
        elif fault == "cue_gold": d["cases"][2]["expected_cue_visibility"] = "observed"
        elif fault == "prompt": d["model_prompt"] += "Current must show the cue."
        elif fault == "schema": d["response_schema"]["properties"]["temperature"] = {"type": "string"}
        else: d["cases"][0]["evidence_origin"] = "unlabelled_retained_transition"
    change_method(plan, mutate)
    with pytest.raises(ValueError): runner.validate_plan(plan, tmp_path)


def test_changed_code_or_design_binding_rejected(plan, tmp_path):
    runner.preflight_plan(plan, tmp_path)
    plan["implementation"]["observer"]["sha256"] = "a" * 64
    with pytest.raises(ValueError): runner.validate_plan(plan, tmp_path)


def test_region_bindings_must_agree_with_preparation_result(plan, tmp_path):
    runner.preflight_plan(plan, tmp_path)
    def mutate(d):
        original = Path(d["artifact_manifest"]["path"])
        alias = tmp_path / "other-manifest.json"; alias.write_bytes(original.read_bytes())
        d["artifact_manifest"] = {"path": str(alias), "sha256": hashlib.sha256(alias.read_bytes()).hexdigest()}
    change_method(plan, mutate)
    with pytest.raises(ValueError): runner.preflight_plan(plan, tmp_path)


def test_identical_control_requires_identical_inputs(plan, tmp_path):
    runner.preflight_plan(plan, tmp_path)
    def mutate(d):
        d["cases"][0]["current"] = copy.deepcopy(d["cases"][1]["current"])
        d["cases"][0]["current_region_id"] = d["cases"][1]["current_region_id"]
    change_method(plan, mutate)
    with pytest.raises(ValueError): runner.preflight_plan(plan, tmp_path)


def test_changed_original_blocks_even_if_prepared_frame_is_intact(plan, tmp_path):
    runner.preflight_plan(plan, tmp_path)
    d = json.loads(Path(plan["design"]["path"]).read_text(encoding="utf-8"))
    preparation = json.loads(Path(d["region_preparation"]["path"]).read_text(encoding="utf-8"))
    Path(preparation["preparation"]["regions"][0]["source"]["path"]).write_bytes(b"changed original")
    with pytest.raises(ValueError): runner.preflight_plan(plan, tmp_path)


def test_non_fullframe_cannot_be_substituted(plan, tmp_path):
    runner.preflight_plan(plan, tmp_path)
    def mutate(d):
        prep_path = Path(d["region_preparation"]["path"])
        p = json.loads(prep_path.read_text(encoding="utf-8"))
        p["preparation"]["regions"][0]["box"] = [0, 0, 8, 6]
        p["preparation"]["regions"][0]["required_box"] = [0, 0, 8, 6]
        manifest = regions.prepare(p["preparation"], tmp_path / "cropped", workspace_root=tmp_path)
        d["region_preparation"] = write_json(prep_path, p)
        manifest_path = tmp_path / "cropped/manifest.json"
        d["artifact_manifest"] = {"path": str(manifest_path), "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
        d["source_preparation"] = write_json(tmp_path / "result.json", {"plan": d["region_preparation"], "manifest": d["artifact_manifest"]})
        for c in d["cases"]:
            for role in ("previous", "current"):
                index = int(c[role + "_region_id"][-1])
                c[role] = {k: manifest["regions"][index]["crop"][k] for k in ("path", "sha256", "size")}
    change_method(plan, mutate)
    with pytest.raises(ValueError): runner.preflight_plan(plan, tmp_path)


@pytest.mark.parametrize("mutation,requests", [(None, 4), ("source_on_load", 0), ("source_after_first", 1), ("inconsistent_control", 1)])
def test_main_records_http_budget_and_closes_owned_context(plan, tmp_path, monkeypatch, mutation, requests):
    monkeypatch.setattr(runner, "workspace_root", lambda: tmp_path)
    d = json.loads(Path(plan["design"]["path"]).read_text(encoding="utf-8"))
    repo = d["comparison_candidates"][0]
    weights = tmp_path / "local_image_stack/experiments/bridge/target/visual-judge-models" / repo.split("/")[-1]
    weights.mkdir(parents=True)
    artifacts = []
    for name in ("model.gguf", "projector.gguf"):
        p = weights / name; p.write_bytes(b"fixture, no model")
        artifacts.append({"file": name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    d["assets_manifest"] = write_json(tmp_path / "assets.json", {"models": [{"repo": repo, "files": artifacts}], "runtime": {"tag": "fixture"}})
    plan["design"] = write_json(Path(plan["design"]["path"]), d)
    monkeypatch.setattr(runner.shared, "verify_runtime", lambda *args: {"fixture": True})
    monkeypatch.setattr(runner.shared.base, "gpu_memory", lambda: 0)
    class Port:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def settimeout(self, *a): pass
        def connect_ex(self, *a): return 111
    monkeypatch.setattr(runner.socket, "socket", lambda *a: Port())
    prep = json.loads(Path(d["region_preparation"]["path"]).read_text(encoding="utf-8"))
    original = Path(prep["preparation"]["regions"][0]["source"]["path"])
    state, calls = {}, []
    @contextmanager
    def owned(command, log, request_fn, factory, report):
        state["opened"] = True; report.update(owned_pid=12345, owned_server_closed=False)
        if mutation == "source_on_load": original.write_bytes(b"changed on load")
        try: yield report
        finally: state["closed"] = True; report["owned_server_closed"] = True
    monkeypatch.setattr(runner.shared, "owned_server", owned)
    def request(url, body, timeout):
        assert url.endswith('/v1/chat/completions') and timeout == 60
        calls.append(body)
        if mutation == "source_after_first" and len(calls) == 1: original.write_bytes(b"changed between cases")
        value = {"previous_subject_presence": "present", "previous_cue_visibility": "not_observed", "previous_evidence": "No visible requested cue",
                 "current_subject_presence": "present", "current_cue_visibility": "observed" if mutation == "inconsistent_control" else "not_observed", "current_evidence": "Visible area checked"}
        return {"choices": [{"message": {"content": json.dumps(value)}, "finish_reason": "stop"}]}
    monkeypatch.setattr(runner.shared.base, "request", request)
    plan_path = tmp_path / "plan.json"; write_json(plan_path, plan)
    output, logs = tmp_path / "report.json", tmp_path / "logs"
    monkeypatch.setattr(sys, "argv", ["runner", "--plan", str(plan_path), "--model-repo", repo, "--output", str(output), "--log-dir", str(logs)])
    runner.main()
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["http_model_requests_attempted"] == len(calls) == requests
    assert result["owned_server_closed"] is True and state == {"opened": True, "closed": True}
    assert result["admission_allowed"] is False and result["automatic_retries"] == 0
    assert result["input_preflight"]["human_gold"] is False
    if mutation: assert result["rows"][-1]["transport_status"] == "unavailable"
    else: assert len(result["rows"]) == 4 and result["unattempted_cases"] == []


def test_output_outside_workspace_rejected_before_services(plan, tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "workspace_root", lambda: tmp_path)
    p = tmp_path / "plan.json"; write_json(p, plan)
    outside = tmp_path.parent / "do-not-write-cue-report.json"
    monkeypatch.setattr(sys, "argv", ["runner", "--plan", str(p), "--model-repo", "unsloth/Qwen3.5-9B-GGUF", "--output", str(outside), "--log-dir", str(tmp_path / "logs")])
    def forbidden(*a, **k): raise AssertionError("No services for invalid write scope")
    monkeypatch.setattr(runner.shared.base, "gpu_memory", forbidden)
    with pytest.raises(ValueError): runner.main()
    assert not outside.exists()
