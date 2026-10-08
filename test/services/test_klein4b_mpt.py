"""Experimental caller contracts; no network or model loading."""

import io
import json
from unittest.mock import Mock

import pytest
from PIL import Image

from app.config import config
from app.services import klein4b_experimental as klein
from app.services import material
from local_image_stack.experiments import klein4b_graph
from test.services.test_corrective_continuity import pipeline, item  # noqa: F401


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(config, "app", {
        "openai_image_klein4b_experimental_enabled": True,
        "openai_image_klein4b_seed": 123,
        "openai_image_size": "512x512",
        "openai_image_model": "z-image-turbo",
        "openai_image_base_url": "http://127.0.0.1:8090/v1",
        "openai_image_precision_fallback_model": "flux-klein-4b-edit-exp",
    })
    monkeypatch.setattr(klein, "validate_local_assets", lambda manifest: None)
    buffer = io.BytesIO()
    Image.new("RGB", (512, 512)).save(buffer, format="PNG")
    request = Mock(return_value=(buffer.getvalue(), ""))
    monkeypatch.setattr(material, "_request_openai_image", request)
    return request, buffer.getvalue()


def generate(tmp_path, count=0, route="precision", info=None, **kwargs):
    roles = ["identity", "style", "detail"][:count]
    refs = [f"reference-{i}.png" for i in range(count)]
    return material.generate_images_openai(
        "An unbranded object in daylight", 3, material.VideoAspect.square,
        save_dir=str(tmp_path), route=route,
        model_override="flux-klein-4b-edit-exp" if count else "flux-klein-4b-t2i-exp",
        reference_images=refs,
        reference_info=info if info is not None else {"reference_pack": [{"role": r} for r in roles]},
        **kwargs,
    )


@pytest.mark.parametrize("count", [0, 1, 2, 3])
@pytest.mark.parametrize("route", ["standard", "precision"])
def test_tier_independent_of_conditioning(configured, tmp_path, count, route):
    request, _ = configured
    item = generate(tmp_path, count, route)[0]
    endpoint, payload = request.call_args.args
    assert endpoint == "http://127.0.0.1:8091/v1/images/generations"
    assert request.call_args.kwargs == {"max_attempts": 1}
    assert payload["model"] == ("flux-klein-4b-edit-exp" if count else "flux-klein-4b-t2i-exp")
    assert payload["seed"] == 123 and payload["steps"] == 4 and payload["guidance"] == 1
    assert payload["size"] == "512x512"
    assert payload["reference_roles"] == ["identity_reference", "style_reference", "factual_reference"][:count]
    for i in range(count):
        assert payload["reference_image" if i == 0 else f"reference_image_{i+1}"] == f"reference-{i}.png"
    assert item.source_info["quality_tier"] == route
    assert item.source_info["conditioning_mode"] == ("manual_reference" if count else "none")
    assert item.source_info["qa_status"] == "pending"
    assert "flux-klein-precision" not in json.dumps(payload)
    assert request.call_count == 1


def test_root_can_occupy_second_slot(configured, tmp_path):
    info = {"reference_pack": [{"role": "style"}, {"role": "continuity"}],
            "temporal_progression": True, "temporal_state": "steam rises from hot tea"}
    item = generate(tmp_path, 2, info=info)[0]
    payload = configured[0].call_args.args[1]
    assert payload["reference_roles"] == ["style_reference", "continuity_anchor"]
    assert "Use image 2 as the stable root" in payload["prompt"]
    assert "MUST advance" in payload["prompt"]
    assert item.source_info["conditioning_mode"] == "continuity_reference"


@pytest.mark.parametrize("info", [
    {}, {"reference_pack": [{"role": "unknown"}]},
    {"reference_pack": [{"role": "identity", "comfyui_input": "wrong.png"}]},
    {"reference_pack": [{"role": "identity"}], "temporal_progression": True, "temporal_state": "changed"},
])
def test_invalid_role_pack_fails_before_dispatch(configured, tmp_path, info):
    with pytest.raises(ValueError):
        generate(tmp_path, 1, info=info)
    configured[0].assert_not_called()


