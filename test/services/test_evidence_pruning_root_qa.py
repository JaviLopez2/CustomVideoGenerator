"""Regressions for evidence-pruning fallbacks and gross visual QA."""
import json
from unittest.mock import patch

from app.services import llm, material
from test.services.test_corrective_continuity import pipeline, item  # noqa: F401
from test.services.test_evidence_semantic_fallback import rejected


def make_plan(rows, narrations, inventory):
    with patch.object(llm, "_generate_response", side_effect=[json.dumps(rows)] * 2):
        result = llm.generate_scene_image_plan(
            "Polaroid SX-70",
            [{"narration": narration} for narration in narrations],
            reference_inventory=inventory,
            app_config={},
        )
    assert len(result) == len(rows)
    return result


def test_partial_detail_evidence_is_pruned_instead_of_erasing_scene():
    inventory = [
        {"role": "identity", "description": "Overall Polaroid SX-70 whole-subject identity."},
        {
            "role": "detail",
            "description": (
                "Close visible detail of the Polaroid SX-70 front controls, lens area, "
                "red shutter button and front panel."
            ),
        },
    ]
    row = {
        "subject": "Polaroid SX-70 shutter controls",
        "canonical_subject": "Polaroid SX-70",
        "scene_description": "Close view of the shutter, focus ring, lens barrel and red button.",
        "required_features": ["red shutter button", "lens area", "focus ring", "lens barrel"],
        "forbidden_features": [],
        "reference_need": "detail",
        "reference_target": "primary_subject",
        "reference_query": "red shutter button lens focus ring barrel",
        "evidence_scope": "specialized_visible",
        "reference_critical": True,
        "includes_primary_subject": False,
        "route": "precision",
    }
    scene = make_plan(
        [row],
        ["Cuando pulsas el disparador, la luz entra a través del objetivo."],
        inventory,
    )[0]

    assert scene["planner_validation"] == "coverage_pruned"
    assert scene["coverage_status"] == "covered"
    assert scene["route"] == "precision"
    assert scene["reference_need"] == "detail"
    assert scene["reference_target"] == "primary_subject"
    assert "red shutter button" in scene["prompt"]
    assert "lens area" in scene["prompt"]
    assert "focus ring" not in scene["prompt"]
    assert "lens barrel" not in scene["prompt"]
    assert "el disparador" not in scene["prompt"].lower()
    assert "red shutter button" in scene["reference_query"]


def test_spanish_grounding_uses_explicit_english_visual_label():
    row = rejected(
        reference_need="detail",
        reference_target="primary_subject",
        evidence_scope="specialized_visible",
        reference_query="unsupported close detail",
        observable_subject="el disparador",
        observable_subject_visual="red shutter button",
        scene_description="unsupported close detail",
    )
    scene = make_plan(
        [row],
        ["Cuando pulsas el disparador, la cámara inicia la exposición."],
        [{"role": "identity", "description": "whole Polaroid SX-70"}],
    )[0]

    assert scene["planner_validation"] == "coverage_fallback"
    assert scene["canonical_subject"] == "red shutter button"
    assert "red shutter button" in scene["prompt"]
    assert "el disparador" not in scene["prompt"].lower()


def test_hidden_scene_reuses_recent_visible_output_not_abstract_context():
    visible_output = {
        "subject": "instant photograph",
        "canonical_subject": "instant photograph",
        "scene_description": "An instant photograph resting on a table.",
        "reference_need": "none",
        "reference_target": "output",
        "evidence_scope": "externally_visible",
        "reference_critical": False,
        "includes_primary_subject": False,
        "route": "standard",
    }
    hidden = rejected(
        reference_target="output",
        observable_subject="",
        observable_result="",
        observable_state="",
    )
    scenes = make_plan(
        [visible_output, hidden],
        [
            "An instant photograph rests on the table.",
            "The chemical reaction continues inside the film layers.",
        ],
        [{"role": "identity", "description": "whole Polaroid SX-70"}],
    )
    fallback = scenes[1]

    assert fallback["planner_validation"] == "coverage_fallback"
    assert fallback["canonical_subject"] == "instant photograph"
    assert fallback["reference_target"] == "output"
    assert fallback["route"] == "standard"
    assert "narration-grounded exterior context" not in fallback["prompt"]
    assert "instant photograph" in fallback["prompt"]


