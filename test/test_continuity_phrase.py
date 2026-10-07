"""Planner regressions for continuity identity wording, with no live LLM calls."""

import json
from unittest.mock import patch

import pytest

from app.services import llm


@pytest.mark.parametrize("description", [
    "same NASA panel", "the same NASA panel", "Same NASA panel",
    "THE SAME NASA panel", "NASA panel",
])
@pytest.mark.parametrize("temporal", [False, True])
def test_planner_preserves_named_identity_without_duplicate_same(description, temporal):
    row = {
        "subject": "instrument panel", "canonical_subject": "instrument panel",
        "scene_description": "an instrument panel planner-47",
        "planner_id": "planner-47", "continuity_key": "internal_group_29",
        "continuity_description": description, "reference_need": "none",
        "reference_target": "output", "evidence_scope": "externally_visible",
        "temporal_progression": temporal,
    }
    narration = "An instrument panel."
    if temporal:
        row.update(observable_state="faint amber outline", visual_state="faint amber outline")
        narration = "The instrument panel shows a faint amber outline."
    with patch.object(llm, "_generate_response", return_value=json.dumps([row])):
        scene = llm.generate_scene_image_plan(
            "instrument panel", [{"narration": narration}], app_config={},
        )[0]
    prompt = scene["prompt"]
    assert "The same NASA panel" in prompt
    assert "same same" not in prompt.casefold()
    assert "NASA panel" in scene["continuity_description"]
    assert scene["continuity_key"] == "internal_group_29"
    assert "internal_group_29" not in prompt and "planner-47" not in prompt
    if temporal:
        assert "is visible with faint amber outline" in prompt
        assert scene["temporal_progression"] is True
    else:
        assert "remains the visible continuity target" in prompt
