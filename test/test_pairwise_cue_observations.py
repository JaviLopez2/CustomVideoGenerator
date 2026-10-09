"""Generic cue/physical-state separation and zero-retry boundaries, CPU only."""
import base64
import copy
import hashlib
import json
from pathlib import Path

from PIL import Image
import pytest

from scripts import pairwise_cue_observations as observer


def answer(previous="not_observed", current="observed"):
    return {"previous_subject_presence": "present", "previous_cue_visibility": previous,
            "previous_evidence": "No clear requested cue in the visible region",
            "current_subject_presence": "present", "current_cue_visibility": current,
            "current_evidence": "A visible cue beside the subject"}


def response(value=None, **choice):
    return {"choices": [{"message": {"content": json.dumps(value or answer())}, "finish_reason": "stop", **choice}],
            "usage": {"completion_tokens": 70}}


@pytest.fixture
def images(tmp_path):
    result = []
    for name, color in [("previous", "red"), ("current", "blue")]:
        path = tmp_path / (name + ".png")
        Image.new("RGB", (16, 32), color).save(path)
        result.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                       "size": [16, 32], "offline_label": "CUE_LABEL_SENTINEL"})
    return result


def case(images, name="case0"):
    return {"case_id": name, "previous": images[0], "current": images[1],
            "offline_expected": "DO_NOT_SEND_EXPECTATION"}


def test_generic_prompt_and_schema_match_declared_method():
    design = json.loads((Path(__file__).parents[1] / "docs/validation/pairwise-visible-cue-design-2026-10-09.json").read_text(encoding="utf-8"))
    assert observer.prompt(design["subject"], design["cue_query"]) == design["model_prompt"]
    assert observer.schema() == design["response_schema"]
    alternative = observer.prompt("branch", "Visible frost crystals on the subject surface")
    assert "Subject: branch." in alternative and "frost crystals" in alternative
    assert "Subject: mug." not in alternative


@pytest.mark.parametrize("field,value", [("subject", ""), ("subject", " "), ("subject", None), ("subject", 3), ("subject", "x" * 513),
                                        ("cue_query", ""), ("cue_query", " "), ("cue_query", None), ("cue_query", 3), ("cue_query", "x" * 1025)])
def test_invalid_generic_query_never_dispatches(field, value):
    query = {"subject": "branch", "cue_query": "Visible material cue"}; query[field] = value
    with pytest.raises(ValueError): observer.prompt(**query)


def test_payload_preserves_png_order_and_keeps_annotations_offline(images):
    request = observer.payload(*images, "branch", "Visible material cue")
    parts = request["messages"][0]["content"]
    assert parts[0]["text"] == observer.prompt("branch", "Visible material cue")
    for part, expected in zip(parts[1:], images):
        raw = base64.b64decode(part["image_url"]["url"].split(",", 1)[1])
        assert hashlib.sha256(raw).hexdigest() == expected["sha256"]
    assert "CUE_LABEL_SENTINEL" not in json.dumps(request)
    assert request["max_tokens"] == 256 and request["temperature"] == 0
    assert request["chat_template_kwargs"] == {"enable_thinking": False}
    assert request["response_format"]["json_schema"]["schema"] == observer.schema()


@pytest.mark.parametrize("fault", ["missing", "extra", "enum", "type", "blank", "long", "absent_observed", "uncertain_absence"])
def test_invalid_or_contradictory_observation_is_rejected(fault):
    value = answer()
    if fault == "missing": value.pop("current_evidence")
    elif fault == "extra": value["temperature"] = "hot"
    elif fault == "enum": value["current_cue_visibility"] = "present"
    elif fault == "type": value["current_evidence"] = 3
    elif fault == "blank": value["current_evidence"] = " "
    elif fault == "long": value["current_evidence"] = "x" * 161
    elif fault == "absent_observed": value["current_subject_presence"] = "absent"
    else:
        value["previous_subject_presence"] = "uncertain"
        value["previous_cue_visibility"] = "not_observed"
    with pytest.raises(ValueError): observer.validate(value)