def test_visual_caption_judge_normalizes_llm_response():
    response = json.dumps({
        "candidates": [{
            "index": 1,
            "semantic_score": 0.1,
            "identity_confidence": 0.05,
            "required_feature_coverage": 0.0,
            "forbidden_feature_violation": 0.9,
            "observed_forbidden": ["unrelated person"],
            "verdict": "reject",
            "rationale": "The requested photograph is absent.",
        }]
    })
    with patch.object(llm, "_generate_response", return_value=response):
        result = llm.evaluate_precision_visual_caption(
            subject="instant photograph",
            required_features=[],
            forbidden_features=["unrelated person"],
            visual_caption="A man stands outside a house.",
            app_config={},
        )
    assert result["available"] is True
    assert result["verdict"] == "reject"
    assert result["identity_confidence"] == 0.05
    assert result["forbidden_feature_violation"] == 0.9
    assert result["observed_forbidden"] == ["unrelated person"]


def test_multiple_root_is_rejected_even_if_text_judge_is_unavailable(monkeypatch):
    candidate = item("grid")
    monkeypatch.setattr(
        material,
        "_precision_semantic_evaluation",
        lambda **kw: {
            "available": False,
            "caption": "Several instant photographs are arranged in a grid on a table.",
            "reason": "text judge unavailable",
        },
    )
    result = material._scene_gross_semantic_assessment(
        candidate,
        subject="instant photograph",
        required_features=[],
        forbidden_features=[],
        require_single=True,
    )
    assert result["gross_failure"] is True
    assert result["explicit_multiple"] is True
    assert result["status"] == "gross_failure"


def test_gross_semantic_assessment_flags_multiple_instances(monkeypatch):
    candidate = item("grid")
    monkeypatch.setattr(
        material,
        "_precision_semantic_evaluation",
        lambda **kw: {
            "available": True,
            "caption": "Several instant photographs are arranged in a grid on a wooden table.",
            "judgment": {
                "available": True,
                "semantic_score": 0.72,
                "identity_confidence": 0.82,
                "required_feature_coverage": 0.2,
                "forbidden_feature_violation": 0.8,
                "verdict": "reject",
            },
        },
    )
    result = material._scene_gross_semantic_assessment(
        candidate,
        subject="SX-70 instant photograph",
        required_features=[],
        forbidden_features=[],
        require_single=True,
    )
    assert result["gross_failure"] is True
    assert result["explicit_multiple"] is True
    assert result["status"] == "gross_failure"


def test_gross_fallback_gets_one_retry_and_uses_recovery(pipeline, monkeypatch):
    run, diagnostics = pipeline
    monkeypatch.setattr(material, "_gross_scene_semantic_qa_enabled", lambda: True)
    monkeypatch.setattr(material, "_gross_scene_semantic_retry_enabled", lambda: True)
    generated = [item("wrong-person"), item("recovered-photo")]
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        return [generated[len(calls) - 1]]

    assessments = iter([
        {
            "available": True,
            "status": "gross_failure",
            "gross_failure": True,
            "reason": "requested subject absent",
        },
        {
            "available": True,
            "status": "pass",
            "gross_failure": False,
            "reason": "requested subject present",
        },
    ])
    monkeypatch.setattr(material, "generate_images_openai", generate)
    monkeypatch.setattr(
        material,
        "_near_duplicate_assessment",
        lambda *a, **kw: {"actionable": False, "best_similarity": 0.3},
    )
    monkeypatch.setattr(
        material, "_scene_gross_semantic_assessment", lambda *a, **kw: next(assessments)
    )

    result = run(
        search_terms=["A clear instant photograph on a table."],
        scene_durations=[1],
        scene_routes=["standard"],
        scene_subjects=["instant photograph"],
        scene_planner_validation=["coverage_fallback"],
    )

    assert result == ["recovered-photo.png.mp4"]
    assert len(calls) == 2
    assert "unmistakable main subject" in calls[1]["search_term"]
    qa = diagnostics[-1]["plan_scenes"][0]["gross_semantic_qa"]
    assert qa["selected_candidate"] == "retry"


