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
