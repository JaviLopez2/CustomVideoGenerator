"""Offline coverage-gate regressions; no image service calls."""
import json
from unittest.mock import patch

import pytest

from app.services import llm


INVENTORY = [{"role": "identity", "description": "whole primary device"}]


def rejected(**changes):
    return {
        "subject": "sealed motor", "canonical_subject": "sealed motor",
        "scene_description": "twin gears spraying lubricant inside the housing",
        "reference_need": "internal", "reference_target": "primary_subject",
        "evidence_scope": "hidden_internal", "route": "precision",
        "required_features": ["twin gears"],
        "safe_visual_alternative": "twin gears spraying lubricant outside the housing",
        "continuity_key": "rejected_mechanism",
        "continuity_description": "twin gears spraying lubricant",
        **changes,
    }


def plan(rows, narrations):
    with patch.object(llm, "_generate_response", side_effect=[json.dumps(rows)] * 2) as generate:
        result = llm.generate_scene_image_plan(
            "device", [{"narration": n} for n in narrations],
            reference_inventory=INVENTORY, app_config={},
        )
    assert len(result) == len(rows)
    assert generate.call_count == 2  # Existing planner + audit, no additional LLM.
    return result


def assert_clean(scene):
    for key in ("prompt", "safe_visual_alternative", "canonical_subject", "reference_query",
                "continuity_description"):
        assert "twin gears" not in scene[key]
        assert "spraying lubricant" not in scene[key]
    assert scene["required_features"] == []
    assert scene["continuity_key"] == "none"


def test_observable_subject_and_state_survive_rejected_mechanism():
    scene = plan([rejected(observable_subject="sealed motor", observable_state="red exterior")],
                 ["The sealed motor has a red exterior."])[0]
    assert scene["planner_validation"] == "coverage_fallback"
    assert scene["canonical_subject"] == "sealed motor"
    assert "red exterior" in scene["prompt"]
    assert "externally visible result or context" not in scene["prompt"]
    assert_clean(scene)


def test_output_progression_is_grounded_in_original_language():
    scene = plan([rejected(reference_target="output", canonical_subject="chemical reaction",
                           observable_subject="la fotografía", observable_state="aparecen formas y color")],
                 ["En la fotografía aparecen formas y color."])[0]
    assert scene["canonical_subject"] == "la fotografía"
    assert "aparecen formas y color" in scene["prompt"]
    assert scene["reference_target"] == "output"
    assert scene["reference_need"] == "none"
    assert_clean(scene)


@pytest.mark.parametrize("state", ["twin gears spraying lubricant", "invented bright blue surface"])
def test_rejected_alternative_is_not_a_grounding_source(state):
    scene = plan([rejected(observable_subject="sealed motor", observable_state=state,
                           safe_visual_alternative=state)], ["The sealed motor is on a table."])[0]
    assert state not in scene["prompt"]
    assert scene["canonical_subject"] == "sealed motor"
    assert_clean(scene)


def test_even_literal_hidden_claim_is_not_preserved_as_observable():
    scene = plan([rejected(observable_subject="twin gears", observable_state="spraying lubricant")],
                 ["Inside the sealed motor, twin gears are spraying lubricant."])[0]
    # An observable noun alone is not sufficient evidence for its asserted action.
    assert_clean(scene)


def test_covered_identity_survives_without_rejected_mechanism():
    identity = rejected(scene_description="closed exterior of sealed motor", reference_need="identity",
                        evidence_scope="externally_visible", required_features=[],
                        safe_visual_alternative="", continuity_key="none", continuity_description="")
    scene = plan([identity, rejected()], ["A sealed motor.", "Its hidden mechanism works."])[1]
    assert scene["canonical_subject"] == "sealed motor"
    assert scene["route"] == "precision"
    assert scene["reference_need"] == "identity"
    assert "closed exterior documentary view of sealed motor" in scene["prompt"]
    assert_clean(scene)


@pytest.mark.parametrize("critical", [False, True])
def test_ordinary_output_is_not_rejected_for_primary_only_pack(critical):
    row = {"reference_target": "output", "reference_need": "none",
           "evidence_scope": "externally_visible", "reference_critical": critical,
           "scene_description": "a finished print on a desk"}
    assert llm._scene_reference_coverage(row, INVENTORY)[0] == "covered"


@pytest.mark.parametrize("need,scope", [("identity", "externally_visible"),
                                        ("none", "specialized_visible"),
                                        ("internal", "hidden_internal")])
def test_output_exception_does_not_bypass_specialized_evidence(need, scope):
    row = {"reference_target": "output", "reference_need": need,
           "evidence_scope": scope, "reference_critical": True}
    assert llm._scene_reference_coverage(row, INVENTORY)[0] == "unsupported"


def test_output_hidden_claim_does_not_use_ordinary_output_exception():
    row = {"reference_target": "output", "reference_need": "none",
           "evidence_scope": "externally_visible", "reference_critical": True,
           "scene_description": "cutaway with internal gears"}
    assert llm._scene_reference_coverage(row, INVENTORY)[0] == "unsupported"
