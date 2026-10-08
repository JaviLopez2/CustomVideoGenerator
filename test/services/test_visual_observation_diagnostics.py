"""Retained diagnostics cannot rescue or reject scenes; no inference/network."""

import copy
import json
from unittest.mock import Mock

import pytest

from app.config import config
from app.services import material, visual_observation_diagnostics as v
from test.services.test_corrective_continuity import pipeline, item  # noqa: F401


def report_for(image):
    inventory = {"target_presence": {"status": "present", "evidence": "Recorded observation"},
                 "components": {"contact": {"state": "observed", "locations": ["side"], "evidence": "Visible"}}}
    return {"inventory_protocol": "target-component-observations-2", "target": "object",
            "execution_head": "a" * 40, "harness_sha256": "b" * 64,
            "rows": [{"sha256": v.digest(image), "path": "NEVER_FOLLOW_THIS_PATH",
                      "transport_status": "completed", "finish_reason": "stop", "reasoning_characters": 0,
                      "final_content": json.dumps(inventory), "inventory": inventory}],
            "private_settings": "DO_NOT_COPY", "comparisons": [{"verdict": "pass", "admission_allowed": True}]}


def write_store(tmp_path, report):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return v.RetainedVisualObservations.from_file(path, v.digest(path)), path


def test_current_pixels_and_source_hash_bound_to_raw_diagnostic(tmp_path):
    image = tmp_path / "pixels.png"
    image.write_bytes(b"retained pixels")
    report = report_for(image)
    store, path = write_store(tmp_path, report)
    result = v.diagnose(image, store)
    assert result["status"] == "uncertain" and result["available"]
    assert result["source_report_sha256"] == v.digest(path)
    assert result["image_sha256"] == v.digest(image)
    assert result["raw_observation"]["final_content"] == report["rows"][0]["final_content"]
    assert not result["admission_allowed"] and not result["automatic_rejection"]
    assert not result["physical_identity_established"] and not result["pixel_truth_verified"]
    assert "DO_NOT_COPY" not in json.dumps(result) and "NEVER_FOLLOW_THIS_PATH" not in json.dumps(result)
    assert "comparisons" not in result and "verdict" not in result
    # Reads snapshots, not mutable reports or row paths; returned data is isolated.
    path.write_text("changed")
    result["raw_observation"]["final_content"] = "changed"
    assert v.diagnose(image, store)["raw_observation"]["final_content"] == report["rows"][0]["final_content"]
    image.write_bytes(b"different pixels")
    assert v.diagnose(image, store)["reason"] == "no_observation_for_current_pixels"


def test_report_hash_mismatch_is_rejected(tmp_path):
    image = tmp_path / "image"
    image.write_bytes(b"pixels")
    _, path = write_store(tmp_path, report_for(image))
    with pytest.raises(ValueError, match="changed"):
        v.RetainedVisualObservations.from_file(path, "c" * 64)


@pytest.mark.parametrize("mutation", ["protocol", "duplicate", "hash", "oversized_content", "oversized_report", "empty_rows", "missing_target"])
def test_bad_provenance_or_unbounded_report_is_rejected(tmp_path, mutation):
    image = tmp_path / "image"
    image.write_bytes(b"pixels")
    report = report_for(image)
    if mutation == "protocol":
        report["inventory_protocol"] = "unknown"
    elif mutation == "duplicate":
        report["rows"].append(copy.deepcopy(report["rows"][0]))
    elif mutation == "hash":
        report["rows"][0]["sha256"] = "wrong"
    elif mutation == "oversized_content":
        report["rows"][0]["final_content"] = "x" * (v.MAX_CONTENT_CHARACTERS + 1)
    elif mutation == "oversized_report":
        report["private_settings"] = "x" * (v.MAX_REPORT_BYTES + 1)
    elif mutation == "empty_rows":
        report["rows"] = []
    else:
        report["target"] = ""
    with pytest.raises(ValueError):
        write_store(tmp_path, report)


@pytest.mark.parametrize("mutation", ["invalid_json", "truncated", "reasoning", "missing_inventory", "tampered_inventory", "declared_verdict", "failed_transport"])
def test_incomplete_outputs_remain_unavailable_with_raw_failure(tmp_path, mutation):
    image = tmp_path / "image"
    image.write_bytes(b"pixels")
    report = report_for(image)
    row = report["rows"][0]
    if mutation == "invalid_json":
        row["final_content"] = "It looks good, pass!"
    elif mutation == "truncated":
        row["finish_reason"] = "length"
    elif mutation == "reasoning":
        row["reasoning_characters"] = 5
    elif mutation == "missing_inventory":
        del row["inventory"]
    elif mutation == "tampered_inventory":
        row["inventory"]["components"] = {}
    elif mutation == "declared_verdict":
        row["inventory"]["verdict"] = "pass"
        row["final_content"] = json.dumps(row["inventory"])
    else:
        row["transport_status"] = "unavailable"
    store, _ = write_store(tmp_path, report)
    result = v.diagnose(image, store)
    assert result["status"] == "unavailable" and not result["available"]
    assert result["raw_observation"]["final_content"] == row["final_content"]
    assert not result["admission_allowed"] and not result["automatic_rejection"]


