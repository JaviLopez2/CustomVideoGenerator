"""No model, GPU or network calls: admission parsing and label isolation."""
import json
import runpy
from pathlib import Path

import pytest
from PIL import Image

HARNESS = runpy.run_path(str(Path(__file__).parents[1] / "scripts/evaluate_multimodal_judges.py"))
normalize = HARNESS["normalize"]


@pytest.mark.parametrize("count,status", [(2, "pass"), (3, "fail"), (0, "fail"), (None, "uncertain")])
def test_observed_count_decides_instead_of_claimed_verdict(count, status):
    contract = {"counts": [{"subject": "parts", "expected_count": 2}]}
    result = normalize({"counts": [{"subject": "parts", "observed_count": count,
                       "reason": "Observed separate components"}], "verdict": "pass"}, contract)
    assert result["verdict"] == status


@pytest.mark.parametrize("actual", [None, {}, {"subject": "other"},
    {"subject": "parts", "observed_count": True, "reason": "evidence"},
    {"subject": "parts", "observed_count": 2, "uncertain": "false", "reason": "evidence"}])
def test_invalid_response_does_not_pass(actual):
    with pytest.raises(ValueError):
        normalize({"counts": [actual]}, {"counts": [{"subject": "parts", "expected_count": 2}]})


def test_missing_structure_check_is_not_an_acceptance():
    with pytest.raises(ValueError):
        normalize({"counts": []}, {"geometry_constraints": ["part_arrangement"]})


def test_identity_does_not_substitute_for_temporal_state():
    answer = {"counts": [], "identity": {"status": "pass", "score": 1, "reason": "same shape"},
              "state": {"status": "uncertain", "score": None, "reason": "not visible"},
              "progression": {"status": "uncertain", "score": None, "reason": "only different light"}}
    assert normalize(answer, {"temporal": {"expected_state": "frosted"}})["verdict"] == "uncertain"


def test_expected_verdict_and_review_reason_are_not_sent(tmp_path):
    path = tmp_path / "sample.png"
    Image.new("RGB", (8, 8), "red").save(path)
    case = {"artifact": str(path), "sha256": HARNESS["digest"](path), "expected_verdict": "LABEL_SECRET",
            "review_reason": "REVIEW_SECRET", "contract": {"counts": [{"subject": "parts", "expected_count": 2}]}}
    parts, inputs = HARNESS["content"](case)
    payload = json.dumps(parts)
    assert "LABEL_SECRET" not in payload and "REVIEW_SECRET" not in payload
    assert len(inputs) == 1 and len([p for p in parts if p["type"] == "image_url"]) == 1