def test_disabled_is_not_silent_alias_replacement(configured, tmp_path):
    config.app["openai_image_klein4b_experimental_enabled"] = False
    with pytest.raises(ValueError, match="not enabled"):
        generate(tmp_path)
    configured[0].assert_not_called()


def test_primary_order_mismatch_rejected(configured, tmp_path):
    with pytest.raises(ValueError, match="first ordered"):
        generate(tmp_path, 2, reference_image="other.png")
    configured[0].assert_not_called()


def test_scene_evidence_and_exclusions_reach_positive_prompt(configured, tmp_path):
    generate(tmp_path, 1, info={"reference_pack": [{"role": "identity", "description": "a red ceramic mug"}]},
             forbidden_features=["lettering", "extra handles"])
    prompt = configured[0].call_args.args[1]["prompt"]
    assert "Image 1 evidence: a red ceramic mug" in prompt
    assert "Exclude these scene-specific features: lettering; extra handles" in prompt


def test_explicit_t2i_never_becomes_edit(configured, tmp_path):
    with pytest.raises(ValueError, match="T2I requires"):
        material.generate_images_openai("A mug", 3, save_dir=str(tmp_path),
            model_override="flux-klein-4b-t2i-exp", reference_images=["mug.png"],
            reference_info={"reference_pack": [{"role": "identity"}]})
    configured[0].assert_not_called()


def test_temporal_contradiction_rejected_by_real_caller(configured, tmp_path):
    with pytest.raises(ValueError, match="contradicts"):
        material.generate_images_openai("preserve the previous visual state", 3, save_dir=str(tmp_path),
            model_override="flux-klein-4b-edit-exp", reference_images=["root.png"],
            reference_info={"reference_pack": [{"role": "continuity"}],
                            "temporal_progression": True, "temporal_state": "now hot"})
    configured[0].assert_not_called()


def test_missing_workflow(configured, tmp_path, monkeypatch):
    monkeypatch.setattr(klein4b_graph, "WORKFLOWS", tmp_path)
    with pytest.raises(ValueError, match="Missing asset"):
        generate(tmp_path)
    configured[0].assert_not_called()


def test_missing_asset(tmp_path):
    manifest = {"components": {"vae": {"filename": "absent.safetensors",
        "local_path": str(tmp_path / "absent.safetensors"), "expected_size_bytes": 10,
        "verification_status": "verified_local_bytes"}}}
    with pytest.raises(ValueError, match="Missing or changed"):
        klein.validate_local_assets(manifest)


def test_bridge_error_never_enters_9b_fallback(configured, tmp_path):
    configured[0].return_value = None, "HTTP 500: execution failed"
    config.app["openai_image_precision_fallback_model"] = "flux-klein-precision"
    with pytest.raises(RuntimeError, match="no automatic retry"):
        generate(tmp_path, 1)
    assert configured[0].call_count == 1


def test_wrong_output_resolution_is_explicit(configured, tmp_path):
    config.app["openai_image_size"] = "768x1376"
    with pytest.raises(ValueError, match="dimensions"):
        generate(tmp_path)


@pytest.mark.parametrize("detail,allowed", [
    ("HTTP 404: workflow not found", True),
    ("HTTP 404: unknown model", True),
    ("HTTP 500: timeout", False),
    ("unconfirmed request error", False),
    ("gross semantic QA rejected", False),
    ("temporal QA rejected", False),
    ("factual QA incoherent", False),
    ("HTTP 404: resource not found", False),
])
def test_conservative_failure_classification(detail, allowed):
    assert klein.confirmed_technical_failure(detail) is allowed


def test_actual_material_fallback_preserves_pack(configured, tmp_path):
    request, png = configured
    request.side_effect = [(None, "HTTP 404: workflow not found"), (png, "")]
    items = material.generate_images_openai(
        "A mug and a key", 3, material.VideoAspect.square, str(tmp_path),
        route="precision", model_override="qwen-image-2.1-precision",
        reference_images=["root.png", "detail.png"], reference_info={
            "reference_pack": [{"role": "continuity"}, {"role": "detail"}],
            "temporal_progression": True, "temporal_state": "hot tea with steam"},
    )
    assert len(items) == 1
    assert request.call_count == 2
    payload = request.call_args.args[1]
    assert payload["reference_image_2"] == "detail.png"
    assert payload["reference_roles"] == ["continuity_anchor", "factual_reference"]
    assert items[0].source_info["fallback_from_model"] == "qwen-image-2.1-precision"
    assert items[0].source_info["model"] == "flux-klein-4b-edit-exp"
    assert items[0].source_info["qa_status"] == "pending"


