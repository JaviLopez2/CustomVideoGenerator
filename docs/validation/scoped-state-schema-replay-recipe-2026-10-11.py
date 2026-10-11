"""CPU matrix and archived-reply audit; never repairs or requests observations."""
from datetime import datetime, timezone
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import scoped_structure_observations as published
from scripts import scoped_state_schema as adapter

OUTPUT = ROOT / "docs/validation/scoped-state-schema-replay-2026-10-11.json"


def bind(path):
    path = Path(path)
    return {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def fp(value):
    return hashlib.sha256(published.canonical(value).encode()).hexdigest()


def accepted_json(value, schema):
    try:
        jsonschema.validate(value, schema)
        return True
    except jsonschema.ValidationError:
        return False


def accepted_runtime(value, scope):
    try:
        published.validate(value, scope)
        return True
    except ValueError:
        return False


def main():
    if OUTPUT.exists():
        raise ValueError("Preserve previous replay and audit")
    execution, source, assets = runpy.run_path(str(ROOT / "docs/validation/procedural-mug-connections-execution-recipe-v2-2026-10-11.py"))["verify"]()
    bindings = {name: bind(ROOT / name) for name in ["scripts/scoped_structure_observations.py",
                "scripts/scoped_state_schema.py", "docs/validation/scoped-state-schema-replay-recipe-2026-10-11.py",
                "docs/validation/procedural-mug-connections-execution-plan-v2-2026-10-11.json",
                "docs/validation/procedural-mug-connections-plan-v2-2026-10-11.json"]}
    matrix = []
    for states in [[], ["vapor"], ["vapor", "output"], ["a", "b", "c", "d"]]:
        scope = {"subject": "device", "protected_structure": "Permanent parts and their connections.", "allowed_state_changes": states}
        for state in ["observed", "not_observed", "uncertain", "not_applicable", None, 1, False, "", "NOT_APPLICABLE", "unknown"]:
            value = {"reference_subject_presence": "present", "candidate_subject_presence": "present",
                     "protected_structure_change": "not_observed", "structural_connections_change": "not_observed",
                     "allowed_state_change": state, "structure_evidence": "Same visible construction.",
                     "state_evidence": "State compared separately."}
            emitted = accepted_json(value, adapter.schema(scope))
            runtime = accepted_runtime(value, scope)
            assert emitted == runtime
            matrix.append({"declared_states": len(states), "state_value": state, "schema_accepts": emitted,
                           "runtime_accepts": runtime, "both_subjects_present_other_fields_consistent": True})
    replay = []
    for key in ["qwen35", "qwen3vl"]:
        p = ROOT / f"docs/validation/procedural-mug-connections-{key}-2026-10-11.json"
        original = p.read_bytes()
        report = json.loads(original)
        value = json.loads(report["rows"][0]["final_content"])
        scope = source["cases"][0]["scope"]
        before = copy.deepcopy(value)
        old, new, runtime = accepted_json(value, published.schema()), accepted_json(value, adapter.schema(scope)), accepted_runtime(value, scope)
        assert old and not new and not runtime and value == before and p.read_bytes() == original
        replay.append({"model": key, "report": bind(p), "allowed_state_change": value["allowed_state_change"],
                       "generic_schema_accepts": old, "new_schema_accepts": new, "published_runtime_accepts": runtime,
                       "raw_bytes_and_semantic_value_preserved": True, "old_status": report["rows"][0]["transport_status"],
                       "new_observation_or_relabel_created": False})
    payloads = []
    for case, old_binding in zip(source["cases"], source["request_bindings"], strict=True):
        old = published.payload(case["reference"], case["candidate"], case["scope"])
        new = adapter.payload(case["reference"], case["candidate"], case["scope"])
        expected = copy.deepcopy(old)
        expected["response_format"]["json_schema"]["schema"]["properties"]["allowed_state_change"]["enum"] = ["observed", "not_observed", "uncertain"]
        assert new == expected and fp(old) == old_binding["request_sha256"] and fp(new) != fp(old)
        assert case["case_id"] not in published.canonical(new)
        payloads.append({"case_id": case["case_id"], "old_request_sha256": fp(old), "new_request_sha256": fp(new),
                         "only_state_enum_changed": True, "request_executed": False})
    record = {"protocol": "scope-compatible-state-schema-cpu-replay-1", "checked_utc": datetime.now(timezone.utc).isoformat(),
              "schema_builder_version": adapter.VERSION, "bindings": bindings, "state_applicability_matrix": matrix,
              "archived_reply_replay": replay, "future_payload_comparison": payloads,
              "existing_execution_and_preparation_pins_still_verify": True,
              "relational_constraints_still_require_published_runtime_validation": True,
              "legacy_collector_or_app_automatically_uses_adapter": False,
              "new_model_requests": 0, "generations": 0, "admission_allowed": False,
              "physical_identity_established": False, "natural_image_accuracy_measured": False}
    with OUTPUT.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"matrix": len(matrix), "archived_replies": len(replay), "payloads_compared": len(payloads), "model_requests": 0}))


if __name__ == "__main__":
    main()
