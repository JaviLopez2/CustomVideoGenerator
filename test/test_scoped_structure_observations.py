"""CPU regressions for explicit structure/state scope; no visual inference."""
import base64
import copy
import hashlib
import json
import zlib
from unittest.mock import Mock

import pytest
from PIL import Image, PngImagePlugin

from scripts import scoped_structure_observations as observer


def scope(subject="tool", states=()):
    return {"subject": subject, "protected_structure": "The subject's inherent physical parts and their connections.",
            "allowed_state_changes": list(states)}


def answer(structure="not_observed", connections="not_observed", state="not_applicable"):
    return {"reference_subject_presence": "present", "candidate_subject_presence": "present",
            "protected_structure_change": structure, "structural_connections_change": connections,
            "allowed_state_change": state, "structure_evidence": "Visible parts and their connections compared.",
            "state_evidence": "No state change declared."}


def response(value=None, reason="stop"):
    return {"choices": [{"finish_reason": reason, "message": {"content": json.dumps(value or answer())}}]}


@pytest.fixture
def images(tmp_path):
    values = []
    for name, color in [("reference", "red"), ("candidate", "blue")]:
        p = tmp_path / (name + ".png")
        Image.new("RGB", (16, 32), color).save(p)
        values.append({"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "size": [16, 32]})
    return values


def cases(images):
    return [{"case_id": name, "reference": images[0], "candidate": images[1], "scope": scope()}
            for name in ["one", "two", "three"]]


@pytest.mark.parametrize("subject,states", [
    ("camera", ["photographic output emerging while printing"]),
    ("container", ["visible vapor rising from contents"]),
    ("tool", []),
])
def test_declared_scope_is_generic_and_part_of_request_binding(images, subject, states):
    declared = scope(subject, states)
    request = observer.payload(*images, declared)
    assert declared == scope(subject, states)
    text = request["messages"][0]["content"][0]["text"]
    assert subject in text and declared["protected_structure"] in text
    assert all(state in text for state in states)
    assert request["max_tokens"] == 512 and request["temperature"] == 0
    assert request["chat_template_kwargs"] == {"enable_thinking": False}
    assert request["response_format"]["json_schema"]["schema"] == observer.schema()
    for part, desc in zip(request["messages"][0]["content"][1:], images):
        assert base64.b64decode(part["image_url"]["url"].split(",", 1)[1]) == open(desc["path"], "rb").read()
    changed = observer.payload(*images, scope(subject, ["a different allowed state"]))
    assert json.dumps(request, sort_keys=True) != json.dumps(changed, sort_keys=True)


@pytest.mark.parametrize("update", [
    {"subject": ""}, {"protected_structure": " "}, {"allowed_state_changes": "steam"},
    {"allowed_state_changes": ["state", " STATE "]}, {"allowed_state_changes": ["x"] * 5},
    {"expected_answer": "HUMAN_LABEL_SENTINEL"},
])
def test_invalid_or_label_bearing_scope_rejected_before_request(images, update):
    data = cases(images); data[0]["scope"].update(update)
    send = Mock()
    with pytest.raises(ValueError): observer.collect(data, send)
    send.assert_not_called()


@pytest.mark.parametrize("change", ["observed", "not_observed", "uncertain"])
def test_reported_structure_never_certifies_identity_or_admission(change):
    result = observer.diagnostic(answer(change), scope())
    assert result["status"] == "uncertain"
    assert result["admission_allowed"] is result["automatic_rejection"] is False
    assert result["physical_identity_established"] is result["pixel_truth_verified"] is False
    assert bool(result["hints"]) == (change == "observed")


def test_state_observation_does_not_override_a_reported_structural_change():
    declared = scope("device", ["output emerges"])
    value = answer("observed", "observed", "observed")
    result = observer.diagnostic(value, declared)
    assert [hint["kind"] for hint in result["hints"]] == ["reported_structure_change", "reported_connection_change"]
    assert result["allowed_state_observation"] == "observed" and result["status"] == "uncertain"


@pytest.mark.parametrize("value,declared", [
    (answer("not_observed", "observed"), scope()),
    (answer(state="observed"), scope()),
    (answer(state="not_applicable"), scope(states=["output emerges"])),
    ({**answer(), "candidate_subject_presence": "uncertain"}, scope()),
    ({**answer(), "verdict": "pass"}, scope()),
])
def test_contradictory_or_extra_answer_not_rehabilitated(value, declared):
    with pytest.raises(ValueError): observer.validate(value, declared)


def test_unestablished_subject_only_has_uncertain_comparison():
    value = answer("uncertain", "uncertain"); value["candidate_subject_presence"] = "absent"
    result = observer.diagnostic(value, scope())
    assert not result["hints"] and result["reason"] == "subject_not_established"


@pytest.mark.parametrize("fault", ["length", "reasoning", "duplicate", "markdown"])
def test_incomplete_or_nonfinal_json_is_not_repaired(fault):
    reply = response()
    message = reply["choices"][0]["message"]
    if fault == "length": reply["choices"][0]["finish_reason"] = "length"
    elif fault == "reasoning": message["reasoning_content"] = "reasoning"
    elif fault == "duplicate": message["content"] = message["content"][:-1] + ',"protected_structure_change":"observed"}'
    else: message["content"] = "```json\n" + message["content"] + "\n```"
    with pytest.raises(ValueError): observer.parse_response(reply, scope())


def test_collector_keeps_raw_invalid_reply_stops_and_never_retries(images):
    data, saved = cases(images), []
    send = Mock(side_effect=[response(), response(reason="length")])
    rows = observer.collect(data, send, saved.append)
    assert send.call_count == len(rows) == len(saved) == 2
    assert rows[0]["transport_status"] == "completed" and rows[1]["transport_status"] == "unavailable"
    assert rows[1]["finish_reason"] == "length" and rows[1]["final_content"]
    assert all(row["scope_sha256"] and row["request_sha256"] for row in rows)
    assert all(row["prepare_seconds"] >= 0 and row["request_parse_seconds"] >= 0 for row in rows)


def test_changed_second_input_stops_before_second_http(images):
    def send(request):
        with open(images[1]["path"], "ab") as handle: handle.write(b"changed")
        return response()
    request = Mock(side_effect=send)
    rows = observer.collect(cases(images), request)
    assert request.call_count == 1 and len(rows) == 2
    assert rows[1]["transport_status"] == "unavailable" and rows[1]["request_attempted"] is False


def test_callback_or_request_cannot_mutate_declared_scope_of_later_case(images):
    data = cases(images)
    requests = []
    def send(request):
        requests.append(copy.deepcopy(request))
        data[1]["scope"]["allowed_state_changes"] = ["UNDECLARED_STATE_SENTINEL"]
        return response()
    rows = observer.collect(data, send)
    assert len(rows) == 3 and all(row["transport_status"] == "completed" for row in rows)
    assert "UNDECLARED_STATE_SENTINEL" not in json.dumps(requests)


def test_prompt_ancillary_metadata_rejected_before_http(images):
    p = images[0]["path"]
    metadata = PngImagePlugin.PngInfo(); metadata.add_text("prompt", "PRIVATE_METADATA_SENTINEL")
    Image.new("RGB", (16, 32), "red").save(p, pnginfo=metadata)
    images[0]["sha256"] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    send = Mock()
    rows = observer.collect(cases(images), send)
    assert rows[0]["request_attempted"] is False and rows[0]["transport_status"] == "unavailable"
    send.assert_not_called()


@pytest.mark.parametrize("position", ["before_iend", "after_iend"])
def test_trailing_png_text_cannot_reach_request(images, position):
    from pathlib import Path
    p = Path(images[0]["path"]); raw = p.read_bytes()
    text = b"prompt\x00PRIVATE_METADATA_SENTINEL"
    body = b"tEXt" + text
    chunk = len(text).to_bytes(4, "big") + body + zlib.crc32(body).to_bytes(4, "big")
    p.write_bytes(raw[:-12] + chunk + raw[-12:] if position == "before_iend" else raw + chunk)
    images[0]["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    send = Mock()
    rows = observer.collect(cases(images), send)
    assert rows[0]["request_attempted"] is False and rows[0]["transport_status"] == "unavailable"
    send.assert_not_called()


@pytest.mark.parametrize("fault", ["multiple_choices", "numeric_reasoning"])
def test_invalid_response_retains_all_raw_choices_before_validation(images, fault):
    reply = response()
    if fault == "multiple_choices": reply["choices"].append(copy.deepcopy(reply["choices"][0]))
    else: reply["choices"][0]["message"]["reasoning_content"] = 7
    saved=[]
    send = Mock(return_value=reply)
    rows = observer.collect(cases(images), send, saved.append)
    assert send.call_count == len(rows) == len(saved) == 1
    assert rows[0]["transport_status"] == "unavailable"
    assert rows[0]["raw_choices"] == saved[0]["raw_choices"] == reply["choices"]
