import json
from unittest.mock import patch

import pytest

from app.services import llm, material
from app.utils.image_prompt import clean_image_text
from test.services.test_corrective_continuity import pipeline, item  # noqa: F401


def test_machine_ids_removed_but_explicit_literal_inscriptions_survive():
    assert "chain_delta_72" not in clean_image_text("same target chain_delta_72")
    assert 'literal text: "hello_world"' in clean_image_text('literal text: "hello_world"')
    assert "job-47" not in clean_image_text("same target job-47", ["job-47"])


def state_plan():
    states = ["faint amber outline", "clearer amber outline", "fully bright amber outline"]
    rows = [{
        "subject": "indicator tile", "canonical_subject": "indicator tile",
        "scene_description": "fully bright final result chain_delta_72",
        "composition": "completed final display", "required_features": ["fully bright"],
        "reference_need": "none", "reference_target": "output",
        "evidence_scope": "externally_visible", "route": "standard",
        "continuity_key": "chain_delta_72", "planner_id": "draft-47",
        "continuity_description": "the same triangular glyph within the tile boundary",
        "observable_state": state, "temporal_progression": True,
        "context_subject": "control console" if n else "",
        "includes_primary_subject": bool(n),
    } for n, state in enumerate(states)]
    with patch.object(llm, "_generate_response", side_effect=[json.dumps(rows)] * 2):
        result = llm.generate_scene_image_plan("indicator", [{"narration": f"The tile shows a {s}."}
            for s in states], app_config={},
            reference_inventory=[{"role": "identity", "description": "whole control console"}])
    assert len(result) == 3
    return result


def test_state_chain_keeps_content_and_scene_local_progression():
    result = state_plan()
    for scene, state in zip(result, ["faint amber outline", "clearer amber outline", "fully bright amber outline"]):
        assert state in scene["prompt"]
        assert "dominant visual instruction" in scene["prompt"]
        assert "same triangular glyph" in scene["prompt"]
        assert "same direction" in scene["prompt"]
        assert scene["continuity_key"] == "chain_delta_72"
        assert "chain_delta_72" not in scene["prompt"]
    assert "fully bright" not in result[0]["prompt"]
    assert "completed final display" not in result[0]["prompt"]
    assert "Separate physical context: control console" in result[2]["prompt"]
    assert "outside and beside" in result[2]["prompt"]
    assert "existing depicted content intact" in result[2]["prompt"]


def test_continuity_without_state_keeps_natural_language_not_group_id():
    row = {"subject": "tile", "scene_description": "same tile draft-47", "planner_id": "draft-47",
           "continuity_key": "arbitrary_group_29", "continuity_description": "same glyph on the tile",
           "reference_need": "none", "reference_target": "output", "evidence_scope": "externally_visible"}
    with patch.object(llm, "_generate_response", return_value=json.dumps([row])):
        scene = llm.generate_scene_image_plan("tile", [{"narration": "A tile."}], app_config={})[0]
    assert "arbitrary_group_29" not in scene["prompt"]
    assert "draft-47" not in scene["prompt"]
    assert "same glyph on the tile" in scene["prompt"]


def test_context_anchor_is_spatially_separate_from_content(pipeline, monkeypatch):
    run, diagnostics = pipeline
    calls = []
    monkeypatch.setattr(material, "generate_images_openai", lambda **kw: calls.append(kw) or [item(f"stage{len(calls)}")])
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": False, "best_similarity": .5})
    monkeypatch.setattr(material, "_upload_reference_to_comfyui", lambda path: "previous-stage.png")
    monkeypatch.setattr(material, "_continuity_edit_chain_enabled", lambda: True)
    run(search_terms=["faint glyph chain_delta_72", "clear glyph beside console", "bright glyph beside console"],
        scene_routes=["standard"] * 3, scene_subjects=["tile"] * 3,
        scene_reference_targets=["output"] * 3, scene_includes_primary_subject=[False, True, True],
        scene_continuity_keys=["chain_delta_72"] * 3,
        scene_continuity_descriptions=["same triangular glyph on the tile"] * 3)
    assert len(calls) == 3
    assert calls[1]["reference_images"] == ["previous-stage.png", "identity.png"]
    for call in calls[1:]:
        prompt = material._qwen_precision_prompt_with_references(
            call["search_term"], call["reference_subject"], len(call["reference_images"]), call["reference_info"])
        assert "same triangular glyph" in prompt
        assert "outside and beside" in prompt
        assert "never reinterpret the whole reference frame" in prompt
        assert "chain_delta_72" not in prompt


@pytest.mark.parametrize("model,refs", [("qwen-image-2.1", []), ("qwen-image-2.1", ["anchor.png"]), ("other", ["anchor.png"])])
def test_final_request_payload_has_no_machine_names(monkeypatch, model, refs):
    monkeypatch.setattr(material.config, "app", {})
    monkeypatch.setattr(material, "_openai_image_endpoint", lambda **kw: ("mock://image", model))
    calls = []
    monkeypatch.setattr(material, "_request_openai_image", lambda endpoint, payload: calls.append(payload) or (None, "unconfirmed request error"))
    material.generate_images_openai("same tile chain_delta_72", 1, reference_images=refs,
        reference_subject="tile target_alpha", reference_info={"reference_pack": [{"role": "identity", "description": "console internal_group_18"}]})
    assert len(calls) == 1
    assert all(token not in calls[0]["prompt"] for token in ("chain_delta_72", "target_alpha", "internal_group_18"))
    assert "same tile" in calls[0]["prompt"]