def test_invalid_store_or_missing_image_is_bounded_unavailable(tmp_path):
    assert v.diagnose(tmp_path / "missing", object())["reason"] == "invalid_observation_store"
    assert v.diagnose(tmp_path / "missing", v.RetainedVisualObservations())["reason"] == "diagnostic_unavailable"


@pytest.mark.parametrize("qa_verdict", ["pass", "fail", "uncertain", "unavailable"])
@pytest.mark.parametrize("observation", ["valid", "invalid", "no_match", "missing_pixels"])
def test_caller_diagnostic_does_not_change_qa_admission(pipeline, monkeypatch, tmp_path, qa_verdict, observation):
    run, diagnostics = pipeline
    monkeypatch.setitem(config.app, "openai_image_visual_qa_experimental_enabled", True)
    image = tmp_path / "candidate.png"
    image.write_bytes(b"retained candidate")
    report = report_for(image)
    if observation == "invalid":
        report["rows"][0]["final_content"] = "not JSON"
    store, _ = write_store(tmp_path, report)
    if observation == "no_match":
        image.write_bytes(b"new candidate")
    elif observation == "missing_pixels":
        image.unlink()
    generated = item("unused")
    generated.url = str(image)
    generated.source_info["model"] = "flux-klein-4b-t2i-exp"
    generation = Mock(return_value=[generated])
    monkeypatch.setattr(material, "generate_images_openai", generation)
    engine = Mock()
    engine.assess.return_value = {"verdict": qa_verdict, "available": qa_verdict != "unavailable"}
    monkeypatch.setattr(material, "_new_visual_qa_engine", Mock(return_value=engine))
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": False})
    result = run(search_terms=["object"], scene_routes=["standard"], scene_subjects=["object"],
                 scene_qa_contracts=[{"identity_critical": True}], visual_observation_store=store)
    assert bool(result) == (qa_verdict == "pass")
    assert generation.call_count == engine.assess.call_count == 1
    diagnostic = diagnostics[-1]["plan_scenes"][0]["visual_observation_diagnostic"]
    assert diagnostic["status"] == ("uncertain" if observation == "valid" else "unavailable")
    assert diagnostic["candidate_stage"] == "before_semantic_qa"
    assert not diagnostic["admission_allowed"] and not diagnostic["automatic_rejection"]
    assert generated.source_info["visual_qa"]["verdict"] == qa_verdict


def test_default_caller_never_reads_retained_diagnostics(pipeline, monkeypatch):
    run, diagnostics = pipeline
    monkeypatch.setattr(material, "generate_images_openai", Mock(return_value=[item("default")]))
    reader = Mock(side_effect=AssertionError("unexpected diagnostic read"))
    monkeypatch.setattr(v, "diagnose", reader)
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": False})
    assert run(search_terms=["object"], scene_routes=["standard"])
    reader.assert_not_called()
    assert "visual_observation_diagnostic" not in diagnostics[-1]["plan_scenes"][0]


def test_valid_diagnostic_alone_cannot_verify_experimental_scene(pipeline, monkeypatch, tmp_path):
    run, diagnostics = pipeline
    monkeypatch.setitem(config.app, "openai_image_visual_qa_experimental_enabled", False)
    image = tmp_path / "candidate.png"
    image.write_bytes(b"retained pixels")
    store, _ = write_store(tmp_path, report_for(image))
    generated = item("unused")
    generated.url = str(image)
    generated.source_info["model"] = "flux-klein-4b-t2i-exp"
    generation = Mock(return_value=[generated])
    monkeypatch.setattr(material, "generate_images_openai", generation)
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": False})
    assert run(search_terms=["object"], scene_routes=["standard"], visual_observation_store=store) == []
    assert generation.call_count == 1
    assert diagnostics[-1]["plan_scenes"][0]["visual_observation_diagnostic"]["status"] == "uncertain"
    assert diagnostics[-1]["plan_scenes"][0]["experimental_qa_status"] == "unverified_rejected"


def test_coordinate_protocol_remains_raw_uncertain_diagnostic(tmp_path):
    image = tmp_path / "image"
    image.write_bytes(b"pixels")
    report = report_for(image)
    report["inventory_protocol"] = "target-location-observations-1"
    report["rows"][0]["inventory"]["components"]["contact"]["locations"] = [
        {"box": [100, 100, 200, 200], "evidence": "Visible site"}]
    report["rows"][0]["final_content"] = json.dumps(report["rows"][0]["inventory"])
    store, _ = write_store(tmp_path, report)
    result = v.diagnose(image, store)
    assert result["status"] == "uncertain" and result["available"]
    assert not result["pixel_truth_verified"] and not result["admission_allowed"]