@pytest.mark.parametrize("fault", ["truncated", "reasoning", "duplicate_key", "multiple_choices", "non_json", "blank", "missing_message"])
def test_incomplete_reply_not_silently_normalized(fault):
    reply = response()
    if fault == "truncated": reply["choices"][0]["finish_reason"] = "length"
    elif fault == "reasoning": reply["choices"][0]["message"]["reasoning_content"] = "hidden analysis"
    elif fault == "duplicate_key": reply["choices"][0]["message"]["content"] = '{"current_evidence":"x","current_evidence":"y"}'
    elif fault == "multiple_choices": reply["choices"].append(copy.deepcopy(reply["choices"][0]))
    elif fault == "non_json": reply["choices"][0]["message"]["content"] = "No visible cue"
    elif fault == "blank": reply["choices"][0]["message"]["content"] = " "
    else: reply["choices"][0].pop("message")
    with pytest.raises(ValueError): observer.parse_response(reply)


@pytest.mark.parametrize("previous,current,transition", [
    ("not_observed", "observed", "reported_appearance"),
    ("observed", "not_observed", "reported_disappearance"),
    ("observed", "observed", "reported_visible_in_both"),
    ("not_observed", "not_observed", "reported_not_observed_in_both"),
    ("uncertain", "observed", None), ("observed", "uncertain", None),
])
def test_cue_pattern_never_certifies_physical_state_or_identity(previous, current, transition):
    value = observer.diagnostic(answer(previous, current))
    assert value["visible_transition"] == transition
    assert value["verdict"] == "uncertain"
    assert all(value[key] is None for key in ("identity_score", "state_score", "progression_score"))
    assert value["admission_allowed"] is False and value["automatic_rejection"] is False
    assert value["physical_identity_established"] is False and value["physical_temperature_measured"] is False


def test_absent_subject_preserves_uncertainty():
    value = answer("uncertain", "observed"); value["previous_subject_presence"] = "absent"
    result = observer.diagnostic(value)
    assert result["visible_transition"] is None and result["verdict"] == "uncertain"


@pytest.mark.parametrize("visibility", ["observed", "not_observed", "uncertain"])
def test_equal_byte_inputs_cannot_be_progression_proof(visibility):
    result = observer.diagnostic(answer(visibility, visibility), identical_inputs=True)
    assert result["input_consistency_violation"] is False
    assert result["visible_transition"] == "no_visible_change"
    assert result["progression_score"] is None and result["verdict"] == "uncertain"


def test_four_cases_complete_without_annotation_leak(images):
    calls = []
    def request(body): calls.append(body); return response()
    rows = observer.collect([case(images, f"case{i}") for i in range(4)], "branch", "Visible material cue", request)
    assert len(rows) == len(calls) == 4
    assert all(row["transport_status"] == "completed" and row["request_attempted"] for row in rows)
    assert "DO_NOT_SEND_EXPECTATION" not in json.dumps(calls)
    assert all(row["diagnostic"]["verdict"] == "uncertain" for row in rows)


def test_identical_control_inconsistency_is_kept_and_stops_cohort(images):
    first = case([images[0], images[0]], "self")
    calls, callbacks = [], []
    def request(body): calls.append(body); return response()  # Contradictory cue categories on identical bytes.
    rows = observer.collect([first, case(images)], "branch", "Visible material cue", request, callbacks.append)
    assert len(rows) == len(calls) == len(callbacks) == 1
    assert rows[0]["observation"] == answer()
    assert rows[0]["diagnostic"]["input_consistency_violation"] is True
    assert rows[0]["diagnostic"]["visible_transition"] is None
    assert rows[0]["transport_status"] == "unavailable" and rows[0]["error_type"] == "InputConsistencyViolation"


@pytest.mark.parametrize("fault", ["timeout", "truncated", "changed_image"])
def test_first_failure_stops_without_retry(images, fault):
    calls = []
    if fault == "changed_image": Path(images[0]["path"]).write_bytes(b"changed")
    def request(body):
        calls.append(body)
        if fault == "timeout": raise TimeoutError("test")
        return response(finish_reason="length")
    rows = observer.collect([case(images, "first"), case(images, "second")], "branch", "Visible material cue", request)
    assert len(rows) == 1 and rows[0]["transport_status"] == "unavailable"
    assert len(calls) == (0 if fault == "changed_image" else 1)


@pytest.mark.parametrize("cases", [[], [{}] * 5])
def test_outside_fixed_case_budget_rejected(cases):
    with pytest.raises(ValueError): observer.collect(cases, "branch", "Visible cue", lambda _: None)
