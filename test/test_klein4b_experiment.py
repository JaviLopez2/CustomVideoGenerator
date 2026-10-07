"""Offline contracts only: synthetic fixtures, no torch, downloads or services."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from local_image_stack.experiments.klein4b import (
    ALIASES, FILENAMES, Reference, build_request, fallback_alias, require_ready, resolve_alias,
)


@pytest.fixture
def manifest():
    return json.loads((Path(__file__).parents[1] / "docs/validation/flux-klein-4b-assets.json").read_text())


@pytest.mark.parametrize("alias", ALIASES)
def test_aliases_only_resolve_distilled_4b(manifest, alias):
    binding = resolve_alias(alias, manifest)
    assert binding["checkpoint"] == "flux-2-klein-4b-fp8.safetensors"
    assert "9b" not in json.dumps(binding).lower()
    with pytest.raises(ValueError, match="Unknown experimental alias"):
        resolve_alias("flux-klein-precision", manifest)
    manifest["workflows"][ALIASES[alias]]["checkpoint"] = "flux-2-klein-9b-kv-fp8.safetensors"
    with pytest.raises(ValueError, match="4B alias"):
        resolve_alias(alias, manifest)


def test_t2i_payload_has_no_references(manifest):
    request = build_request(manifest, "single subject", 42, "768x1376")
    assert request["payload"] == {"model": "flux-klein-4b-t2i-exp", "prompt": "single subject",
                                  "seed": 42, "size": "768x1376", "steps": 4, "guidance": 1.0, "n": 1}
    assert request["reference_roles"] == []
    assert request["dispatch_allowed"] is False


@pytest.mark.parametrize("count", [1, 2, 3])
def test_edit_reference_order_and_roles(manifest, count):
    refs = tuple(Reference(f"input-{n}.png", role) for n, role in enumerate(
        ["identity_reference", "factual_reference", "style_reference"][:count]))
    request = build_request(manifest, "requested scene", 9, "1024x1024", refs)
    p = request["payload"]
    assert p["model"] == "flux-klein-4b-edit-exp"
    assert [p["reference_image" if n == 1 else f"reference_image_{n}"] for n in range(1, count + 1)] == [r.image for r in refs]
    assert request["reference_roles"] == [r.role for r in refs]
    assert len([key for key in p if key.startswith("reference_image")]) == count


def test_temporal_edit_changes_state_without_changing_identity(manifest):
    request = build_request(manifest, "single physical sheet", 0, "768x1376",
                            (Reference("root.png", "continuity_anchor"),),
                            temporal_progression=True, temporal_state="visible colors become stronger")
    prompt = request["payload"]["prompt"]
    assert "stable root of the same physical subject" in prompt
    assert "MUST advance" in prompt and "visible colors become stronger" in prompt
    assert "underlying depicted content unchanged" not in prompt
    assert "keep all visible content unchanged" not in prompt


@pytest.mark.parametrize("contradiction", ["keep all visible content unchanged", "underlying depicted content unchanged", "preserve the previous visual state"])
def test_temporal_contradictions_are_rejected(manifest, contradiction):
    with pytest.raises(ValueError, match="contradicts"):
        build_request(manifest, contradiction, 1, "512x512", (Reference("root.png", "continuity_anchor"),),
                      temporal_progression=True, temporal_state="new visible state")


def test_invalid_reference_contracts(manifest):
    with pytest.raises(ValueError, match="unique"):
        build_request(manifest, "scene", 1, "512x512", (Reference("a.png", "identity_reference"),) * 2)
    with pytest.raises(ValueError, match="three"):
        build_request(manifest, "scene", 1, "512x512", tuple(Reference(str(n), "identity_reference") for n in range(4)))
    with pytest.raises(ValueError, match="T2I requires"):
        build_request(manifest, "scene", 1, "512x512", alias="flux-klein-4b-edit-exp")
    with pytest.raises(ValueError, match="continuity root"):
        build_request(manifest, "scene", 1, "512x512", temporal_progression=True, temporal_state="new state")


@pytest.mark.parametrize("failure", ["semantic_failure", "temporal_failure", "factual_failure", "unconfirmed_request_error", "timeout", "unknown"])
def test_qa_and_uncertain_errors_never_enable_fallback(failure):
    assert fallback_alias(failure, has_references=True, enabled=True) is None


def test_fallback_remains_disabled_and_requires_confirmed_technical_failure():
    assert fallback_alias("confirmed_generation_error", has_references=True) is None
    assert fallback_alias("confirmed_generation_error", has_references=True, enabled=True) == "flux-klein-4b-edit-exp"
    assert fallback_alias("confirmed_generation_error", has_references=False, enabled=True) is None
    assert fallback_alias("invalid_output", has_references=True, image_generated=True, enabled=True) is None


@pytest.mark.parametrize("scope", ["research_only", "non_commercial", None])
def test_commercial_admission_rejects_restricted_component(manifest, scope):
    manifest["components"]["text_encoder"]["license_scope"] = scope
    with pytest.raises(ValueError, match="commercial"):
        build_request(manifest, "scene", 1, "512x512", commercial=True)


@pytest.fixture
def verified_fixtures(manifest, tmp_path):
    # Bytes below are synthetic test material, never actual model weights or runtime graphs.
    manifest = copy.deepcopy(manifest)
    paths = {}
    for key, filename in FILENAMES.items():
        path = tmp_path / filename
        path.write_bytes(b"synthetic-fixture")
        manifest["components"][key]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        paths[key] = path
    workflows = {}
    graph = {str(index): {"class_type": loader, "inputs": {field: FILENAMES[component]}}
             for index, (loader, field, component) in enumerate([
                 ("UNETLoader", "unet_name", "diffusion_model"),
                 ("CLIPLoader", "clip_name", "text_encoder"),
                 ("VAELoader", "vae_name", "vae"),
             ])}
    for mode in ("t2i", "edit"):
        path = tmp_path / (mode + ".json")
        path.write_text(json.dumps(graph))
        manifest["workflows"][mode].update(format="comfyui_api", sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        workflows[mode] = path
    manifest.update(status="ready", comfyui_commit="fixture-comfy", bridge_commit="fixture-bridge")
    return manifest, paths, workflows


def test_missing_asset_reports_exact_filename(manifest, tmp_path):
    with pytest.raises(ValueError, match="flux-2-klein-4b-fp8.safetensors"):
        require_ready(manifest, {key: tmp_path / name for key, name in FILENAMES.items()}, {})


def test_ready_requires_hashes_provenance_and_api_exports(verified_fixtures):
    manifest, paths, workflows = verified_fixtures
    require_ready(manifest, paths, workflows, commercial=True)
    for section, key, field in [("components", "vae", "sha256"), ("components", "text_encoder", "source"),
                                ("components", "diffusion_model", "license_source"), ("workflows", "edit", "sha256")]:
        bad = copy.deepcopy(manifest)
        bad[section][key][field] = None
        with pytest.raises(ValueError):
            require_ready(bad, paths, workflows)
    bad = copy.deepcopy(manifest)
    bad["workflows"]["edit"]["format"] = "comfyui_ui_template"
    with pytest.raises(ValueError, match="export"):
        require_ready(bad, paths, workflows)
    paths["vae"].write_bytes(b"corrupt fixture")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        require_ready(manifest, paths, workflows)


def test_workflow_cannot_hide_9b_behind_4b_manifest(verified_fixtures):
    manifest, paths, workflows = verified_fixtures
    graph = json.loads(workflows["edit"].read_text())
    graph["0"]["inputs"]["unet_name"] = "flux-2-klein-9b-kv-fp8.safetensors"
    workflows["edit"].write_text(json.dumps(graph))
    manifest["workflows"]["edit"]["sha256"] = hashlib.sha256(workflows["edit"].read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="undeclared graph asset"):
        require_ready(manifest, paths, workflows)


def test_planned_candidate_and_runtime_are_isolated(manifest):
    assert manifest["status"] == "planned"
    assert all(c["sha256"] is None for c in manifest["components"].values())
    production = Path(__file__).parents[1] / "app/services/material.py"
    assert not any(alias in production.read_text(encoding="utf-8") for alias in ALIASES)
