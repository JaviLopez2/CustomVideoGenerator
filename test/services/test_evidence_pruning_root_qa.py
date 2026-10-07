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


def test_primary_fallback_keeps_referenced_identity_over_mentioned_output():
    row = rejected(
        subject="Polaroid SX-70 camera",
        canonical_subject="Polaroid SX-70 camera",
        reference_target="primary_subject",
        observable_subject="Polaroid SX-70 camera",
        observable_subject_visual="Polaroid SX-70 camera",
        observable_result="developed photograph",
        observable_result_visual="developed photograph",
    )
    scene = make_plan(
        [row],
        ["The Polaroid SX-70 camera appears to reveal a developed photograph."],
        [{"role": "identity", "description": "whole Polaroid SX-70 camera"}],
    )[0]

    assert scene["planner_validation"] == "coverage_fallback"
    assert scene["canonical_subject"] == "Polaroid SX-70 camera"
    assert scene["reference_target"] == "primary_subject"
    assert scene["reference_need"] == "identity"
    assert scene["route"] == "precision"
    assert scene["includes_primary_subject"] is True
    assert "Polaroid SX-70 camera" in scene["prompt"]
    assert "developed photograph" not in scene["canonical_subject"].lower()


def test_rejected_detail_fallback_keeps_established_primary_identity():
    inventory = [
        {"role": "identity", "description": "whole Polaroid SX-70 camera"},
        {
            "role": "detail",
            "description": "Close visible detail of the Polaroid SX-70 front controls, lens area, red shutter button and front panel.",
        },
    ]
    identity = {
        "subject": "Polaroid SX-70 camera",
        "canonical_subject": "Polaroid SX-70 camera",
        "scene_description": "A complete Polaroid SX-70 camera on a table.",
        "reference_need": "identity",
        "reference_target": "primary_subject",
        "evidence_scope": "externally_visible",
        "reference_critical": True,
        "includes_primary_subject": True,
        "route": "precision",
    }
    detail = {
        "subject": "red shutter button",
        "canonical_subject": "red shutter button",
        "scene_description": "Close view of red shutter button, focus ring, barrel and surrounding housing.",
        "observable_subject": "red shutter button",
        "observable_subject_visual": "red shutter button",
        "reference_need": "detail",
        "reference_target": "primary_subject",
        "reference_query": "red shutter button focus ring barrel surrounding housing",
        "evidence_scope": "specialized_visible",
        "reference_critical": True,
        "includes_primary_subject": True,
        "route": "precision",
    }
    scenes = make_plan(
        [identity, detail],
        [
            "The Polaroid SX-70 camera is ready to use.",
            "The red shutter button is pressed and light enters through the lens.",
        ],
        inventory,
    )
    fallback = scenes[1]

    assert fallback["planner_validation"] == "coverage_fallback"
    assert fallback["canonical_subject"] == "Polaroid SX-70 camera"
    assert fallback["reference_target"] == "primary_subject"
    assert fallback["reference_need"] == "identity"
    assert fallback["route"] == "precision"
    assert "Polaroid SX-70 camera" in fallback["prompt"]
    assert "red shutter button" in fallback["prompt"]


