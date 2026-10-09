"""Evidence boundaries and zero-retry cohort behavior without GPU or network."""
import base64
import copy
import hashlib
import json

import pytest
from PIL import Image

from scripts import paired_shape_observations as observer


def answer(change="not_observed"):
    return {"reference_subject_presence": "present", "candidate_subject_presence": "present",
            "major_shape_change": change, "difference_evidence": "Visible principal parts compared"}


def response(value=None, **choice):
    return {"choices": [{"message": {"content": json.dumps(value or answer())},
                         "finish_reason": "stop", **choice}], "usage": {"completion_tokens": 40}}


@pytest.fixture
def images(tmp_path):
    descriptors = []
    for name, color in [("reference", "red"), ("candidate", "blue")]:
        path = tmp_path / (name + ".png")
        Image.new("RGB", (16, 32), color).save(path)
        descriptors.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "size": [16, 32], "offline_label": "HUMAN_LABEL_SENTINEL"})
    return descriptors


def test_prompt_and_schema_are_generic_and_match_pinned_plan():
    from pathlib import Path
    plan = json.loads((Path(__file__).parents[1] / "docs/validation/paired-shape-probe-plan-2026-10-09.json").read_text())
    assert observer.prompt(plan["subject"]) == plan["model_prompt"]
    assert observer.schema() == plan["response_schema"]
    assert "container" in observer.prompt("container")
    assert "Subject: key." not in observer.prompt("container")
    assert "verdict" not in observer.schema()["properties"]


@pytest.mark.parametrize("target", ["", " ", None, 3, "x" * 513])
def test_invalid_target_is_rejected(target):
    with pytest.raises(ValueError): observer.prompt(target)


def test_payload_preserves_exact_pixels_order_and_excludes_metadata(images):
    request = observer.payload(*images, "container")
    parts = request["messages"][0]["content"]
    assert parts[0]["text"] == observer.prompt("container")
    assert len(parts) == 3
    for part, image in zip(parts[1:], images):
        encoded = part["image_url"]["url"].split(",", 1)[1]
        assert hashlib.sha256(base64.b64decode(encoded)).hexdigest() == image["sha256"]
    assert "HUMAN_LABEL_SENTINEL" not in json.dumps(request)
    assert request["max_tokens"] == 256 and request["temperature"] == 0
    assert request["chat_template_kwargs"] == {"enable_thinking": False}
    assert request["response_format"]["json_schema"]["strict"] is True


@pytest.mark.parametrize("fault", ["hash", "size", "format"])
def test_changed_or_misidentified_input_is_rejected(images, fault):
    from pathlib import Path
    if fault == "hash": images[1]["sha256"] = "f" * 64
    elif fault == "size": images[1]["size"] = [32, 16]
    else:
        path = Path(images[1]["path"])
        Image.new("RGB", (16, 32)).save(path, format="JPEG")
        images[1]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError): observer.payload(*images, "container")


@pytest.mark.parametrize("change", ["observed", "not_observed", "uncertain"])
def test_all_valid_observations_remain_diagnostic_only(change):
    observation = observer.validate(answer(change))
    result = observer.diagnostic(observation)
    assert result["status"] == "uncertain"
    assert result["admission_allowed"] is result["automatic_rejection"] is False
    assert result["physical_identity_established"] is result["pixel_truth_verified"] is False
    assert bool(result["hints"]) == (change == "observed")


@pytest.mark.parametrize("update", [
    {"major_shape_change": True}, {"major_shape_change": "pass"},
    {"candidate_subject_presence": "unknown"}, {"reference_subject_presence": []},
    {"difference_evidence": ""}, {"difference_evidence": 1}, {"verdict": "pass"},
    {"candidate_subject_presence": "absent"}, {"reference_subject_presence": "uncertain"},
])
def test_invalid_or_contradictory_observation_is_rejected(update):
    value = answer(); value.update(update)
    with pytest.raises(ValueError): observer.validate(value)


def test_subject_not_established_only_supports_uncertainty():
    value = answer("uncertain"); value["candidate_subject_presence"] = "absent"
    result = observer.diagnostic(observer.validate(value))
    assert result["hints"] == [] and result["reason"] == "subject_not_established"


@pytest.mark.parametrize("fault", ["choices", "empty", "truncated", "reasoning", "markdown", "duplicate_key"])
def test_transport_and_json_failures_are_not_repaired(fault):
    reply = response()
    if fault == "choices": reply["choices"] = []
    elif fault == "empty": reply["choices"][0]["message"]["content"] = None
    elif fault == "truncated": reply["choices"][0]["finish_reason"] = "length"
    elif fault == "reasoning": reply["choices"][0]["message"]["reasoning_content"] = "hidden reasoning"
    elif fault == "markdown": reply["choices"][0]["message"]["content"] = "```json\n" + json.dumps(answer()) + "\n```"
    else: reply["choices"][0]["message"]["content"] = json.dumps(answer())[:-1] + ',"major_shape_change":"observed"}'
    with pytest.raises(ValueError): observer.parse_response(reply)


def test_successful_response_preserves_observation_without_identity_assertion():
    result = observer.parse_response(response(answer("observed")))
    assert result == answer("observed")


def cases(images):
    return [{"case_id": name, "reference": images[0], "candidate": images[1],
             "offline_expected_major_shape_change": "observed", "offline_human_review_verbatim": "LABEL_SENTINEL"}
            for name in ["one", "two", "three"]]


def test_collector_stops_first_invalid_preserving_partial_rows_and_no_retry(images):
    calls, saved = [], []
    def send(request):
        calls.append(request)
        return response() if len(calls) == 1 else response(finish_reason="length")
    rows = observer.collect(cases(images), "container", send, lambda row: saved.append(copy.deepcopy(row)))
    assert len(calls) == len(rows) == len(saved) == 2
    assert rows[0]["transport_status"] == "completed" and rows[1]["transport_status"] == "unavailable"
    assert rows[1]["finish_reason"] == "length" and rows[1]["final_content"]
    assert "LABEL_SENTINEL" not in json.dumps(calls)


def test_collector_times_out_once_and_preserves_unattempted_budget(images):
    calls = []
    def send(request):
        calls.append(request); raise TimeoutError("test timeout")
    rows = observer.collect(cases(images), "container", send)
    assert len(calls) == len(rows) == 1
    assert rows[0]["error_type"] == "TimeoutError" and rows[0]["transport_status"] == "unavailable"


def test_collector_does_not_dispatch_changed_image(images):
    images[0]["sha256"] = "f" * 64
    calls = []
    rows = observer.collect(cases(images), "container", lambda request: calls.append(request))
    assert not calls and len(rows) == 1 and rows[0]["request_attempted"] is False


def test_collector_enforces_predeclared_maximum_before_any_dispatch(images):
    calls = []
    with pytest.raises(ValueError):
        observer.collect(cases(images) + cases(images), "container", lambda request: calls.append(request))
    assert not calls
