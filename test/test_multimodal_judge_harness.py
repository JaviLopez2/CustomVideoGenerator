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


def test_schema_requires_exact_top_level_visual_fields():
    schema = HARNESS["response_schema"]({"counts": [{"subject": "parts", "expected_count": 2}],
        "geometry_constraints": ["silhouette"], "forbid_text": True, "temporal": {"expected_state": "frosted"}})
    assert set(schema["required"]) == {"counts", "geometry", "text", "identity", "state", "progression"}
    assert schema["additionalProperties"] is False
    assert schema["properties"]["counts"]["minItems"] == schema["properties"]["counts"]["maxItems"] == 1


def test_expected_verdict_and_review_reason_are_not_sent(tmp_path):
    path = tmp_path / "sample.png"
    Image.new("RGB", (8, 8), "red").save(path)
    case = {"artifact": str(path), "sha256": HARNESS["digest"](path), "expected_verdict": "LABEL_SECRET",
            "review_reason": "REVIEW_SECRET", "contract": {"counts": [{"subject": "parts", "expected_count": 2}]}}
    parts, inputs = HARNESS["content"](case)
    payload = json.dumps(parts)
    assert "LABEL_SECRET" not in payload and "REVIEW_SECRET" not in payload
    assert len(inputs) == 1 and len([p for p in parts if p["type"] == "image_url"]) == 1


def test_blind_count_probe_withholds_target_number(tmp_path):
    path = tmp_path / "sample.png"
    Image.new("RGB", (8, 8), "red").save(path)
    case = {"artifact": str(path), "sha256": HARNESS["digest"](path),
            "contract": {"counts": [{"subject": "components", "expected_count": 117, "tolerance": 4}]}}
    parts, _ = HARNESS["content"](case, blind_counts=True)
    payload = json.dumps(parts)
    assert "expected_count" not in payload and "117" not in payload and "tolerance" not in payload


def test_supplementary_region_cannot_come_from_another_candidate(tmp_path):
    path = tmp_path / "sample.png"
    Image.new("RGB", (8, 8), "red").save(path)
    case = {"artifact": str(path), "sha256": HARNESS["digest"](path), "contract": {}}
    with pytest.raises(ValueError):
        HARNESS["content"](case, regions=[{"source_sha256": "wrong-image"}])


def test_schema_string_bound_control_leaves_required_checks():
    contract = {"counts": [{"subject": "parts", "expected_count": 2}]}
    bounded = HARNESS["response_schema"](contract, concise=True)
    ordinary = HARNESS["response_schema"](contract)
    assert bounded["properties"]["counts"]["items"]["properties"]["reason"]["maxLength"] == 120
    assert "maxLength" not in ordinary["properties"]["counts"]["items"]["properties"]["reason"]
    assert bounded["required"] == ordinary["required"] == ["counts"]