@pytest.mark.parametrize("failure", ["gross semantic QA rejected", "temporal QA rejected",
                                      "factual QA rejected", "unconfirmed request error"])
def test_actual_material_does_not_fallback_on_qa_or_unknown(configured, tmp_path, failure):
    request, _ = configured
    request.return_value = None, failure
    items = material.generate_images_openai(
        "An object", 3, save_dir=str(tmp_path), route="precision",
        model_override="qwen-image-2.1-precision", reference_images=["a.png"],
        reference_info={"reference_pack": [{"role": "identity"}]},
    )
    assert items == [] and request.call_count == 1


@pytest.mark.parametrize("status,verdict,expected", [
    ("pass", "pass", True), ("pass", "uncertain", False),
    ("uncertain", "uncertain", False), ("unavailable", "", False),
    ("gross_failure", "reject", False),
])
def test_pipeline_experimental_qa_requires_verified_pass(pipeline, monkeypatch, status, verdict, expected):
    run, diagnostics = pipeline
    generated = item("klein")
    generated.source_info["model"] = "flux-klein-4b-t2i-exp"
    request = Mock(return_value=[generated])
    monkeypatch.setattr(material, "generate_images_openai", request)
    monkeypatch.setattr(material, "_gross_scene_semantic_qa_enabled", lambda: True)
    monkeypatch.setattr(material, "_scene_gross_semantic_assessment", lambda *a, **kw: {
        "available": status != "unavailable", "status": status, "verdict": verdict,
        "gross_failure": status == "gross_failure"})
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": False})
    result = run(search_terms=["A mug"], scene_durations=[1], scene_routes=["standard"], scene_subjects=["mug"])
    assert bool(result) is expected
    assert request.call_count == 1


def test_pipeline_uncertain_temporal_is_rejected_without_retry(pipeline, monkeypatch):
    run, diagnostics = pipeline
    generated = item("klein")
    generated.source_info["model"] = "flux-klein-4b-edit-exp"
    request = Mock(return_value=[generated])
    monkeypatch.setattr(material, "generate_images_openai", request)
    monkeypatch.setattr(material, "_gross_scene_semantic_qa_enabled", lambda: True)
    monkeypatch.setattr(material, "_scene_gross_semantic_assessment", lambda *a, **kw: {
        "available": True, "status": "pass", "verdict": "pass", "gross_failure": False})
    monkeypatch.setattr(material, "_temporal_semantic_qa_enabled", lambda: True)
    monkeypatch.setattr(material, "_scene_temporal_semantic_assessment", lambda *a, **kw: {
        "available": True, "status": "uncertain", "verdict": "uncertain", "temporal_failure": False})
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": False})
    result = run(search_terms=["same mug now cooled"], scene_durations=[1], scene_routes=["standard"],
        scene_subjects=["mug"], scene_reference_targets=["output"], scene_includes_primary_subject=[False],
        scene_continuity_keys=["mug_chain"], scene_continuity_descriptions=["single red mug"],
        scene_temporal_progressions=[True], scene_temporal_states=["no steam"])
    assert result == [] and request.call_count == 1
    assert diagnostics[-1]["plan_scenes"][0]["experimental_qa_status"] == "unverified_rejected"


def test_experimental_transport_does_not_retry_503(monkeypatch):
    monkeypatch.setattr(config, "app", {})
    monkeypatch.setattr(config, "proxy", {})
    response = Mock(status_code=503)
    response.json.return_value = {"error": "backend unavailable"}
    post = Mock(return_value=response)
    monkeypatch.setattr(material.requests, "post", post)
    result, reason = material._request_openai_image("http://127.0.0.1:8091/v1/images/generations", {}, max_attempts=1)
    assert result is None and reason.startswith("HTTP 503:")
    assert post.call_count == 1