def test_temporal_output_fallback_keeps_concrete_continuity_subject():
    inventory = [{"role": "identity", "description": "whole Polaroid SX-70 camera"}]
    rows = [
        {
            "subject": "instant photograph",
            "canonical_subject": "instant photograph",
            "scene_description": "An instant photograph with a faint early image.",
            "observable_subject": "instant photograph",
            "observable_result": "instant photograph",
            "observable_result_visual": "instant photograph",
            "observable_state": "faint early image",
            "visual_state": "faint low-contrast image",
            "reference_need": "none",
            "reference_target": "output",
            "evidence_scope": "externally_visible",
            "route": "standard",
            "continuity_key": "developing_print",
            "continuity_description": "the same instant photograph",
            "temporal_progression": True,
        },
        {
            "subject": "emerging tonal shapes",
            "canonical_subject": "emerging tonal shapes",
            "scene_description": "Emerging tonal shapes become visible.",
            "observable_subject": "",
            "observable_result": "emerging tonal shapes",
            "observable_result_visual": "emerging tonal shapes",
            "observable_state": "emerging tonal shapes",
            "visual_state": "emerging tonal shapes",
            "reference_need": "context",
            "reference_target": "output",
            "evidence_scope": "externally_visible",
            "route": "standard",
            "continuity_key": "developing_print",
            "continuity_description": "the same instant photograph",
            "temporal_progression": True,
        },
    ]
    scenes = make_plan(
        rows,
        [
            "The instant photograph has a faint early image.",
            "The same instant photograph now shows emerging tonal shapes.",
        ],
        inventory,
    )
    fallback = scenes[1]

    assert fallback["planner_validation"] == "coverage_fallback"
    assert fallback["canonical_subject"] == "instant photograph"
    assert fallback["reference_target"] == "output"
    assert fallback["temporal_progression"] is True
    assert "emerging tonal shapes" != fallback["canonical_subject"]


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


def test_hidden_output_fallback_retains_concrete_visible_description():
    # Run 0118359c: S5 inherited S3's branded output name, but lost the
    # blank physical print description. Both attempts were captioned as cameras.
    for identity, physical_view in [
        ("Polaroid SX-70 photograph", "A blank instant photograph emerging from the camera exit slot."),
        ("Atlas fabricator panel", "A flat rectangular panel with a smooth white surface resting on a tray."),
    ]:
        visible = dict(subject=identity, canonical_subject=identity,
            scene_description=physical_view, reference_target="output", reference_need="none",
            evidence_scope="externally_visible", route="standard", includes_primary_subject=False)
        hidden = rejected(reference_target="output", observable_subject="", observable_result="",
                          observable_state="", safe_visual_alternative="cutaway with internal gears")
        scenes = make_plan([visible, hidden], [physical_view, "The hidden process continues."],
                           [{"role": "identity", "description": "whole source device"}])
        fallback = scenes[1]
        assert physical_view in fallback["prompt"]
        assert fallback["canonical_subject"] == identity
        assert fallback["reference_target"] == "output"
        assert fallback["reference_need"] == "none"
        assert fallback["route"] == "standard"
        assert fallback["continuity_key"] == "none"
        assert not fallback["temporal_progression"]
        assert "established visible exterior state" not in fallback["prompt"]
        assert "internal gears" not in fallback["prompt"]
        assert "twin gears" not in fallback["prompt"]


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


def test_continuity_description_drops_temporal_stage_language():
    rows = [
        {
            "subject": "SX-70 instant photo sheet",
            "canonical_subject": "SX-70 instant photo sheet",
            "scene_description": "An early instant photograph with faint visible detail.",
            "observable_state": "faint visible detail",
            "visual_state": "faint visible detail",
            "reference_need": "none",
            "reference_target": "output",
            "evidence_scope": "externally_visible",
            "route": "standard",
            "continuity_key": "photo_chain",
            "continuity_description": (
                "single SX-70 instant photo sheet undergoing development stages"
            ),
            "temporal_progression": True,
        },
        {
            "subject": "SX-70 instant photo sheet",
            "canonical_subject": "SX-70 instant photo sheet",
            "scene_description": "The same photograph has clearer visible detail.",
            "observable_state": "clearer visible detail",
            "visual_state": "clearer visible detail",
            "reference_need": "none",
            "reference_target": "output",
            "evidence_scope": "externally_visible",
            "route": "standard",
            "continuity_key": "photo_chain",
            "continuity_description": (
                "single SX-70 instant photo sheet undergoing development stages"
            ),
            "temporal_progression": True,
        },
    ]
    scenes = make_plan(
        rows,
        [
            "The SX-70 instant photo sheet has faint visible detail.",
            "The same SX-70 instant photo sheet has clearer visible detail.",
        ],
        [{"role": "identity", "description": "whole Polaroid SX-70"}],
    )
    expected = "the same single SX-70 instant photo sheet"
    assert scenes[0]["continuity_description"] == expected
    assert scenes[1]["continuity_description"] == expected
    assert "development stages" not in scenes[0]["prompt"].lower()
    assert "development stages" not in scenes[1]["prompt"].lower()


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


