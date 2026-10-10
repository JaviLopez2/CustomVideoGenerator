"""Experimental subject structure/state protocol, isolated from MPT admission."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import time

from PIL import Image

from scripts import paired_shape_observations as legacy

VERSION = "scoped-structure-state-observations-1"


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def validate_scope(value):
    if not isinstance(value, dict) or set(value) != {"subject", "protected_structure", "allowed_state_changes"}:
        raise ValueError("Expected only the declared subject/structure/state scope")
    for key, maximum in [("subject", 256), ("protected_structure", 512)]:
        if not isinstance(value[key], str) or not value[key].strip() or len(value[key]) > maximum:
            raise ValueError("Invalid subject or protected structure")
    states = value["allowed_state_changes"]
    if (not isinstance(states, list) or len(states) > 4
            or any(not isinstance(s, str) or not s.strip() or len(s) > 256 for s in states)
            or len({s.casefold().strip() for s in states}) != len(states)):
        raise ValueError("Invalid or duplicate allowed states")
    return copy.deepcopy(value)


def prompt(scope):
    declared = validate_scope(scope)
    return ("Compare image 1 (reference) and image 2 (candidate) using this declared scope: "
            + canonical(declared) + ". Inspect the visible form of the protected physical structure and connections "
            "between its principal parts. Describe visible structural evidence rather than relying on object names. "
            "A major structural change is a missing, added, fused or substantially deformed principal part or changed "
            "connection between principal parts. Minor local size differences alone do not establish a major change. "
            "Separately report visible change of only the declared allowed states; use not_applicable when none are declared. "
            "An allowed state never excuses a structural defect. If a difference cannot be assigned confidently to protected "
            "structure versus allowed state, report uncertain rather than ignoring it. Ignore lighting, color, surface texture, "
            "lettering and background. Perspective, scale, occlusion or cropping that prevents checking requires uncertainty. "
            "Report subject presence in each image, protected_structure_change and structural_connections_change as observed, "
            "not_observed or uncertain, and allowed_state_change separately. Give short structure_evidence and state_evidence. "
            "A connection change implies a structural change. not_observed does not prove identity or complete preservation. "
            "If either subject is not established, both structural comparisons must be uncertain, as must state comparison "
            "when states are declared. Return only the specified JSON object.")


def schema():
    properties = {key: {"type": "string", "enum": ["present", "absent", "uncertain"]}
                  for key in ["reference_subject_presence", "candidate_subject_presence"]}
    for key in ["protected_structure_change", "structural_connections_change"]:
        properties[key] = {"type": "string", "enum": ["observed", "not_observed", "uncertain"]}
    properties["allowed_state_change"] = {"type": "string", "enum": ["observed", "not_observed", "uncertain", "not_applicable"]}
    for key in ["structure_evidence", "state_evidence"]:
        properties[key] = {"type": "string"}
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def payload(reference, candidate, scope):
    declared = validate_scope(scope)
    for descriptor in [reference, candidate]:
        if not isinstance(descriptor, dict) or set(descriptor) != {"path", "sha256", "size"}:
            raise ValueError("Expected only pinned prepared image fields")
        if not isinstance(descriptor["path"], str) or not Path(descriptor["path"]).is_absolute():
            raise ValueError("Prepared image must use an absolute path")
    request = legacy.payload(reference, candidate, declared["subject"])
    for part in request["messages"][0]["content"][1:]:
        raw = base64.b64decode(part["image_url"]["url"].split(",", 1)[1], validate=True)
        # Metadata may follow IDAT; Image.open alone does not inspect that tail.
        offset, last_chunk = 8, None
        while offset < len(raw):
            if offset + 12 > len(raw):
                raise ValueError("Incomplete PNG chunk")
            length = int.from_bytes(raw[offset:offset + 4], "big")
            name = raw[offset + 4:offset + 8]
            end = offset + 12 + length
            if name not in {b"IHDR", b"IDAT", b"IEND"} or end > len(raw):
                raise ValueError("Unexpected ancillary or invalid PNG chunk")
            if name == b"IEND" and (length != 0 or end != len(raw)):
                raise ValueError("Trailing PNG data")
            offset, last_chunk = end, name
        if last_chunk != b"IEND":
            raise ValueError("Missing PNG end")
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if raw[24] != 8 or image.mode != "RGB" or image.info or image.getexif():
                raise ValueError("Expected explicitly prepared RGB8 PNG without ancillary metadata")
    request["messages"][0]["content"][0]["text"] = prompt(declared)
    request["max_tokens"] = 512
    request["response_format"]["json_schema"] = {"name": "scoped_structure_state", "strict": True, "schema": schema()}
    return request


def validate(answer, scope):
    declared = validate_scope(scope)
    properties = schema()["properties"]
    if not isinstance(answer, dict) or set(answer) != set(properties):
        raise ValueError("Incomplete or extra observation fields")
    for key, definition in properties.items():
        value = answer[key]
        if (not isinstance(value, str) or not value.strip() or len(value) > 16384
                or "enum" in definition and value not in definition["enum"]):
            raise ValueError("Invalid observation")
    if (answer["allowed_state_change"] == "not_applicable") != (not declared["allowed_state_changes"]):
        raise ValueError("State observation contradicts declared scope")
    if (answer["structural_connections_change"] == "observed"
            and answer["protected_structure_change"] != "observed"):
        raise ValueError("Connection change contradicts structure observation")
    if any(answer[key] != "present" for key in ["reference_subject_presence", "candidate_subject_presence"]):
        if (any(answer[key] != "uncertain" for key in ["protected_structure_change", "structural_connections_change"])
                or declared["allowed_state_changes"] and answer["allowed_state_change"] != "uncertain"):
            raise ValueError("Comparison requires both subjects established")
    return dict(answer)


def parse_response(reply, scope):
    if not isinstance(reply, dict) or not isinstance(reply.get("choices"), list) or len(reply["choices"]) != 1:
        raise ValueError("Expected one final choice")
    choice = reply["choices"][0]
    if not isinstance(choice, dict) or choice.get("finish_reason") != "stop" or not isinstance(choice.get("message"), dict):
        raise ValueError("Incomplete choice")
    message = choice["message"]
    if message.get("reasoning_content") not in (None, "") or not isinstance(message.get("content"), str):
        raise ValueError("Missing final content or unexpected reasoning")
    def unique(pairs):
        if len(dict(pairs)) != len(pairs):
            raise ValueError("Duplicate JSON field")
        return dict(pairs)
    return validate(json.loads(message["content"], object_pairs_hook=unique), scope)


def diagnostic(answer, scope):
    value = validate(answer, scope)
    result = {"version": VERSION, "status": "uncertain", "admission_allowed": False, "automatic_rejection": False,
              "physical_identity_established": False, "pixel_truth_verified": False,
              "allowed_state_observation": value["allowed_state_change"], "hints": []}
    if any(value[key] != "present" for key in ["reference_subject_presence", "candidate_subject_presence"]):
        result["reason"] = "subject_not_established"
    else:
        for key, kind in [("protected_structure_change", "reported_structure_change"),
                          ("structural_connections_change", "reported_connection_change")]:
            if value[key] == "observed":
                result["hints"].append({"kind": kind, "evidence": value["structure_evidence"]})
    return result


def collect(cases, request_fn, on_result=None):
    if not isinstance(cases, list) or not 1 <= len(cases) <= 3:
        raise ValueError("Expected one to three predeclared pairs")
    snapshot = copy.deepcopy(cases)
    identifiers = set()
    for case in snapshot:
        if (not isinstance(case, dict) or set(case) != {"case_id", "reference", "candidate", "scope"}
                or not isinstance(case["case_id"], str) or not case["case_id"].strip()
                or case["case_id"] in identifiers):
            raise ValueError("Invalid or duplicate case declaration")
        identifiers.add(case["case_id"])
        validate_scope(case["scope"])
    rows = []
    for case in snapshot:
        row = {"case_id": case["case_id"], "protocol": VERSION, "transport_status": "unavailable",
               "request_attempted": False, "scope_sha256": hashlib.sha256(canonical(case["scope"]).encode()).hexdigest(),
               "prepare_seconds": 0.0, "request_parse_seconds": 0.0}
        started, requested = time.perf_counter(), None
        try:
            request = payload(case["reference"], case["candidate"], case["scope"])
            row["request_sha256"] = hashlib.sha256(canonical(request).encode()).hexdigest()
            row["inputs"] = [{"role": role, "sha256": case[role]["sha256"]} for role in ["reference", "candidate"]]
            row["prepare_seconds"] = time.perf_counter() - started
            row["request_attempted"] = True
            requested = time.perf_counter()
            reply = request_fn(request)
            if isinstance(reply, dict):
                choices = reply.get("choices")
                row["raw_choices"] = copy.deepcopy(choices)
                if isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict):
                    choice = choices[0]
                    if isinstance(choice.get("message"), dict):
                        message = choice["message"]
                        reasoning = message.get("reasoning_content")
                        row.update(final_content=message.get("content"), finish_reason=choice.get("finish_reason"),
                                   reasoning_characters=len(reasoning) if isinstance(reasoning, str) else 0 if reasoning is None else None)
                row.update(usage=reply.get("usage"), server_timings=reply.get("timings"))
            row["observation"] = parse_response(reply, case["scope"])
            row["diagnostic"] = diagnostic(row["observation"], case["scope"])
            row["transport_status"] = "completed"
        except (OSError, ValueError, KeyError, TypeError) as exc:
            row["error_type"] = type(exc).__name__
        if requested is None:
            row["prepare_seconds"] = time.perf_counter() - started
        else:
            row["request_parse_seconds"] = time.perf_counter() - requested
        rows.append(row)
        if on_result:
            on_result(copy.deepcopy(row))
        if row["transport_status"] != "completed":
            break
    return rows
