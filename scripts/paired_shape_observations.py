"""Paired shape diagnostics: no identity, admission or model dispatch authority."""
import base64
import hashlib
import io
import json
import time
from pathlib import Path

from PIL import Image

VERSION = "paired-major-shape-observations-1"

def prompt(target):
    if not isinstance(target, str) or not target.strip() or len(target) > 512:
        raise ValueError("Invalid target")
    return ("Compare only the visible shape and arrangement of major parts of the requested subject in image 1 (reference) "
            "and image 2 (candidate). Subject: " + target + ". A major change means a missing, added or fused principal part, "
            "or a clearly different overall form or arrangement. Ignore color, lighting, background, lettering and surface texture. "
            "Minor local size variations alone do not establish a major change. Object-name recognition alone does not establish "
            "shape preservation. If scale, perspective or occlusion prevents checking, report uncertain. State presence of the "
            "subject in each image, report major_shape_change as observed, not_observed or uncertain, and give short visible "
            "difference_evidence. not_observed is not proof of physical identity. Return only the specified JSON object.")

def schema():
    properties = {field: {"type": "string", "enum": ["present", "absent", "uncertain"]}
                  for field in ["reference_subject_presence", "candidate_subject_presence"]}
    properties.update(major_shape_change={"type": "string", "enum": ["observed", "not_observed", "uncertain"]},
                      difference_evidence={"type": "string"})
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}

def payload(reference, candidate, target):
    parts = [{"type": "text", "text": prompt(target)}]
    for image in [reference, candidate]:
        raw = Path(image["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != image["sha256"]:
            raise ValueError("Image changed")
        with Image.open(io.BytesIO(raw)) as opened:
            if opened.format != "PNG" or list(opened.size) != image["size"]:
                raise ValueError("Expected the pinned PNG and dimensions")
            opened.verify()
        parts.append({"type": "image_url", "image_url": {
            "url": "data:image/png;base64," + base64.b64encode(raw).decode()}})
    return {"model": "visual-judge", "messages": [{"role": "user", "content": parts}],
            "max_tokens": 256, "temperature": 0, "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "paired_major_shape", "strict": True, "schema": schema()}}}

def validate(answer):
    properties = schema()["properties"]
    if not isinstance(answer, dict) or set(answer) != set(properties):
        raise ValueError("Incomplete or extra observation fields")
    for field, description in properties.items():
        value = answer[field]
        if not isinstance(value, str) or not value.strip() or len(value) > 16384:
            raise ValueError("Invalid observation value")
        if "enum" in description and value not in description["enum"]:
            raise ValueError("Unknown observation category")
    if (answer["reference_subject_presence"] != "present" or answer["candidate_subject_presence"] != "present"):
        if answer["major_shape_change"] != "uncertain":
            raise ValueError("Shape comparison requires both subjects established")
    return dict(answer)

def parse_response(response):
    if not isinstance(response, dict) or not isinstance(response.get("choices"), list) or len(response["choices"]) != 1:
        raise ValueError("Expected one completed choice")
    choice = response["choices"][0]
    if not isinstance(choice, dict) or choice.get("finish_reason") != "stop" or not isinstance(choice.get("message"), dict):
        raise ValueError("Incomplete choice")
    message = choice["message"]
    content = message.get("content")
    if message.get("reasoning_content") not in (None, "") or not isinstance(content, str) or not content.strip():
        raise ValueError("Missing final content or unexpected reasoning")
    def unique_object(pairs):
        if len(dict(pairs)) != len(pairs):
            raise ValueError("Duplicate JSON field")
        return dict(pairs)
    return validate(json.loads(content, object_pairs_hook=unique_object))

def diagnostic(observation):
    value = validate(observation)
    established = all(value[field] == "present" for field in ["reference_subject_presence", "candidate_subject_presence"])
    result = {"version": VERSION, "status": "uncertain", "admission_allowed": False, "automatic_rejection": False,
              "physical_identity_established": False, "pixel_truth_verified": False, "hints": []}
    if not established:
        result["reason"] = "subject_not_established"
    elif value["major_shape_change"] == "observed":
        result["hints"] = [{"kind": "reported_major_shape_change", "evidence": value["difference_evidence"]}]
    return result

def collect(cases, target, request_fn, on_result=None):
    if not isinstance(cases, list) or not 1 <= len(cases) <= 3:
        raise ValueError("Cohort requires one to three predeclared cases")
    prompt(target)
    rows = []
    for case in cases:
        row = {"case_id": case["case_id"], "transport_status": "unavailable", "request_attempted": False}
        started = time.perf_counter()
        try:
            request = payload(case["reference"], case["candidate"], target)
            row["request_sha256"] = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False,
                                                             separators=(",", ":")).encode()).hexdigest()
            row["inputs"] = [{"role": role, "sha256": case[role]["sha256"]} for role in ["reference", "candidate"]]
            row["request_attempted"] = True
            reply = request_fn(request)
            if isinstance(reply, dict):
                choices = reply.get("choices")
                if isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict):
                    choice = choices[0]; message = choice.get("message")
                    if isinstance(message, dict):
                        row.update(final_content=message.get("content"), finish_reason=choice.get("finish_reason"),
                                   reasoning_characters=len(message.get("reasoning_content") or ""))
                row.update(usage=reply.get("usage"), server_timings=reply.get("timings"))
            row["observation"] = parse_response(reply)
            row["diagnostic"] = diagnostic(row["observation"])
            row["transport_status"] = "completed"
        except (OSError, ValueError, KeyError, TypeError) as exc:
            row["error_type"] = type(exc).__name__
        row["seconds"] = time.perf_counter() - started
        rows.append(row)
        if on_result:
            on_result(dict(row))
        if row["transport_status"] != "completed":
            break
    return rows
