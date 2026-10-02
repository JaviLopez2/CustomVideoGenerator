import json
from unittest.mock import patch

import pytest

from app.services import llm, material
from app.utils.image_prompt import clean_image_text
from test.services.test_corrective_continuity import pipeline, item  # noqa: F401


def test_machine_ids_removed_but_explicit_literal_inscriptions_survive():
    assert "chain_delta_72" not in clean_image_text("same target chain_delta_72", ["chain_delta_72"])
    assert 'literal text: "hello_world"' in clean_image_text('literal text: "hello_world"')
    assert "job-47" not in clean_image_text("same target job-47", ["job-47"])
    assert clean_image_text("project_alpha model_v2 hello_world") == "project_alpha model_v2 hello_world"


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
        "observable_state": state, "visual_state": state, "temporal_progression": True,
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
        assert "same triangular glyph" in scene["prompt"]
        assert "Current visible state" not in scene["prompt"]
        assert "State instructions govern appearance" not in scene["prompt"]
        assert scene["continuity_key"] == "chain_delta_72"
        assert "chain_delta_72" not in scene["prompt"]
    assert "fully bright" not in result[0]["prompt"]
    assert "completed final display" not in result[0]["prompt"]
    assert "A separate control console is visible in the surrounding scene" in result[2]["prompt"]
    assert "outside and beside" not in result[2]["prompt"]
    assert "existing depicted content intact" not in result[2]["prompt"]


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
        assert "<image1> is the canvas" in prompt
        assert "<image2> is identity evidence" in prompt
        assert "outside and beside" not in prompt
        assert "never reinterpret the whole reference frame" not in prompt
        assert "chain_delta_72" not in prompt


@pytest.mark.parametrize("model,refs", [("qwen-image-2.1", []), ("qwen-image-2.1", ["anchor.png"]), ("other", ["anchor.png"])])
def test_final_request_payload_has_no_machine_names(monkeypatch, model, refs):
    monkeypatch.setattr(material.config, "app", {})
    monkeypatch.setattr(material, "_openai_image_endpoint", lambda **kw: ("mock://image", model))
    calls = []
    monkeypatch.setattr(material, "_request_openai_image", lambda endpoint, payload: calls.append(payload) or (None, "unconfirmed request error"))
    material.generate_images_openai("same tile chain_delta_72 project_alpha model_v2 hello_world", 1, reference_images=refs,
        reference_subject="tile target_alpha", reference_info={"continuity_key": "chain_delta_72",
        "planner_id": "target_alpha", "reference_pack": [{"id": "internal_group_18", "role": "identity", "description": "console internal_group_18"}]})
    assert len(calls) == 1
    assert all(token not in calls[0]["prompt"] for token in ("chain_delta_72", "target_alpha", "internal_group_18"))
    assert "same tile" in calls[0]["prompt"]
    assert all(token in calls[0]["prompt"] for token in ("project_alpha", "model_v2", "hello_world"))


def test_fallback_request_preserves_user_text_and_removes_known_ids(monkeypatch):
    monkeypatch.setattr(material.config, "app", {})
    monkeypatch.setattr(material, "_openai_image_endpoint", lambda **kw: ("mock://image", "qwen-image-2.1"))
    monkeypatch.setattr(material, "_precision_fallback_model", lambda: "offline-fallback")
    calls = []
    monkeypatch.setattr(material, "_request_openai_image", lambda endpoint, payload: calls.append(payload) or (None, "invalid image"))
    material.generate_images_openai("hello_world chain_delta_72", 1, route="precision",
        reference_images=["anchor.png"], reference_info={"continuity_key": "chain_delta_72"})
    assert len(calls) == 2
    assert calls[1]["model"] == "offline-fallback"
    for call in calls:
        assert "chain_delta_72" not in call["prompt"]
        assert "hello_world" in call["prompt"]


