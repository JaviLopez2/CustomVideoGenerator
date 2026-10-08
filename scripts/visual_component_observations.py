"""Target presence and per-location coverage, separate from geometry admission."""
import base64
import copy
import json
import runpy
from pathlib import Path

H = runpy.run_path(str(Path(__file__).with_name("evaluate_multimodal_judges.py")))
VERSION = "target-component-observations-1"
CONDITIONAL_VERSION = "target-component-observations-2"
COVERAGE_VERSION = "component-location-coverage-2"


def validate_profile(profile):
    if not isinstance(profile, dict) or profile.get("version") not in {VERSION, CONDITIONAL_VERSION}:
        raise ValueError("Unknown component protocol")
    components = profile.get("components")
    if not isinstance(components, dict) or not 1 <= len(components) <= 16:
        raise ValueError("Invalid components")
    if any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip()
           for k, v in components.items()):
        raise ValueError("Missing component definition")
    return profile


def schema(profile):
    validate_profile(profile)
    presence = {"type": "object", "properties": {
        "status": {"type": "string", "enum": ["present", "absent", "uncertain"]},
        "evidence": {"type": "string"}}, "required": ["status", "evidence"], "additionalProperties": False}
    component = {"type": "object", "properties": {
        "state": {"type": "string", "enum": ["observed", "absent", "uncertain", "not_applicable"]},
        "locations": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "string"}}, "required": ["state", "locations", "evidence"], "additionalProperties": False}
    basic = {"type": "object", "properties": {"target_presence": presence,
        "components": {"type": "object", "properties": {k: component for k in profile["components"]},
                       "required": list(profile["components"]), "additionalProperties": False}},
        "required": ["target_presence", "components"], "additionalProperties": False}
    if profile["version"] == VERSION:
        return basic
    # oneOf branches, not unsupported if/then conditionals or sibling properties.
    branches = []
    for status in ["present", "absent", "uncertain"]:
        branch = copy.deepcopy(basic)
        branch["properties"]["target_presence"]["properties"]["status"]["enum"] = [status]
        for field in branch["properties"]["components"]["properties"].values():
            if status == "present":
                field["properties"]["state"]["enum"] = ["observed", "absent", "uncertain"]
            else:
                field["properties"]["state"]["enum"] = ["not_applicable" if status == "absent" else "uncertain"]
                field["properties"]["locations"]["maxItems"] = 0
        branches.append(branch)
    return {"oneOf": branches}


