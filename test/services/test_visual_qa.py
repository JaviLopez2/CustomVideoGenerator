"""Local evidence contracts and bounded judge policy; no model/network execution."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from app.services import llm, visual_qa as qa
from app.services import material
from app.config import config
from test.services.test_corrective_continuity import pipeline, item  # noqa: F401


@pytest.mark.parametrize("caption,expected,status", [
    ("Two handles are visible.", 2, "pass"),
    ("Two handles are visible.", 1, "fail"),
    ("No handles are visible.", 1, "fail"),
    ("The handles are partly obscured.", 2, "uncertain"),
    ("One handle or two handles may be present.", 1, "uncertain"),
    ("Two bottles beside a single handle.", 1, "pass"),
])
def test_exact_count_scope(caption, expected, status):
    assert qa.quantity(caption, {}, {"subject": "handles", "expected_count": expected})["status"] == status


def test_indefinite_article_is_not_enough_for_exact_count():
    assert qa.quantity("A tool is visible.", {}, {"subject": "tool", "expected_count": 1})["status"] == "uncertain"
    assert qa.quantity("A tool is visible.", {"labels": ["tool"]}, {"subject": "tool", "expected_count": 1})["status"] == "pass"


def test_detections_and_caption_conflict_stays_uncertain():
    assert qa.quantity("One bottle.", {"labels": ["bottle", "bottle"]},
                       {"subject": "bottle", "expected_count": 1})["status"] == "uncertain"


def test_disjunction_without_repeated_subject_is_ambiguous():
    assert qa.quantity("One or two bottles may be visible.", {},
                       {"subject": "bottle", "expected_count": 1})["status"] == "uncertain"


@pytest.mark.parametrize("value", [-1, True, "2"])
def test_count_contract_invalid(value):
    with pytest.raises(ValueError):
        qa.quantity("Two objects.", {}, {"subject": "objects", "expected_count": value})


@pytest.mark.parametrize("caption,status", [
    ("The surface shows frost.", "pass"),
    ("The surface is blue in different lighting.", "uncertain"),
    ("There is no frost on the surface.", "fail"),
])
def test_state_is_not_identity_or_lighting(caption, status):
    result = qa.state_check(caption, {"required_evidence": ["frost"]})
    assert result["status"] == status and result["identity_score"] is None


def test_absence_is_not_inferred_from_omission():
    contract = {"forbidden_evidence": ["smoke"]}
    assert qa.state_check("A container is visible.", contract)["status"] == "uncertain"
    assert qa.state_check("Smoke rises from the container.", contract)["status"] == "fail"
    assert qa.state_check("The container is visible without smoke.", contract)["status"] == "pass"


def test_progression_requires_previous_evidence():
    contract = {"required_evidence": ["frost"]}
    result = qa.state_check("The surface has frost.", contract, "The surface has no frost.")
    assert result["progression_score"] == 1
    unchanged = qa.state_check("The surface has frost.", contract, "The surface already has frost.")
    assert unchanged["progression_score"] is None


def test_shape_not_pixel_similarity():
    shape = {"size": [100, 100], "polygons": [[20, 10, 40, 10, 40, 90, 20, 90]]}
    moved = {"size": [200, 200], "polygons": [[60, 20, 100, 20, 100, 180, 60, 180]]}
    assert qa.silhouette(shape, moved)["status"] == "pass"
    distorted = {"size": [100, 100], "polygons": [[10, 10, 90, 10, 90, 90, 10, 90]]}
    assert qa.silhouette(shape, distorted)["status"] != "pass"
    assert qa.silhouette({"size": [100, 100], "polygons": []}, shape)["status"] == "uncertain"


def test_native_grouped_polygon_instances_are_not_discarded():
    ring = [20, 10, 40, 10, 40, 90, 20, 90]
    flat = {"size": [100, 100], "polygons": [ring]}
    native = {"size": [100, 100], "polygons": [[ring]]}
    assert qa.silhouette(flat, native)["status"] == "pass"
    assert qa.normalized_mask([[], [[float("nan"), 1]]], [100, 100]) is None


def test_critical_identity_cannot_be_certified_by_exact_count(image):
    result = qa.VisualQA(Evidence()).assess(image, {"identity_critical": True,
        "counts": [{"subject": "object", "expected_count": 1}]})
    assert result["verdict"] == "uncertain"
    assert result["checks"][0]["identity_score"] is None


class Evidence:
    model_identity = "fake-local-v1"
    def __init__(self, caption="One object is visible."):
        self.caption = caption
        self.calls = []
    def read(self, image, task="<MORE_DETAILED_CAPTION>", query="", crop=None):
        self.calls.append((str(image), task, query))
        value = self.caption if task == "<MORE_DETAILED_CAPTION>" else {"labels": ["object"], "bboxes": [[0, 0, 10, 10]]}
        return {"available": True, "value": value, "size": [20, 20]}


@pytest.fixture
def image(tmp_path):
    path = tmp_path / "artifact.png"
    Image.new("RGB", (20, 20), "red").save(path)
    return path


def test_no_requirements_no_vision_calls(image):
    evidence = Evidence()
    result = qa.VisualQA(evidence).assess(image, {"subject": "object"})
    assert result["status"] == "not_required" and evidence.calls == []


def test_count_only_does_not_run_temporal_or_segmentation(image):
    evidence = Evidence()
    result = qa.VisualQA(evidence).assess(image, {"counts": [{"subject": "object", "expected_count": 1}]})
    assert result["verdict"] == "pass"
    assert [call[1] for call in evidence.calls] == ["<MORE_DETAILED_CAPTION>", "<OD>"]


def test_clear_fail_short_circuits_expensive_checks(image):
    evidence = Evidence("Two objects are visible.")
    evidence.read = Mock(side_effect=[{"available": True, "value": evidence.caption},
                                     {"available": True, "value": {"labels": ["object", "object"]}}])
    result = qa.VisualQA(evidence).assess(image, {
        "counts": [{"subject": "objects", "expected_count": 1}], "forbid_text": True,
        "geometry_constraints": ["silhouette"], "reference_image": str(image),
        "temporal": {"required_evidence": ["frost"]},
    })
    assert result["verdict"] == "fail" and evidence.read.call_count == 2


def test_result_cache_image_contract_model_invalidation(image):
    evidence = Evidence()
    engine = qa.VisualQA(evidence)
    contract = {"counts": [{"subject": "object", "expected_count": 1}]}
    assert not engine.assess(image, contract)["cache_hit"]
    assert engine.assess(image, contract)["cache_hit"]
    assert len(evidence.calls) == 2
    altered = {"counts": [{"subject": "object", "expected_count": 2}]}
    assert not engine.assess(image, altered)["cache_hit"]
    evidence.model_identity = "fake-local-v2"
    assert not engine.assess(image, contract)["cache_hit"]
    Image.new("RGB", (20, 20), "blue").save(image)
    assert not engine.assess(image, contract)["cache_hit"]


def test_unavailable_and_empty_caption_not_accepted_or_cached(image):
    evidence = Evidence("")
    engine = qa.VisualQA(evidence)
    contract = {"counts": [{"subject": "object", "expected_count": 1}]}
    assert engine.assess(image, contract)["verdict"] == "unavailable"
    assert not engine.assess(image, contract)["cache_hit"]
    assert len(evidence.calls) == 2
    assert engine.assess(image.with_name("missing.png"), contract)["verdict"] == "unavailable"


def test_unknown_is_never_pass(image):
    result = qa.VisualQA(Evidence("The object is partly obscured.")).assess(image,
        {"counts": [{"subject": "object", "expected_count": 2}]})
    assert result["verdict"] == "uncertain"


def test_bad_contract_and_missing_model_are_unavailable(image):
    result = qa.VisualQA(Evidence()).assess(image, {"counts": [{"subject": "object"}]})
    assert result["verdict"] == "unavailable"
    missing = qa.FlorenceEvidence(lambda: None, "missing-local-model")
    assert not missing.read(image)["available"]
    assert not missing.cache.entries


def test_reference_and_previous_bytes_invalidate_result(image, tmp_path):
    reference = tmp_path / "reference.png"
    Image.new("RGB", (20, 20), "blue").save(reference)
    evidence = Evidence("One object with frost.")
    engine = qa.VisualQA(evidence)
    contract = {"reference_image": str(reference), "temporal": {"required_evidence": ["frost"],
        "previous_image": str(reference)}}
    assert not engine.assess(image, contract)["cache_hit"]
    assert engine.assess(image, contract)["cache_hit"]
    Image.new("RGB", (20, 20), "green").save(reference)
    assert not engine.assess(image, contract)["cache_hit"]


def test_fast_judge_is_explicit_local_and_bounded(monkeypatch):
    response = SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop",
        message=SimpleNamespace(content='{"verdict":"uncertain"}', reasoning_content="ignored"))])
    create = Mock(return_value=response)
    client = Mock()
    client.chat.completions.create = create
    factory = Mock(return_value=client)
    monkeypatch.setattr(llm, "OpenAI", factory)
    settings = {"openai_image_qa_fast_local_judge": True, "llm_provider": "openai",
                "openai_base_url": "http://127.0.0.1:8080/v1", "openai_model_name": "local-judge"}
    assert llm._generate_qa_response("judge", settings) == '{"verdict":"uncertain"}'
    assert factory.call_args.kwargs["timeout"] == 30 and factory.call_args.kwargs["max_retries"] == 0
    assert create.call_args.kwargs["max_tokens"] == 512
    assert create.call_args.kwargs["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    settings["openai_base_url"] = "https://external.example/v1"
    assert llm._generate_qa_response("judge", settings).startswith("Error:")
    assert factory.call_count == 1


def test_reasoning_never_replaces_final_content(monkeypatch):
    response = SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop",
        message=SimpleNamespace(content=None, reasoning_content='{"verdict":"pass"}'))])
    client = Mock()
    client.chat.completions.create.return_value = response
    monkeypatch.setattr(llm, "OpenAI", Mock(return_value=client))
    settings = {"openai_image_qa_fast_local_judge": True, "openai_base_url": "http://localhost:8080/v1"}
    assert llm._generate_qa_response("judge", settings).startswith("Error:")


@pytest.mark.parametrize("failure", [TimeoutError(), ValueError("invalid response")])
def test_judge_failures_are_unavailable(monkeypatch, failure):
    monkeypatch.setattr(llm, "OpenAI", Mock(side_effect=failure))
    assert llm._generate_qa_response("judge", {"openai_image_qa_fast_local_judge": True,
        "openai_base_url": "http://localhost:8080/v1"}).startswith("Error:")


@pytest.mark.parametrize("verdict", ["pass", "fail", "uncertain", "unavailable"])
def test_scene_contract_joint_qa_no_duplicate_calls(pipeline, monkeypatch, verdict):
    run, diagnostics = pipeline
    monkeypatch.setitem(config.app, "openai_image_visual_qa_experimental_enabled", True)
    generated = item("scoped")
    generated.source_info["model"] = "flux-klein-4b-t2i-exp"
    generation = Mock(return_value=[generated])
    monkeypatch.setattr(material, "generate_images_openai", generation)
    engine = Mock()
    engine.assess.return_value = {"verdict": verdict, "available": verdict != "unavailable", "checks": []}
    monkeypatch.setattr(material, "_new_visual_qa_engine", Mock(return_value=engine))
    gross = Mock(side_effect=AssertionError("duplicate gross call"))
    temporal = Mock(side_effect=AssertionError("unnecessary temporal call"))
    monkeypatch.setattr(material, "_scene_gross_semantic_assessment", gross)
    monkeypatch.setattr(material, "_scene_temporal_semantic_assessment", temporal)
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": False})
    result = run(search_terms=["An object"], scene_durations=[1], scene_routes=["standard"],
        scene_subjects=["object"], scene_qa_contracts=[{"counts": [{"subject": "object", "expected_count": 1}]}])
    assert bool(result) == (verdict == "pass")
    assert engine.assess.call_count == generation.call_count == 1
    gross.assert_not_called()
    temporal.assert_not_called()


def test_count_contract_cannot_bypass_temporal_requirement(pipeline, monkeypatch):
    run, diagnostics = pipeline
    monkeypatch.setitem(config.app, "openai_image_visual_qa_experimental_enabled", True)
    generated = item("scoped")
    generated.source_info["model"] = "flux-klein-4b-edit-exp"
    monkeypatch.setattr(material, "generate_images_openai", Mock(return_value=[generated]))
    engine = Mock()
    engine.assess.return_value = {"verdict": "uncertain", "available": True, "checks": []}
    monkeypatch.setattr(material, "_new_visual_qa_engine", Mock(return_value=engine))
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": False})
    result = run(search_terms=["same object now frosted"], scene_durations=[1], scene_routes=["standard"],
        scene_subjects=["object"], scene_reference_targets=["output"], scene_includes_primary_subject=[False],
        scene_continuity_keys=["state_chain"], scene_continuity_descriptions=["single object"],
        scene_temporal_progressions=[True], scene_temporal_states=["visible frost"],
        scene_qa_contracts=[{"counts": [{"subject": "object", "expected_count": 1}]}])
    assert result == []
    assert engine.assess.call_args.args[1]["temporal"]["expected_state"] == "visible frost"


def test_scene_marks_reference_identity_critical(pipeline, monkeypatch):
    run, _ = pipeline
    monkeypatch.setitem(config.app, "openai_image_visual_qa_experimental_enabled", True)
    generated = item("critical")
    generated.source_info["model"] = "flux-klein-4b-t2i-exp"
    monkeypatch.setattr(material, "generate_images_openai", Mock(return_value=[generated]))
    engine = Mock()
    engine.assess.return_value = {"verdict": "uncertain", "available": True}
    monkeypatch.setattr(material, "_new_visual_qa_engine", Mock(return_value=engine))
    result = run(search_terms=["object"], scene_routes=["standard"], scene_subjects=["object"],
        scene_reference_critical=[True], scene_qa_contracts=[{"counts": [{"subject": "object", "expected_count": 1}]}])
    assert result == []
    assert engine.assess.call_args.args[1]["identity_critical"] is True


def test_empty_contract_does_not_verify_experimental_scene(pipeline, monkeypatch):
    run, _ = pipeline
    monkeypatch.setitem(config.app, "openai_image_visual_qa_experimental_enabled", True)
    generated = item("empty")
    generated.source_info["model"] = "flux-klein-4b-t2i-exp"
    monkeypatch.setattr(material, "generate_images_openai", Mock(return_value=[generated]))
    engine = Mock()
    engine.assess.return_value = {"verdict": "pass", "available": True, "status": "not_required"}
    monkeypatch.setattr(material, "_new_visual_qa_engine", Mock(return_value=engine))
    assert run(search_terms=["object"], scene_routes=["standard"], scene_subjects=["object"],
               scene_qa_contracts=[{}]) == []