@pytest.mark.parametrize("target,context", [("primary_subject", ""), ("none", ""), ("primary_subject", "vehicle")])
def test_same_target_is_not_placed_beside_itself(target, context):
    row = {"subject": "vehicle", "canonical_subject": "vehicle", "context_subject": context,
           "scene_description": "vehicle model_v2 in changing light", "includes_primary_subject": True,
           "continuity_key": "vehicle_state_7", "continuity_description": "same vehicle model_v2",
           "planner_id": "draft-47", "reference_query": "vehicle draft-47", "required_features": ["model_v2 draft-47"],
           "reference_need": "none", "reference_target": target, "evidence_scope": "externally_visible"}
    with patch.object(llm, "_generate_response", return_value=json.dumps([row])):
        scene = llm.generate_scene_image_plan("vehicle", [{"narration": "The vehicle model_v2."}], app_config={})[0]
    assert "outside and beside" not in scene["prompt"]
    assert "model_v2" in scene["prompt"]
    assert "vehicle_state_7" not in scene["prompt"]
    assert "draft-47" not in scene["reference_query"]
    assert scene["required_features"] == ["model_v2"]


@pytest.mark.parametrize("target", ["primary_subject", "none"])
def test_same_entity_reference_chain_keeps_anchor_without_context_contract(pipeline, monkeypatch, target):
    run, diagnostics = pipeline
    calls = []
    monkeypatch.setattr(material, "generate_images_openai", lambda **kw: calls.append(kw) or [item(f"stage{len(calls)}")])
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": False, "best_similarity": .5})
    monkeypatch.setattr(material, "_upload_reference_to_comfyui", lambda path: "previous-stage.png")
    monkeypatch.setattr(material, "_continuity_edit_chain_enabled", lambda: True)
    run(search_terms=["vehicle model_v2 in shade", "same vehicle model_v2 in sunlight"],
        scene_routes=["precision"] * 2, scene_subjects=["vehicle"] * 2,
        scene_reference_targets=[target] * 2, scene_includes_primary_subject=[True] * 2,
        scene_continuity_keys=["vehicle_state_7"] * 2, scene_continuity_descriptions=["same vehicle model_v2"] * 2)
    assert calls[1]["reference_images"] == ["previous-stage.png"]
    for call in calls:
        prompt = material._qwen_precision_prompt_with_references(
            call["search_term"], call["reference_subject"], len(call["reference_images"]), call["reference_info"])
        assert "outside and beside" not in prompt
        assert "model_v2" in prompt
        if call["reference_images"]:
            assert "Edit the input image as the canvas" in prompt


def test_continuity_uses_stable_root_instead_of_recursive_previous_stage(pipeline, monkeypatch):
    run, diagnostics = pipeline
    calls = []
    generated = [item("root"), item("middle"), item("final")]
    monkeypatch.setattr(
        material,
        "generate_images_openai",
        lambda **kw: calls.append(kw) or [generated[len(calls) - 1]],
    )
    monkeypatch.setattr(
        material,
        "_near_duplicate_assessment",
        lambda *a, **kw: {"actionable": False, "best_similarity": .4},
    )
    uploaded = []
    def upload(path):
        uploaded.append(path)
        return path.replace(".png", "") + "-uploaded.png"
    monkeypatch.setattr(material, "_upload_reference_to_comfyui", upload)
    monkeypatch.setattr(material, "_continuity_edit_chain_enabled", lambda: True)

    run(
        search_terms=["early state", "middle state", "final state"],
        scene_routes=["standard"] * 3,
        scene_subjects=["output"] * 3,
        scene_reference_targets=["output"] * 3,
        scene_includes_primary_subject=[False] * 3,
        scene_continuity_keys=["stable_output"] * 3,
        scene_continuity_descriptions=["the same printed scene and border"] * 3,
    )

    assert len(calls) == 3
    assert calls[0]["reference_images"] == []
    assert calls[1]["reference_images"] == ["root-uploaded.png"]
    assert calls[2]["reference_images"] == ["root-uploaded.png"]
    assert "middle-uploaded.png" not in calls[2]["reference_images"]
    assert diagnostics[-1]["plan_scenes"][1]["routing_reason"] == "continuity_edit_from_root"
    assert diagnostics[-1]["plan_scenes"][2]["continuity_source_scene"] == 1