def test_continuity_root_is_not_frozen_until_gross_qa_passes(pipeline, monkeypatch):
    run, diagnostics = pipeline
    monkeypatch.setattr(material, "_gross_scene_semantic_qa_enabled", lambda: True)
    monkeypatch.setattr(material, "_gross_scene_semantic_retry_enabled", lambda: True)
    generated = [item("bad-root"), item("good-root"), item("later-stage")]
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        return [generated[len(calls) - 1]]

    assessments = iter([
        {
            "available": True,
            "status": "gross_failure",
            "gross_failure": True,
            "reason": "multiple repeated outputs",
        },
        {
            "available": True,
            "status": "pass",
            "gross_failure": False,
            "reason": "single output present",
        },
    ])
    monkeypatch.setattr(material, "generate_images_openai", generate)
    monkeypatch.setattr(
        material,
        "_near_duplicate_assessment",
        lambda *a, **kw: {"actionable": False, "best_similarity": 0.3},
    )
    monkeypatch.setattr(
        material, "_scene_gross_semantic_assessment", lambda *a, **kw: next(assessments)
    )
    monkeypatch.setattr(material, "_upload_reference_to_comfyui", lambda path: path)
    monkeypatch.setattr(material, "_continuity_edit_chain_enabled", lambda: True)

    result = run(
        search_terms=["single early print", "same print later"],
        scene_durations=[1, 1],
        scene_routes=["standard", "standard"],
        scene_subjects=["instant photograph", "instant photograph"],
        scene_reference_targets=["output", "output"],
        scene_includes_primary_subject=[False, False],
        scene_continuity_keys=["photo_chain", "photo_chain"],
        scene_continuity_descriptions=[
            "single instant photograph with the same depicted content",
            "single instant photograph with the same depicted content",
        ],
    )

    assert result == ["good-root.png.mp4", "later-stage.png.mp4"]
    assert len(calls) == 3
    assert calls[2]["reference_images"] == ["good-root.png"]
    assert diagnostics[-1]["plan_scenes"][1]["continuity_source_scene"] == 1
    assert diagnostics[-1]["plan_scenes"][0]["gross_semantic_qa"]["selected_candidate"] == "retry"


def test_persistent_gross_failure_fails_closed(pipeline, monkeypatch):
    run, diagnostics = pipeline
    monkeypatch.setattr(material, "_gross_scene_semantic_qa_enabled", lambda: True)
    monkeypatch.setattr(material, "_gross_scene_semantic_retry_enabled", lambda: True)
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        return [item("wrong-" + str(len(calls)))]

    monkeypatch.setattr(material, "generate_images_openai", generate)
    monkeypatch.setattr(
        material,
        "_scene_gross_semantic_assessment",
        lambda *a, **kw: {
            "available": True,
            "status": "gross_failure",
            "gross_failure": True,
            "reason": "requested subject absent",
        },
    )

    result = run(
        search_terms=["A clear instant photograph on a table."],
        scene_durations=[1],
        scene_routes=["standard"],
        scene_subjects=["instant photograph"],
        scene_planner_validation=["coverage_fallback"],
    )

    assert result == []
    assert len(calls) == 2
    qa = diagnostics[-1]["plan_scenes"][0]["gross_semantic_qa"]
    assert qa["selected_candidate"] == "none"
    assert qa["status"] == "persistent_gross_failure"
    assert diagnostics[-1]["status"] == "failed"
