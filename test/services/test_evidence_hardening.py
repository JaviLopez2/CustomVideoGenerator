from app.services import llm
from test.services.test_evidence_semantic_fallback import rejected, plan, assert_clean


def test_generic_overlap_does_not_prove_specialized_concept():
    inventory = [{"role": "detail", "description": "close front controls and panel"}]
    ok, reason = llm._reference_role_has_semantic_evidence(
        inventory, "detail", "close detail of front controls showing turbine placement")
    assert not ok
    assert "turbine" in reason


def test_all_discriminating_concepts_must_be_supported():
    query = "close turbine bearing detail"
    assert not llm._reference_role_has_semantic_evidence(
        [{"role": "detail", "description": "turbine exterior"}], "detail", query)[0]
    assert llm._reference_role_has_semantic_evidence(
        [{"role": "detail", "description": "turbine bearing visible"}], "detail", query)[0]


def test_generic_query_cannot_establish_specialized_evidence():
    assert not llm._reference_role_has_semantic_evidence(
        [{"role": "detail", "description": "front close detail"}],
        "detail", "front close detail")[0]


def test_presentation_wording_and_plural_variation_preserve_concepts():
    inventory = [{"role": "detail", "description": "visible turbine bearing"}]
    assert llm._reference_role_has_semantic_evidence(
        inventory, "detail", "reference illustration clearly depicting turbine bearings")[0]
    assert not llm._reference_role_has_semantic_evidence(
        inventory, "detail", "reference illustration clearly depicting turbine bearings and seals")[0]


def test_visible_result_survives_primary_identity_fallback():
    exterior = rejected(scene_description="closed exterior of sealed motor", reference_need="identity",
                        evidence_scope="externally_visible", required_features=[],
                        safe_visual_alternative="", continuity_key="none", continuity_description="")
    hidden = rejected(observable_result="signal lamp", observable_state="steady amber glow",
                      observable_context="on the desk")
    scene = plan([exterior, hidden], ["The sealed motor.",
                 "An internal mechanism works. The signal lamp has a steady amber glow on the desk."])[1]
    assert scene["canonical_subject"] == "signal lamp"
    assert "steady amber glow" in scene["prompt"]
    assert "on the desk" in scene["prompt"]
    assert scene["reference_target"] == "output"
    assert scene["reference_need"] == "none"
    assert scene["route"] == "standard"
    assert_clean(scene)


def test_rejected_alternative_cannot_supply_result_or_context():
    scene = plan([rejected(observable_result="twin gears", observable_context="spraying lubricant")],
                 ["The sealed motor is on a desk."])[0]
    assert_clean(scene)
