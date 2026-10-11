"""CPU scope/schema contract regressions; no inference or historical repair."""
import copy
import hashlib
import importlib
import json
from pathlib import Path

import jsonschema
import pytest
from PIL import Image, PngImagePlugin

from scripts import scoped_structure_observations as published


def adapter():
    return importlib.import_module("scripts.scoped_state_schema")


def scope(states):
    return {"subject": "device", "protected_structure": "Permanent parts and their connections.",
            "allowed_state_changes": states}


def answer(state):
    return {"reference_subject_presence": "present", "candidate_subject_presence": "present",
            "protected_structure_change": "not_observed", "structural_connections_change": "not_observed",
            "allowed_state_change": state, "structure_evidence": "Same visible construction.",
            "state_evidence": "Visible state compared separately."}


@pytest.mark.parametrize("states,state,accepted", [
    ([], "not_applicable", True), ([], "observed", False), ([], "not_observed", False), ([], "uncertain", False),
    (["visible vapor"], "not_applicable", False), (["visible vapor"], "observed", True),
    (["visible vapor"], "not_observed", True), (["visible vapor"], "uncertain", True),
    (["visible vapor", "output emerges"], "not_applicable", False),
    (["visible vapor", "output emerges"], "not_observed", True),
])
def test_emitted_schema_matches_state_applicability_contract(states, state, accepted):
    declared, value = scope(states), answer(state)
    emitted = adapter().schema(declared)
    if accepted:
        jsonschema.validate(value, emitted)
        assert published.validate(value, declared) == value
    else:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(value, emitted)
        with pytest.raises(ValueError):
            published.validate(value, declared)


@pytest.fixture
def images(tmp_path):
    records = []
    for index, color in enumerate(["red", "blue"]):
        p = tmp_path / f"image_{index}.png"
        Image.new("RGB", (16, 32), color).save(p)
        records.append({"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "size": [16, 32]})
    return records


@pytest.mark.parametrize("states,allowed", [([], ["not_applicable"]),
    (["visible vapor"], ["observed", "not_observed", "uncertain"])])
def test_payload_changes_only_state_enum_with_same_images_prompt_and_decoding(images, states, allowed):
    declared = scope(states)
    before = copy.deepcopy(declared)
    old = published.payload(*images, declared)
    expected = copy.deepcopy(old)
    expected["response_format"]["json_schema"]["schema"]["properties"]["allowed_state_change"]["enum"] = allowed
    actual = adapter().payload(*images, declared)
    assert actual == expected
    assert declared == before
    assert "verdict" not in actual["response_format"]["json_schema"]["schema"]["properties"]


@pytest.mark.parametrize("bad_states", [None, "vapor", ["vapor", " VAPOR "], [""]])
def test_schema_cannot_silently_accept_invalid_or_duplicate_scopes(bad_states):
    with pytest.raises(ValueError):
        adapter().schema(scope(bad_states))


def test_schema_mutations_cannot_contaminate_later_scope_or_published_schema():
    old = published.schema()
    changed = adapter().schema(scope([]))
    changed["properties"]["allowed_state_change"]["enum"].append("observed")
    changed["properties"]["structure_evidence"]["type"] = "integer"
    value = answer("observed")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(value, adapter().schema(scope([])))
    jsonschema.validate(value, adapter().schema(scope(["visible vapor"])))
    assert published.schema() == old


def test_adapter_inherits_prepared_image_metadata_rejection(images):
    p = Path(images[0]["path"])
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("prompt", "PRIVATE_METADATA_SENTINEL")
    Image.new("RGB", (16, 32), "red").save(p, pnginfo=metadata)
    images[0]["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        adapter().payload(*images, scope(["visible vapor"]))


@pytest.mark.parametrize("model", ["qwen35", "qwen3vl"])
def test_archived_invalid_answers_remain_invalid_and_bytes_unchanged(model):
    root = Path(__file__).resolve().parents[1]
    p = root / f"docs/validation/procedural-mug-connections-{model}-2026-10-11.json"
    original = p.read_bytes()
    value = json.loads(json.loads(original)["rows"][0]["final_content"])
    jsonschema.validate(value, published.schema())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(value, adapter().schema(scope(["visible vapor"])))
    with pytest.raises(ValueError):
        published.validate(value, scope(["visible vapor"]))
    assert value["allowed_state_change"] == "not_applicable" and p.read_bytes() == original


def test_strict_runtime_connections_and_admission_policy_are_not_relaxed():
    declared = scope(["visible vapor"])
    value = answer("observed")
    value["structural_connections_change"] = "observed"
    # Applicability is constrained; relational structure still needs validation.
    jsonschema.validate(value, adapter().schema(declared))
    with pytest.raises(ValueError):
        published.validate(value, declared)
    value["protected_structure_change"] = "observed"
    result = published.diagnostic(value, declared)
    assert result["status"] == "uncertain" and result["admission_allowed"] is False
    assert result["physical_identity_established"] is False and result["automatic_rejection"] is False
