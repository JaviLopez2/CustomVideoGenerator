"""Presence/coverage is evidence, never a scene admission decision."""
import copy
import json
import runpy
from pathlib import Path

import pytest
from PIL import Image

M = runpy.run_path(str(Path(__file__).parents[1] / "scripts/visual_component_observations.py"))
PROFILE = {"version": M["VERSION"], "components": {"contacts": "Each distinct visible contact location"}}


def answer(presence="present"):
    state = {"present": "observed", "absent": "not_applicable", "uncertain": "uncertain"}[presence]
    return {"target_presence": {"status": presence, "evidence": "Pixel observation"},
            "components": {"contacts": {"state": state,
                "locations": ["upper contact", "lower contact"] if presence == "present" else [],
                "evidence": "Directly visible sites"}}}


def test_counts_come_from_distinct_location_entries():
    assert M["coverage"](answer(), PROFILE)["location_counts"]["contacts"] == 2


def test_absent_target_never_becomes_zero_components_of_a_valid_object():
    result = M["coverage"](answer("absent"), PROFILE)
    assert result["coverage"] == "not_applicable" and result["location_counts"]["contacts"] is None
    comparison = M["compare"](answer(), answer("absent"), PROFILE)
    assert comparison["status"] == "unavailable" and comparison["priority"] == "target_not_established"
    assert not comparison["admission_allowed"] and not comparison["automatic_rejection"]


def test_uncertain_target_cannot_be_rehabilitated_by_components():
    value = answer("uncertain")
    value["components"]["contacts"] = answer()["components"]["contacts"]
    with pytest.raises(ValueError):
        M["validate"](value, PROFILE)


@pytest.mark.parametrize("presence", ["absent", "uncertain"])
def test_matching_missing_targets_never_establish_identity(presence):
    result = M["compare"](answer(presence), answer(presence), PROFILE)
    assert result["status"] == "unavailable" and not result["physical_identity_established"]


@pytest.mark.parametrize("mutation", ["duplicate", "empty_observed", "absent_with_locations", "missing_component", "wrong_target", "verdict"])
def test_inconsistent_component_response_is_rejected(mutation):
    value = answer()
    c = value["components"]["contacts"]
    if mutation == "duplicate":
        c["locations"] = ["Upper contact", "  upper  contact "]
    elif mutation == "empty_observed":
        c["locations"] = []
    elif mutation == "absent_with_locations":
        c["state"] = "absent"
    elif mutation == "missing_component":
        value["components"] = {}
    elif mutation == "wrong_target":
        value["target_presence"]["status"] = "absent"
    else:
        value["verdict"] = "pass"
    with pytest.raises(ValueError):
        M["validate"](value, PROFILE)


def test_incomplete_coverage_remains_an_explicit_hint():
    candidate = answer()
    candidate["components"]["contacts"].update(state="uncertain", locations=[])
    result = M["compare"](answer(), candidate, PROFILE)
    assert result["hints"] == [{"feature": "contacts", "kind": "insufficient_component_coverage"}]
    assert result["status"] == "uncertain" and not result["admission_allowed"]


def test_complete_matching_locations_do_not_prove_pixel_truth():
    summary = M["coverage"](answer(), PROFILE)
    assert summary["coverage"] == "reported_complete" and not summary["pixel_truth_verified"]
    result = M["compare"](answer(), answer(), PROFILE)
    assert not result["admission_allowed"] and not result["physical_identity_established"]


def test_profile_has_definitions_without_desired_counts_or_review_metadata(tmp_path):
    path = tmp_path / "image.png"
    Image.new("RGB", (16, 16), "red").save(path)
    profile = copy.deepcopy(PROFILE)
    profile["private_review"] = "LABEL_SECRET"
    request = M["payload"](path, M["H"]["digest"](path), "generic object", profile)
    text = json.dumps(request)
    assert "LABEL_SECRET" not in text and "expected_count" not in text
    assert "observed_count" not in request["response_format"]["json_schema"]["schema"]["properties"]


def test_conditional_schema_cannot_emit_inapplicable_parts_for_present_target():
    profile = {**PROFILE, "version": M["CONDITIONAL_VERSION"]}
    result = M["schema"](profile)
    assert set(result) == {"oneOf"}
    for branch in result["oneOf"]:
        presence = branch["properties"]["target_presence"]["properties"]["status"]["enum"][0]
        component = branch["properties"]["components"]["properties"]["contacts"]["properties"]
        if presence == "present":
            assert "not_applicable" not in component["state"]["enum"]
        else:
            assert component["locations"]["maxItems"] == 0
            assert component["state"]["enum"] == ["not_applicable" if presence == "absent" else "uncertain"]


def test_legacy_component_schema_stays_distinct_from_conditional_protocol():
    assert "properties" in M["schema"](PROFILE)
    assert "oneOf" not in M["schema"](PROFILE)


def test_zero_observed_components_cannot_appear_as_complete_identity_evidence():
    value = answer()
    value["components"]["contacts"].update(state="absent", locations=[])
    summary = M["coverage"](value, PROFILE)
    assert summary["coverage"] == "no_observed_component"
    result = M["compare"](value, value, PROFILE)
    assert result["priority"] == "component_observation_review"
    assert result["hints"] == [{"feature": "component_coverage", "kind": "no_positive_component_observation"}]
    assert not result["physical_identity_established"] and not result["automatic_rejection"]


def test_explicit_format_supplies_schema_without_a_pixel_answer_or_count(tmp_path):
    image = tmp_path / "sample.png"
    Image.new("RGB", (16, 16), "red").save(image)
    profile = {**PROFILE, "version": M["CONDITIONAL_VERSION"], "review_note": "PRIVATE_LABEL"}
    sha = M["H"]["digest"](image)
    original = M["payload"](image, sha, "target", profile)
    explicit = M["payload"](image, sha, "target", profile, explicit_format=True)
    text = explicit["messages"][0]["content"][0]["text"]
    assert text.startswith(original["messages"][0]["content"][0]["text"])
    prompt_schema = json.loads(text.split("Output JSON Schema: ", 1)[1])
    assert prompt_schema == M["schema"]({**PROFILE, "version": M["VERSION"]})
    assert "PRIVATE_LABEL" not in text and "expected_count" not in text
    assert explicit["response_format"] == original["response_format"]
    assert explicit["messages"][0]["content"][1] == original["messages"][0]["content"][1]
    assert explicit["max_tokens"] == original["max_tokens"] == 512
