"""Experimental generic visible-cue observations; no perceptual admission."""
import copy
import hashlib
import json
import time

from scripts import paired_shape_observations as images

VERSION = "pairwise-visible-cue-observations-1"

def prompt(subject, cue_query):
    for value, limit in [(subject, 512), (cue_query, 1024)]:
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError("Invalid subject/cue query")
    return ("Compare the requested visible cue in image 1 (previous frame) and image 2 (current frame). Subject: "
            + subject + ". Requested cue: " + cue_query +
            " State subject presence and cue_visibility separately for each image. Use observed only for a visibly associated cue, "
            "not color, lighting, object name or expectation. not_observed means the cue is not seen in the visible relevant area, "
            "not a claim of global physical absence. If the relevant area is obstructed, dark or ambiguous, or the subject is not "
            "established, use uncertain for its cue. Give a short visible evidence description for each frame. Do not infer physical "
            "temperature, chemical cause, liquid motion, elapsed time, physical identity or successful progression. "
            "Return only the specified JSON object.")

def schema():
    properties = {}
    for role in ("previous", "current"):
        properties[role + "_subject_presence"] = {"type": "string", "enum": ["present", "absent", "uncertain"]}
        properties[role + "_cue_visibility"] = {"type": "string", "enum": ["observed", "not_observed", "uncertain"]}
        properties[role + "_evidence"] = {"type": "string", "minLength": 1, "maxLength": 160}
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}

def payload(previous, current, subject, cue_query):
    text = prompt(subject, cue_query)
    request = images.payload(previous, current, subject)  # Reuse pinned-byte PNG loading/order/decoding flags.
    request["messages"][0]["content"][0]["text"] = text
    request["response_format"]["json_schema"] = {"name": "pairwise_visible_cue", "strict": True, "schema": schema()}
    return request

def validate(value):
    properties = schema()["properties"]
    if not isinstance(value, dict) or set(value) != set(properties):
        raise ValueError("Missing or extra cue fields")
    for field, description in properties.items():
        item = value[field]
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Invalid cue value")
        if "enum" in description and item not in description["enum"]:
            raise ValueError("Unknown cue category")
        if "maxLength" in description and len(item) > description["maxLength"]:
            raise ValueError("Cue evidence too long")
    for role in ("previous", "current"):
        if value[role + "_subject_presence"] != "present" and value[role + "_cue_visibility"] != "uncertain":
            raise ValueError("Cue visibility requires established subject")
    return dict(value)

def parse_response(reply):
    if not isinstance(reply, dict) or not isinstance(reply.get("choices"), list) or len(reply["choices"]) != 1:
        raise ValueError("Expected one completed choice")
    choice = reply["choices"][0]
    if not isinstance(choice, dict) or choice.get("finish_reason") != "stop" or not isinstance(choice.get("message"), dict):
        raise ValueError("Incomplete cue reply")
    message = choice["message"]
    content = message.get("content")
    if message.get("reasoning_content") not in (None, "") or not isinstance(content, str) or not content.strip():
        raise ValueError("Missing final content or unexpected reasoning")
    def unique(pairs):
        if len(dict(pairs)) != len(pairs):
            raise ValueError("Duplicate cue field")
        return dict(pairs)
    return validate(json.loads(content, object_pairs_hook=unique))

def diagnostic(value, *, identical_inputs=False):
    value = validate(value)
    result = {"version": VERSION, "verdict": "uncertain", "identity_score": None, "state_score": None,
              "progression_score": None, "admission_allowed": False, "automatic_rejection": False,
              "physical_identity_established": False, "physical_temperature_measured": False,
              "visible_transition": None, "input_consistency_violation": False}
    if identical_inputs:
        same = all(value["previous_" + field] == value["current_" + field]
                   for field in ("subject_presence", "cue_visibility"))
        result.update(input_consistency_violation=not same, visible_transition="no_visible_change" if same else None,
                      reason="exact_input_consistency" if same else "inconsistent_categories_on_identical_inputs")
        return result
    if any(value[role + "_subject_presence"] != "present" or value[role + "_cue_visibility"] == "uncertain"
           for role in ("previous", "current")):
        result["reason"] = "cue_evidence_not_established"
        return result
    patterns = {("not_observed", "observed"): "reported_appearance", ("observed", "not_observed"): "reported_disappearance",
                ("observed", "observed"): "reported_visible_in_both", ("not_observed", "not_observed"): "reported_not_observed_in_both"}
    result["visible_transition"] = patterns[(value["previous_cue_visibility"], value["current_cue_visibility"])]
    result["reason"] = "reported_visible_cue_pattern_only"
    return result

def collect(cases, subject, cue_query, request_fn, on_result=None):
    if not isinstance(cases, list) or not 1 <= len(cases) <= 4:
        raise ValueError("One to four declared cue cases required")
    prompt(subject, cue_query)
    rows = []
    for case in cases:
        row = {"case_id": case["case_id"], "transport_status": "unavailable", "request_attempted": False}
        started = time.perf_counter()
        try:
            body = payload(case["previous"], case["current"], subject, cue_query)
            row["request_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
            row["inputs"] = [{"role": role, "sha256": case[role]["sha256"]} for role in ("previous", "current")]
            row["request_attempted"] = True
            reply = request_fn(body)
            if isinstance(reply, dict):
                choices = reply.get("choices")
                if isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict):
                    choice = choices[0]; message = choice.get("message")
                    if isinstance(message, dict):
                        row.update(final_content=message.get("content"), finish_reason=choice.get("finish_reason"),
                                   reasoning_characters=len(message.get("reasoning_content") or ""))
                row.update(usage=reply.get("usage"), server_timings=reply.get("timings"))
            row["observation"] = parse_response(reply)
            row["diagnostic"] = diagnostic(row["observation"], identical_inputs=case["previous"]["sha256"] == case["current"]["sha256"])
            if row["diagnostic"]["input_consistency_violation"]:
                row["error_type"] = "InputConsistencyViolation"
            else:
                row["transport_status"] = "completed"
        except (OSError, ValueError, KeyError, TypeError) as exc:
            row["error_type"] = type(exc).__name__
        row["seconds"] = time.perf_counter() - started
        rows.append(row)
        if on_result:
            on_result(copy.deepcopy(row))
        if row["transport_status"] != "completed":
            break
    return rows
