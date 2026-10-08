"""Coordinate validity/overlap are software checks, not perceptual accuracy."""
import copy
import json
import runpy
from pathlib import Path

import pytest
from PIL import Image

M = runpy.run_path(str(Path(__file__).parents[1] / "scripts/visual_location_observations.py"))
PROFILE = {"version": M["VERSION"], "components": {"contacts": "Each distinct visible physical attachment site"}}


def answer():
    return {"target_presence": {"status": "present", "evidence": "Visible target"},
            "components": {"contacts": {"state": "observed", "evidence": "Distinct visible sites",
                "locations": [{"box": [100, 100, 200, 200], "evidence": "Upper site"},
                              {"box": [100, 500, 200, 600], "evidence": "Lower site"}]}}}


def test_distinct_coordinate_entries_are_unverified_counts_only():
    result = M["coverage"](answer(), PROFILE)
    assert result["location_counts"]["contacts"] == 2
    assert result["overlapping_regions"] == [] and not result["pixel_truth_verified"]
    assert result["coordinate_system"] == "full-image-normalized-0-1000"
    comparison = M["compare"](answer(), answer(), PROFILE)
    assert comparison["status"] == "uncertain" and not comparison["admission_allowed"]
    assert not comparison["automatic_rejection"] and not comparison["physical_identity_established"]


@pytest.mark.parametrize("box", [[], [1, 2, 3], [1, 2, 3, 4, 5], [-1, 0, 5, 5], [0, 0, 1001, 5],
    [True, 0, 5, 5], [0.5, 0, 5, 5], [5, 0, 5, 5], [10, 0, 5, 5], [0, 10, 5, 5]])
def test_invalid_boxes_fail_without_clamping_or_repair(box):
    value = answer()
    value["components"]["contacts"]["locations"][0]["box"] = box
    with pytest.raises(ValueError):
        M["validate"](value, PROFILE)


@pytest.mark.parametrize("mutation", ["duplicate", "string_site", "missing_evidence", "extra_field", "absent_with_sites", "missing_component", "verdict"])
def test_malformed_site_or_applicability_fails(mutation):
    value = answer()
    c = value["components"]["contacts"]
    if mutation == "duplicate":
        c["locations"][1]["box"] = copy.deepcopy(c["locations"][0]["box"])
    elif mutation == "string_site":
        c["locations"][0] = "site description"
    elif mutation == "missing_evidence":
        c["locations"][0]["evidence"] = ""
    elif mutation == "extra_field":
        c["locations"][0]["confidence"] = 1
    elif mutation == "absent_with_sites":
        value["target_presence"]["status"] = "absent"
    elif mutation == "missing_component":
        value["components"] = {}
    else:
        value["verdict"] = "pass"
    with pytest.raises(ValueError):
        M["validate"](value, PROFILE)


def test_overlap_is_only_a_review_hint_not_merging_or_rejection():
    value = answer()
    value["components"]["contacts"]["locations"][1]["box"] = [150, 100, 250, 200]
    summary = M["coverage"](value, PROFILE)
    assert summary["location_counts"]["contacts"] == 2
    assert summary["overlapping_regions"][0]["intersection_over_union"] == pytest.approx(1 / 3)
    result = M["compare"](value, value, PROFILE)
    assert result["hints"] == [{"feature": "region_overlap", "kind": "overlapping_regions_need_review"}]
    assert result["status"] == "uncertain" and not result["automatic_rejection"]


@pytest.mark.parametrize("presence,state", [("absent", "not_applicable"), ("uncertain", "uncertain")])
def test_non_present_target_never_receives_identity_or_region_counts(presence, state):
    value = answer()
    value["target_presence"]["status"] = presence
    value["components"]["contacts"].update(state=state, locations=[])
    assert M["coverage"](value, PROFILE)["location_counts"]["contacts"] is None
    assert M["compare"](value, value, PROFILE)["status"] == "unavailable"


def test_uncertain_and_zero_observation_remain_incomplete_hints():
    value = answer()
    value["components"]["contacts"].update(state="uncertain", locations=[])
    assert M["compare"](value, value, PROFILE)["hints"][0]["kind"] == "insufficient_component_coverage"
    value["components"]["contacts"]["state"] = "absent"
    assert M["coverage"](value, PROFILE)["coverage"] == "no_observed_component"


def test_schema_and_prompt_explain_coordinates_without_answer_or_label(tmp_path):
    image = tmp_path / "image.png"
    Image.new("RGB", (16, 16), "red").save(image)
    profile = {**PROFILE, "private_note": "PRIVATE_ANNOTATION"}
    request = M["payload"](image, M["H"]["digest"](image), "object", profile)
    text = request["messages"][0]["content"][0]["text"]
    assert "PRIVATE_ANNOTATION" not in text and "expected_count" not in text
    assert "FULL image" in text and "[left,top,right,bottom]" in text
    assert request["max_tokens"] == 512 and request["temperature"] == 0
    branches = request["response_format"]["json_schema"]["schema"]["oneOf"]
    box = branches[0]["properties"]["components"]["properties"]["contacts"]["properties"]["locations"]["items"]["properties"]["box"]
    assert box["minItems"] == box["maxItems"] == 4
    assert box["items"] == {"type": "integer", "minimum": 0, "maximum": 1000}
    with pytest.raises(ValueError):
        M["payload"](image, "wrong", "object", profile)
