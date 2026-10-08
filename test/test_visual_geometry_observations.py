"""Offline guarantees: independent observations cannot grant admission."""
import copy
import json
import runpy
from pathlib import Path

import pytest
from PIL import Image

M = runpy.run_path(str(Path(__file__).parents[1] / "scripts/observe_visual_geometry.py"))


def inventory():
    return {f: {"visibility": "present", "observed_count": 1, "description": "Visible physical feature"}
            for f in M["FEATURES"]}


def test_matching_observations_never_authorize_admission():
    result = M["compare"](inventory(), inventory())
    assert result["status"] == "uncertain" and result["admission_allowed"] is False
    assert result["hints"] == []


def test_presence_disagreement_is_only_a_review_hint():
    candidate = inventory()
    candidate["openings"].update(visibility="absent", observed_count=0)
    result = M["compare"](inventory(), candidate)
    assert result["hints"] == [{"feature": "openings", "kind": "presence_disagreement"}]
    assert result["status"] == "uncertain" and result["admission_allowed"] is False


def test_obscured_and_unknown_counts_are_not_matches():
    candidate = inventory()
    candidate["openings"].update(visibility="uncertain", observed_count=None)
    candidate["part_junctions"]["observed_count"] = None
    result = M["compare"](inventory(), candidate)
    assert {h["kind"] for h in result["hints"]} == {"insufficient_observation", "insufficient_count"}


@pytest.mark.parametrize("update", [
    {"visibility": "absent", "observed_count": 1},
    {"visibility": "present", "observed_count": 0},
    {"visibility": "uncertain", "observed_count": 1},
    {"observed_count": True}, {"observed_count": -1}, {"description": ""}])
def test_inconsistent_or_malformed_observation_is_rejected(update):
    answer = inventory()
    answer["openings"].update(update)
    with pytest.raises(ValueError):
        M["validate"](answer)


def test_verdict_and_missing_feature_are_rejected():
    answer = inventory()
    answer["verdict"] = "pass"
    with pytest.raises(ValueError):
        M["validate"](answer)
    del answer["verdict"]
    del answer["openings"]
    with pytest.raises(ValueError):
        M["validate"](answer)


def test_image_only_request_has_no_role_label_or_desired_count(tmp_path):
    path = tmp_path / "image.png"
    Image.new("RGB", (16, 16), "red").save(path)
    request = M["payload"](path, M["H"]["digest"](path), "target object")
    text = request["messages"][0]["content"][0]["text"]
    assert "expected_count" not in text and "expected_verdict" not in text
    assert len(request["messages"]) == 1
    assert len([p for p in request["messages"][0]["content"] if p["type"] == "image_url"]) == 1
    assert "verdict" not in M["schema"]()["properties"]
    path.write_bytes(b"changed")
    with pytest.raises(ValueError):
        M["payload"](path, "wrong-hash", "target object")


def plan():
    return {"target": "ceramic mug", "images": [{"path": "source.png", "sha256": "a" * 64}],
            "comparisons": [{"id": "self", "reference_sha256": "a" * 64, "candidate_sha256": "a" * 64}]}


@pytest.mark.parametrize("mutation", ["missing_target", "duplicate_image", "unknown_hash", "duplicate_pair"])
def test_general_plan_rejects_invalid_target_provenance_or_duplicates(mutation):
    p = plan()
    if mutation == "missing_target":
        p["target"] = ""
    elif mutation == "duplicate_image":
        p["images"].append(copy.deepcopy(p["images"][0]))
    elif mutation == "unknown_hash":
        p["comparisons"][0]["candidate_sha256"] = "b" * 64
    else:
        p["comparisons"].append(copy.deepcopy(p["comparisons"][0]))
    with pytest.raises(ValueError):
        M["validate_plan"](p)


def test_general_plan_metadata_never_reaches_pixel_request(tmp_path):
    image = tmp_path / "sample.png"
    Image.new("RGB", (16, 16), "red").save(image)
    p = plan()
    sha = M["H"]["digest"](image)
    p["images"][0] = {"path": str(image), "sha256": sha}
    p["comparisons"][0].update(reference_sha256=sha, candidate_sha256=sha,
                               original_label="LABEL_PRIVATE", reviewer_note="REVIEW_PRIVATE")
    p = M["validate_plan"](p)
    request = M["payload"](p["images"][0]["path"], sha, p["target"])
    serialized = json.dumps(request)
    assert "LABEL_PRIVATE" not in serialized and "REVIEW_PRIVATE" not in serialized
    assert p["target"] in serialized and "silver key" not in serialized


@pytest.mark.parametrize("component_mode", [False, True])
def test_decoding_contrast_changes_only_response_format(tmp_path, component_mode):
    image = tmp_path / "sample.png"
    Image.new("RGB", (16, 16), "red").save(image)
    sha = M["H"]["digest"](image)
    if component_mode:
        c = runpy.run_path(str(Path(__file__).parents[1] / "scripts/visual_component_observations.py"))
        request = c["payload"](image, sha, "target", {"version": c["CONDITIONAL_VERSION"],
                                 "components": {"contacts": "Distinct visible contact sites"}})
    else:
        request = M["payload"](image, sha, "target")
    original = copy.deepcopy(request)
    free = M["decoding_payload"](request, structured_output=False)
    assert request == original and "response_format" in request
    assert free == {k: v for k, v in original.items() if k != "response_format"}
    assert free["max_tokens"] == 512 and free["temperature"] == 0
    constrained = M["request_fingerprint"](request)
    unconstrained = M["request_fingerprint"](free)
    assert constrained["unconstrained_request_sha256"] == unconstrained["request_sha256"]
    assert constrained["prompt_sha256"] == unconstrained["prompt_sha256"]
    assert unconstrained["response_format_sha256"] is None
    assert M["decoding_payload"](request) == original
