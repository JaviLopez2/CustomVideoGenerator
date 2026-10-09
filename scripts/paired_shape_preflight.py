"""Offline v2 evidence/region checks; never confers perceptual admission."""
import hashlib
import json
from pathlib import Path
import re

from scripts import prepare_visual_regions as regions


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def binding_path(binding, root):
    if (not isinstance(binding, dict) or not isinstance(binding.get("path"), str) or not binding["path"]
            or not isinstance(binding.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", binding["sha256"])):
        raise ValueError("Invalid evidence binding")
    return (Path(root) / binding["path"]).resolve()


def checked_bytes(binding, root):
    raw = binding_path(binding, root).read_bytes()
    if hashlib.sha256(raw).hexdigest() != binding["sha256"]:
        raise ValueError("Evidence bytes changed")
    return raw


def checked_json(binding, root):
    def unique(pairs):
        if len(dict(pairs)) != len(pairs):
            raise ValueError("Duplicate evidence field")
        return dict(pairs)
    return json.loads(checked_bytes(binding, root), object_pairs_hook=unique)


def same_binding(left, right, root):
    return binding_path(left, root) == binding_path(right, root) and left["sha256"] == right["sha256"]


def validate_evidence(plan):
    if "human_review" in plan:
        raise ValueError("Neutral protocol cannot claim a human review")
    for field in ("evidence_provenance", "region_preparation", "region_manifest"):
        binding_path(plan.get(field), Path.cwd())
    controls = plan.get("excluded_region_controls")
    if not isinstance(controls, list) or not 1 <= len(controls) <= 16:
        raise ValueError("Missing exclusion controls")
    for case in plan["cases"]:
        if {"offline_human_review_verbatim", "offline_expected_major_shape_change", "human_review"} & case.keys():
            raise ValueError("Ambiguous legacy gold in neutral case")
        value = case.get("offline_expectation")
        if not isinstance(value, dict) or set(value) != {"origin", "expected_major_shape_change", "human_gold"} or value["human_gold"] is not False:
            raise ValueError("Invalid neutral expectation")
        if value["origin"] == "byte_identity_control":
            if value["expected_major_shape_change"] != "not_observed":
                raise ValueError("Invalid byte-control expectation")
        elif value["origin"] == "unlabelled_pair":
            if value["expected_major_shape_change"] is not None:
                raise ValueError("Unlabelled pair cannot have gold")
        else:
            raise ValueError("Unknown evidence origin")
        if any(not isinstance(case.get(role + "_region_id"), str) or not case[role + "_region_id"] for role in ("reference", "candidate")):
            raise ValueError("Missing region references")


def verify_regions(plan, root):
    preparation = checked_json(plan["region_preparation"], root)
    helper = preparation["helper"]
    checked_bytes(helper, root)
    if hashlib.sha256(Path(regions.__file__).read_bytes()).hexdigest() != helper["sha256"]:
        raise ValueError("Different preparation implementation")
    prep = preparation["preparation"]
    margin, items = prep.get("margin_pixels"), prep.get("regions")
    if (set(prep) != {"protocol", "margin_pixels", "regions"} or prep["protocol"] != "visual-region-preparation-plan-1"
            or type(margin) is not int or not 0 <= margin <= 4096 or not isinstance(items, list) or not 1 <= len(items) <= 16):
        raise ValueError("Invalid bound preparation contract")
    manifest = checked_json(plan["region_manifest"], root)
    if (manifest.get("protocol") != "visual-region-artifacts-1" or manifest.get("admission_allowed") is not False
            or manifest.get("physical_identity_established") is not False or type(manifest.get("generation_or_model_requests")) is not int
            or manifest["generation_or_model_requests"] != 0 or manifest.get("pillow_version") != regions.pillow_version
            or manifest.get("plan_canonical_sha256") != hashlib.sha256(canonical(prep).encode()).hexdigest()):
        raise ValueError("Invalid bound region manifest")
    records = manifest.get("regions")
    if not isinstance(records, list) or len(records) != len(items):
        raise ValueError("Missing or extra region artifacts")
    verified = {}
    for item, record in zip(items, records):
        expected, encoded = regions.render(item, margin)
        actual = {**record, "crop": {key: value for key, value in record["crop"].items() if key != "path"}}
        if canonical(actual) != canonical(expected) or record["id"] in verified:
            raise ValueError("Region claims differ from source reconstruction")
        if checked_bytes(record["crop"], root) != encoded:
            raise ValueError("Stored crop differs from native source subset")
        verified[record["id"]] = record
    return verified


def preflight(plan, root):
    validate_evidence(plan)
    design = checked_json(plan["evidence_provenance"], root)
    if design.get("protocol") != "cross-family-paired-shape-design-1":
        raise ValueError("Unknown evidence design")
    source_result = checked_json(design.get("source_preparation"), root)
    if (not same_binding(design.get("artifact_manifest"), plan["region_manifest"], root)
            or not same_binding(source_result.get("manifest"), plan["region_manifest"], root)
            or not same_binding(source_result.get("plan"), plan["region_preparation"], root)):
        raise ValueError("Region bindings differ from frozen design/preparation result")
    verified = verify_regions(plan, root)
    declarations = design.get("planned_cases")
    if not isinstance(declarations, list) or len(declarations) != len(plan["cases"]):
        raise ValueError("Missing case declarations")
    expectations = []
    for case, declared in zip(plan["cases"], declarations):
        for role in ("reference", "candidate"):
            row = verified.get(case[role + "_region_id"])
            if row is None or row["coverage_relation"] != "contained" or row["whole_declared_region_eligible"] is not True:
                raise ValueError("Requested region is not wholly covered")
            image = case[role]
            if (binding_path(image, root) != binding_path(row["crop"], root) or image["sha256"] != row["crop"]["sha256"]
                    or canonical(image["size"]) != canonical(row["crop"]["size"])):
                raise ValueError("Case input differs from bound region")
        expectation = case["offline_expectation"]
        if (case["case_id"] != declared["id"] or case["reference_region_id"] != declared["reference_region"]
                or case["candidate_region_id"] != declared["candidate_region"]
                or expectation["expected_major_shape_change"] != declared["expected_major_shape_change"]):
            raise ValueError("Case differs from declared evidence")
        if expectation["origin"] == "byte_identity_control" and case["reference"]["sha256"] != case["candidate"]["sha256"]:
            raise ValueError("Byte-control inputs differ")
        expectations.append({"case_id": case["case_id"], **expectation})
    declarations = design.get("pre_request_exclusion_controls")
    controls = plan["excluded_region_controls"]
    if not isinstance(declarations, list) or len(declarations) != len(controls):
        raise ValueError("Changed exclusion controls")
    excluded = []
    for control, declared in zip(controls, declarations):
        if (set(control) != {"region_id", "expected_relation"} or control["region_id"] != declared["region"]
                or control["expected_relation"] != declared["expected_relation"]
                or control["expected_relation"] not in {"partial", "disjoint"}
                or type(declared["model_requests"]) is not int or declared["model_requests"] != 0):
            raise ValueError("Invalid exclusion-control declaration")
        row = verified.get(control["region_id"])
        if row is None or row["coverage_relation"] != control["expected_relation"] or row["whole_declared_region_eligible"] is not False:
            raise ValueError("Exclusion relation changed")
        excluded.append({"region_id": row["id"], "coverage_relation": row["coverage_relation"]})
    return {"protocol": "paired-shape-neutral-preflight-1", "human_gold": False,
            "case_expectations": expectations, "regions_verified": len(verified),
            "excluded_regions": excluded, "excluded_model_requests": 0,
            "semantic_human_coverage": "pending", "admission_allowed": False,
            "physical_identity_established": False, "pixel_subset_and_provenance_verified": True}