def payload(path, sha256, target, profile, *, explicit_format=False):
    if H["digest"](path) != sha256:
        raise ValueError("Image changed")
    instruction = (
        "Inspect this ONE image independently for target: " + target + ". "
        "First report whether the target is actually present, absent or uncertain, with brief pixel evidence. "
        "Never invent the target or its parts because the prompt names them. Ignore other objects. "
        "For each component definition, list EACH distinct visible location separately, not one entry per pair of connected parts. "
        "No expected number of locations is supplied. Do not combine distinct physical contact sites into one item. "
        "Each location is a short spatial description anchored to visible pixels. Do not list inferred or hidden sites. "
        "A feature whose absence is visible has state absent and no locations; obscured/unclear uses uncertain and no locations. "
        "If target is absent, every component is not_applicable with no locations. "
        "If target identity is uncertain, every component must be uncertain with no locations. "
        "When target is present, components cannot be not_applicable. "
        "Color, lighting, liquid temperature and vapor are not component locations. "
        "Return only target_presence {status,evidence} and components keyed by definition, each {state,locations,evidence}. "
        "No verdict, confidence score, reference role, prior label or desired count. No chain of thought. "
        "Definitions: " + json.dumps(validate_profile(profile)["components"]))
    if explicit_format:
        # The decoder's schema is not automatically visible to the model.
        # Give format rules, without an example that implies a desired count.
        instruction += (
            "\nReturn one syntactically valid JSON object, no Markdown or surrounding prose. "
            "Quote every property name and string value. A visible feature uses state observed, NEVER state present. "
            "locations is an array of short strings, NEVER objects. Evidence is a separate string on each component. "
            "These are format rules only, not evidence that any component exists. "
            "Output JSON Schema: " + json.dumps(schema({**profile, "version": VERSION}), separators=(",", ":")))
    return {"model": "visual-judge", "messages": [{"role": "user", "content": [
        {"type": "text", "text": instruction}, {"type": "image_url", "image_url": {
         "url": "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()}}]}],
        "temperature": 0, "max_tokens": 512, "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {"type": "json_schema", "json_schema": {"name": "target_components", "strict": True,
                             "schema": schema(profile)}}}


def validate(answer, profile):
    validate_profile(profile)
    if not isinstance(answer, dict) or set(answer) != {"target_presence", "components"}:
        raise ValueError("Invalid inventory fields")
    presence = answer["target_presence"]
    if not isinstance(presence, dict) or set(presence) != {"status", "evidence"}:
        raise ValueError("Missing target presence")
    status = presence["status"]
    if status not in {"present", "absent", "uncertain"} or not isinstance(presence["evidence"], str) or not presence["evidence"].strip():
        raise ValueError("Invalid target presence")
    components = answer["components"]
    if not isinstance(components, dict) or set(components) != set(profile["components"]):
        raise ValueError("Missing component coverage")
    for component in components.values():
        if not isinstance(component, dict) or set(component) != {"state", "locations", "evidence"}:
            raise ValueError("Invalid component")
        state, locations = component["state"], component["locations"]
        if state not in {"observed", "absent", "uncertain", "not_applicable"}:
            raise ValueError("Invalid component state")
        if not isinstance(locations, list) or any(not isinstance(s, str) or not s.strip() for s in locations):
            raise ValueError("Invalid locations")
        normalized = [" ".join(s.split()).casefold() for s in locations]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Duplicate locations")
        if bool(locations) != (state == "observed"):
            raise ValueError("State/location contradiction")
        if not isinstance(component["evidence"], str) or not component["evidence"].strip():
            raise ValueError("Missing evidence")
        if status == "absent" and state != "not_applicable" or status == "uncertain" and state != "uncertain":
            raise ValueError("Components inferred without established target")
        if status == "present" and state == "not_applicable":
            raise ValueError("Applicable component omitted")
    return answer


def coverage(answer, profile):
    validate(answer, profile)
    status = answer["target_presence"]["status"]
    counts = {name: len(c["locations"]) if c["state"] == "observed" else 0 if c["state"] == "absent" else None
              for name, c in answer["components"].items()}
    incomplete = [name for name, c in answer["components"].items() if c["state"] in {"uncertain", "not_applicable"}]
    observed = [name for name, c in answer["components"].items() if c["state"] == "observed"]
    return {"target_presence": status, "location_counts": counts, "incomplete_components": incomplete,
            "observed_components": observed, "coverage_policy_version": COVERAGE_VERSION,
            "coverage": "not_applicable" if status == "absent" else "incomplete" if incomplete else
                        "no_observed_component" if not observed else "reported_complete",
            "pixel_truth_verified": False}


def compare(reference, candidate, profile):
    a, b = coverage(reference, profile), coverage(candidate, profile)
    result = {"status": "uncertain", "admission_allowed": False, "automatic_rejection": False,
              "physical_identity_established": False, "hints": [], "priority": "no_detected_signal"}
    if b["target_presence"] != "present" or a["target_presence"] != "present":
        result.update(status="unavailable", priority="target_not_established")
        result["hints"].append({"feature": "target_presence", "kind": "target_not_established",
                                "reference": a["target_presence"], "candidate": b["target_presence"]})
        return result
    for name in profile["components"]:
        x, y = a["location_counts"][name], b["location_counts"][name]
        if x is None or y is None:
            result["hints"].append({"feature": name, "kind": "insufficient_component_coverage"})
        elif x != y:
            result["hints"].append({"feature": name, "kind": "location_count_disagreement"})
    if a["coverage"] == "no_observed_component" or b["coverage"] == "no_observed_component":
        result["hints"].append({"feature": "component_coverage", "kind": "no_positive_component_observation"})
    if result["hints"]:
        result["priority"] = "component_observation_review"
    return result
