"""Pixel locations for review; coordinates and overlaps never certify identity."""
import base64
import copy
import json
import runpy
from pathlib import Path

C = runpy.run_path(str(Path(__file__).with_name("visual_component_observations.py")))
H = C["H"]
VERSION = "target-location-observations-1"


def validate_profile(profile):
    if not isinstance(profile, dict) or profile.get("version") != VERSION:
        raise ValueError("Unknown location protocol")
    C["validate_profile"]({**profile, "version": C["CONDITIONAL_VERSION"]})
    return profile


def schema(profile):
    validate_profile(profile)
    result = C["schema"]({**profile, "version": C["CONDITIONAL_VERSION"]})
    location = {"type": "object", "properties": {
        "box": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 1000},
                "minItems": 4, "maxItems": 4},
        "evidence": {"type": "string"}}, "required": ["box", "evidence"], "additionalProperties": False}
    for branch in result["oneOf"]:
        for field in branch["properties"]["components"]["properties"].values():
            field["properties"]["locations"]["items"] = copy.deepcopy(location)
    return result


def payload(path, sha256, target, profile, *, explicit_format=False):
    validate_profile(profile)
    if H["digest"](path) != sha256:
        raise ValueError("Image changed")
    result = schema(profile)
    prompt_schema = copy.deepcopy(result["oneOf"][0])
    prompt_schema["properties"]["target_presence"]["properties"]["status"]["enum"] = ["present", "absent", "uncertain"]
    for field in prompt_schema["properties"]["components"]["properties"].values():
        field["properties"]["state"]["enum"] = ["observed", "absent", "uncertain", "not_applicable"]
    instruction = (
        "Inspect ONE image independently for target: " + target + ". "
        "Report actual target presence present/absent/uncertain with concise pixel evidence. Never invent a named object. "
        "For each definition, localize EACH distinct directly visible physical site separately. "
        "Each locations item contains box [left,top,right,bottom] and short evidence for that single site. "
        "Coordinates are integers normalized from 0 to 1000 relative to the FULL image: left/top origin, right/bottom maximum. "
        "Use a tight nonempty box for ONE visible site, never a box aggregating distinct bands, holes or attachment sites. "
        "No desired number of sites is supplied. Do not infer hidden sites, conventional anatomy, shadows or reflections. "
        "State observed requires visible sites; absent requires visibly absent feature and empty locations; "
        "obscured/ambiguous uses uncertain with empty locations. If target absent, all states not_applicable with empty locations; "
        "if target uncertain, all states uncertain with empty locations. Present target cannot use not_applicable. "
        "Evidence is not a verdict. No reference role, label, identity comparison, score or desired count. "
        "Return compact valid JSON only, no Markdown or chain of thought; quotes on keys/strings. "
        "Definitions: " + json.dumps(profile["components"], separators=(",", ":")) +
        " Output JSON Schema (format rules only, not evidence): " + json.dumps(prompt_schema, separators=(",", ":")))
    return {"model": "visual-judge", "messages": [{"role": "user", "content": [
        {"type": "text", "text": instruction}, {"type": "image_url", "image_url": {
            "url": "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()}}]}],
        "temperature": 0, "max_tokens": 512, "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "target_locations", "strict": True, "schema": result}}}


def validate(answer, profile):
    validate_profile(profile)
    if not isinstance(answer, dict) or set(answer) != {"target_presence", "components"}:
        raise ValueError("Invalid location inventory")
    converted = copy.deepcopy(answer)
    if not isinstance(answer["components"], dict):
        raise ValueError("Invalid components")
    for name, component in answer["components"].items():
        if not isinstance(component, dict) or not isinstance(component.get("locations"), list):
            raise ValueError("Invalid locations")
        boxes = []
        for location in component["locations"]:
            if not isinstance(location, dict) or set(location) != {"box", "evidence"}:
                raise ValueError("Invalid location")
            box = location["box"]
            if (not isinstance(box, list) or len(box) != 4 or any(type(x) is not int or not 0 <= x <= 1000 for x in box)
                    or box[0] >= box[2] or box[1] >= box[3]):
                raise ValueError("Invalid normalized box")
            if not isinstance(location["evidence"], str) or not location["evidence"].strip():
                raise ValueError("Missing site evidence")
            boxes.append(tuple(box))
        if len(boxes) != len(set(boxes)):
            raise ValueError("Duplicate site boxes")
        converted["components"][name]["locations"] = [json.dumps(box) for box in boxes]
    C["validate"](converted, {**profile, "version": C["CONDITIONAL_VERSION"]})
    return answer


def intersection_over_union(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union


def coverage(answer, profile):
    validate(answer, profile)
    converted = copy.deepcopy(answer)
    overlaps = []
    for name, component in answer["components"].items():
        locations = component["locations"]
        converted["components"][name]["locations"] = [json.dumps(x["box"]) for x in locations]
        for i, a in enumerate(locations):
            for j, b in enumerate(locations[:i]):
                iou = intersection_over_union(a["box"], b["box"])
                if iou > 0:
                    overlaps.append({"component": name, "site_indices": [j, i], "intersection_over_union": iou})
    return {**C["coverage"](converted, {**profile, "version": C["CONDITIONAL_VERSION"]}),
            "coordinate_system": "full-image-normalized-0-1000", "location_protocol": VERSION,
            "overlapping_regions": overlaps, "pixel_truth_verified": False}


def compare(reference, candidate, profile):
    a, b = coverage(reference, profile), coverage(candidate, profile)
    result = {"status": "uncertain", "admission_allowed": False, "automatic_rejection": False,
              "physical_identity_established": False, "hints": [], "priority": "no_detected_signal"}
    if a["target_presence"] != "present" or b["target_presence"] != "present":
        result.update(status="unavailable", priority="target_not_established")
        return result
    for name in profile["components"]:
        x, y = a["location_counts"][name], b["location_counts"][name]
        if x is None or y is None:
            result["hints"].append({"feature": name, "kind": "insufficient_component_coverage"})
        elif x != y:
            result["hints"].append({"feature": name, "kind": "region_entry_count_disagreement"})
    if a["overlapping_regions"] or b["overlapping_regions"]:
        result["hints"].append({"feature": "region_overlap", "kind": "overlapping_regions_need_review"})
    if "no_observed_component" in {a["coverage"], b["coverage"]}:
        result["hints"].append({"feature": "component_coverage", "kind": "no_positive_component_observation"})
    if result["hints"]:
        result["priority"] = "location_observation_review"
    return result