def test_known_gross_failure_does_not_accept_unverified_retry(pipeline, monkeypatch):
    run, diagnostics = pipeline
    monkeypatch.setattr(material, "_gross_scene_semantic_qa_enabled", lambda: True)
    monkeypatch.setattr(material, "_gross_scene_semantic_retry_enabled", lambda: True)
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        return [item("wrong-original" if len(calls) == 1 else "unknown-retry")]

    assessments = iter([
        {
            "available": True,
            "status": "gross_failure",
            "gross_failure": True,
            "reason": "requested subject absent",
        },
        {
            "available": False,
            "status": "unavailable",
            "gross_failure": False,
            "reason": "caption judge unavailable",
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

    assert result == []
    assert len(calls) == 2
    qa = diagnostics[-1]["plan_scenes"][0]["gross_semantic_qa"]
    assert qa["selected_candidate"] == "none"
    assert qa["retry"]["status"] == "unavailable"
    assert qa["status"] == "persistent_gross_failure"


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



def test_covered_reference_query_cannot_hide_unsupported_required_features():
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
        "subject": "Polaroid SX-70 front controls",
        "canonical_subject": "Polaroid SX-70",
        "scene_description": "Two rollers press a photo sheet beside the front controls.",
        "required_features": [
            "red shutter button",
            "lens area",
            "two parallel rollers",
            "photo sheet passing through rollers",
        ],
        "forbidden_features": [],
        "reference_need": "detail",
        "reference_target": "primary_subject",
        "reference_query": "front controls lens area red shutter button front panel",
        "evidence_scope": "specialized_visible",
        "reference_critical": True,
        "includes_primary_subject": False,
        "route": "precision",
    }
    scene = make_plan(
        [row],
        ["La cámara expulsa la fotografía hacia el exterior."],
        inventory,
    )[0]

    assert scene["planner_validation"] == "coverage_pruned"
    assert scene["coverage_status"] == "covered"
    assert "red shutter button" in scene["prompt"]
    assert "lens area" in scene["prompt"]
    assert "rollers" not in scene["prompt"].lower()
    assert "photo sheet passing" not in scene["prompt"].lower()


def test_hidden_causal_output_rewrite_preserves_safe_temporal_continuity():
    row = {
        "subject": "freshly ejected instant photograph",
        "canonical_subject": "SX-70 instant photograph",
        "scene_description": (
            "A freshly ejected photograph with visible reagent gel oozing from the edges "
            "and a chemical sheen spreading across the paper surface."
        ),
        "required_features": ["reagent gel", "chemical sheen"],
        "forbidden_features": [],
        "reference_need": "none",
        "reference_target": "output",
        "reference_query": "",
        "evidence_scope": "externally_visible",
        "reference_critical": False,
        "includes_primary_subject": False,
        "route": "standard",
        "observable_result": "la misma fotografía recién expulsada",
        "observable_result_visual": "the same freshly ejected instant photograph",
        "observable_state": "apenas muestra información",
        "visual_state": "barely shows any image information",
        "continuity_key": "photo_chain",
        "continuity_description": "single SX-70 instant photograph",
        "temporal_progression": True,
    }
    scene = make_plan(
        [row],
        ["Al principio, la misma fotografía recién expulsada apenas muestra información."],
        [{"role": "identity", "description": "whole Polaroid SX-70"}],
    )[0]

    assert scene["planner_validation"] == "coverage_fallback"
    assert scene["continuity_key"] == "photo_chain"
    assert scene["temporal_progression"] is True
    assert scene["temporal_state"] == "barely shows any image information"
    assert "reagent" not in scene["prompt"].lower()
    assert "chemical" not in scene["prompt"].lower()
    assert "barely shows any image information" in scene["prompt"].lower()


def test_temporal_caption_judge_normalizes_response():
    response = json.dumps({
        "state_score": 0.15,
        "progression_score": 0.1,
        "verdict": "reject",
        "rationale": "The image already looks fully developed.",
    })
    with patch.object(llm, "_generate_response", return_value=response):
        result = llm.evaluate_precision_temporal_caption(
            subject="instant photograph",
            requested_state="barely shows any image information",
            visual_caption="A detailed colorful landscape is visible inside a Polaroid print.",
            app_config={},
        )
    assert result["available"] is True
    assert result["verdict"] == "reject"
    assert result["state_score"] == 0.15
    assert result["progression_score"] == 0.1


def test_temporal_root_failure_gets_one_verified_retry(pipeline, monkeypatch):
    run, diagnostics = pipeline
    monkeypatch.setattr(material, "_temporal_semantic_qa_enabled", lambda: True)
    monkeypatch.setattr(material, "_temporal_semantic_retry_enabled", lambda: True)
    monkeypatch.setattr(material, "_gross_scene_semantic_qa_enabled", lambda: False)
    generated = [item("too-developed"), item("early-stage")]
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        return [generated[len(calls) - 1]]

    assessments = iter([
        {"available": True, "status": "temporal_failure", "temporal_failure": True,
         "caption": "A fully developed colorful photograph.", "verdict": "reject"},
        {"available": True, "status": "pass", "temporal_failure": False,
         "caption": "A mostly blank instant photograph with faint shapes.", "verdict": "pass"},
    ])
    monkeypatch.setattr(material, "generate_images_openai", generate)
    monkeypatch.setattr(material, "_near_duplicate_assessment",
                        lambda *a, **kw: {"actionable": False, "best_similarity": 0.3})
    monkeypatch.setattr(material, "_scene_temporal_semantic_assessment",
                        lambda *a, **kw: next(assessments))

    result = run(
        search_terms=["same instant photograph, early faint state"],
        scene_durations=[1], scene_routes=["standard"],
        scene_subjects=["instant photograph"], scene_reference_targets=["output"],
        scene_includes_primary_subject=[False], scene_continuity_keys=["photo_chain"],
        scene_continuity_descriptions=["single instant photograph"],
        scene_temporal_progressions=[True],
        scene_temporal_states=["barely shows any image information"],
    )

    assert result == ["early-stage.png.mp4"]
    assert len(calls) == 2
    assert "current state: barely shows any image information" in calls[1]["search_term"]
    qa = diagnostics[-1]["plan_scenes"][0]["temporal_semantic_qa"]
    assert qa["selected_candidate"] == "retry"


def test_temporal_failure_does_not_create_third_candidate_after_duplicate_retry(pipeline, monkeypatch):
    run, diagnostics = pipeline
    monkeypatch.setattr(material, "_temporal_semantic_qa_enabled", lambda: True)
    monkeypatch.setattr(material, "_temporal_semantic_retry_enabled", lambda: True)
    generated = [item("duplicate-original"), item("duplicate-retry")]
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        return [generated[len(calls) - 1]]

    monkeypatch.setattr(material, "generate_images_openai", generate)
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda path, *a, **kw: {
        "actionable": path == "duplicate-original.png",
        "best_similarity": 0.97 if path == "duplicate-original.png" else 0.80,
    })
    monkeypatch.setattr(material, "_scene_temporal_semantic_assessment", lambda *a, **kw: {
        "available": True, "status": "temporal_failure", "temporal_failure": True,
        "caption": "The photograph looks unchanged.", "verdict": "reject",
    })

    result = run(
        search_terms=["same instant photograph, clearer mid-development state"],
        scene_durations=[1], scene_routes=["precision"],
        scene_subjects=["instant photograph"], scene_reference_targets=["primary_subject"],
        scene_includes_primary_subject=[True], scene_continuity_keys=["photo_chain"],
        scene_continuity_descriptions=["single instant photograph"],
        scene_temporal_progressions=[True],
        scene_temporal_states=["clearer shapes and emerging color"],
    )

    assert result == []
    assert len(calls) == 2
    qa = diagnostics[-1]["plan_scenes"][0]["temporal_semantic_qa"]
    assert qa["selected_candidate"] == "none"
    assert qa["status"] == "temporal_retry_budget_exhausted"
