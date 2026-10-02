"""Offline regressions: exercise the generation loop without image services or rendering."""
import copy

import pytest

from app.models.schema import VideoAspect
from app.services import material


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    diagnostics = []
    monkeypatch.setattr(material, "_precision_diagnostics_persist", lambda task, data: diagnostics.append(copy.deepcopy(data)))
    monkeypatch.setattr(material, "_persist_material_sources", lambda *a: None)
    monkeypatch.setattr(material, "_openai_image_model_for_route", lambda route: ("qwen-image-2.1", False))
    monkeypatch.setattr(material, "_qwen_direct_accept_enabled", lambda *a: True)
    monkeypatch.setattr(material, "_precision_retry_on_true_failure_enabled", lambda: True)
    monkeypatch.setattr(material, "_openai_image_color_grading_enabled", lambda: False)
    monkeypatch.setattr(material, "_validate_generated_image_basic", lambda *a: (True, "ok"))
    monkeypatch.setattr(material, "_image_dhash64", lambda *a: 1)
    monkeypatch.setattr(material, "_render_openai_image_video", lambda path, duration: path + ".mp4")
    monkeypatch.setattr(material, "_precision_diagnostics_add_candidate", lambda **kw: None)
    monkeypatch.setattr(material, "_load_manual_precision_reference_manifest", lambda *a: ("user_only", [{}]))
    info = {
        "reference_pack": [{"role": "identity", "anchor": True, "description": "whole primary device", "comfyui_input": "identity.png"}],
    }
    monkeypatch.setattr(material, "_prepare_manual_precision_reference_pack", lambda *a: (["identity.png"], copy.deepcopy(info)))
    # Safety net: an accidental real service call must fail this test.
    def no_network(*a, **kw):
        pytest.fail("unexpected network request")
    monkeypatch.setattr(material.requests, "post", no_network)
    monkeypatch.setattr(material.requests, "get", no_network)

    def run(**kwargs):
        return material._download_videos_openai_image_on_demand(
            task_id="offline-correction", video_aspect=VideoAspect.portrait,
            audio_duration=len(kwargs["search_terms"]), max_clip_duration=1,
            material_directory=str(tmp_path), **kwargs,
        )
    return run, diagnostics


def item(name):
    result = material.MaterialInfo()
    result.url = name + ".png"
    result.provider = "openai_image"
    result.source_info = {"steps": 20}
    return result


def test_balanced_qwen_defaults_remain_lightweight(monkeypatch):
    monkeypatch.setattr(material.config, "app", {})
    assert material._openai_image_generation_steps("precision", "qwen-image-2.1") == 20
    assert material._qwen_direct_accept_enabled("qwen-image-2.1", ["identity.png"])


def test_disabled_retry_budget_accepts_first_duplicate(pipeline, monkeypatch):
    run, diagnostics = pipeline
    monkeypatch.setattr(material, "_precision_retry_on_true_failure_enabled", lambda: False)
    calls = []
    def generate(**kw):
        calls.append(kw)
        return [item("original")]
    monkeypatch.setattr(material, "generate_images_openai", generate)
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": True, "best_similarity": .97})
    assert run(search_terms=["device"], scene_routes=["precision"], scene_subjects=["device"]) == ["original.png.mp4"]
    assert len(calls) == 1
    assert "corrective_retry_selection" not in diagnostics[-1]["scenes"][0]


@pytest.mark.parametrize("retry_metric,selected", [(0.98, "original"), (0.80, "retry"), (0.97, "original"), (None, "original")])
def test_corrective_retry_selects_only_improvement(pipeline, monkeypatch, retry_metric, selected):
    run, diagnostics = pipeline
    generated = [item("original"), item("retry")]
    calls = []
    def generate(**kwargs):
        calls.append(kwargs)
        return [generated[len(calls) - 1]]  # a third attempt would fail
    monkeypatch.setattr(material, "generate_images_openai", generate)
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda path, *a, **kw: {
        "actionable": path == "original.png" or retry_metric is not None and retry_metric >= .96,
        "best_similarity": .97 if path == "original.png" else retry_metric,
    })
    result = run(search_terms=["device close view"], scene_durations=[1], scene_routes=["precision"], scene_subjects=["device"], scene_continuity_keys=["device_instance"])
    assert result == [selected + ".png.mp4"]
    assert len(calls) == 2
    assert "CORRECTION" in calls[1]["search_term"]
    scene = diagnostics[-1]["scenes"][0]
    decision = scene["corrective_retry_selection"]
    assert decision["original_metric"] == .97
    assert decision["retry_metric"] == retry_metric
    assert decision["selected_candidate"] == selected
    assert decision["reason"] == ("similarity_improved" if selected == "retry" else "metric_unavailable" if retry_metric is None else "similarity_not_improved")
    assert scene["near_duplicate_qa"]["best_similarity"] == (.97 if selected == "original" else retry_metric)
    assert scene["continuity_output_file"] == selected + ".png"
    assert len(scene["generation_attempts"]) == 2
    assert diagnostics[-1]["status"] == "completed"


@pytest.mark.parametrize("failure", ["empty", "invalid"])
def test_duplicate_retry_failure_preserves_valid_original(pipeline, monkeypatch, failure):
    run, diagnostics = pipeline
    calls = []
    def generate(**kw):
        calls.append(kw)
        return [item("original")] if len(calls) == 1 else ([] if failure == "empty" else [item("invalid")])
    monkeypatch.setattr(material, "generate_images_openai", generate)
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": True, "best_similarity": .97})
    monkeypatch.setattr(material, "_validate_generated_image_basic", lambda path, *a: (path != "invalid.png", "invalid" if path == "invalid.png" else "ok"))
    assert run(search_terms=["device"], scene_routes=["precision"], scene_subjects=["device"]) == ["original.png.mp4"]
    assert len(calls) == 2
    assert diagnostics[-1]["scenes"][0]["corrective_retry_selection"]["reason"] == "retry_unavailable_or_invalid"


def test_standard_root_continuity_and_identity_anchor_use_qwen_edit_roles(pipeline, monkeypatch):
    run, diagnostics = pipeline
    calls = []

    def generate(**kw):
        calls.append(kw)
        return [item("stage" + str(len(calls)))]

    monkeypatch.setattr(material, "generate_images_openai", generate)
    monkeypatch.setattr(
        material, "_near_duplicate_assessment",
        lambda *a, **kw: {"actionable": False, "best_similarity": .5},
    )
    monkeypatch.setattr(material, "_upload_reference_to_comfyui", lambda path: "stable-anchor.png")
    monkeypatch.setattr(material, "_continuity_edit_chain_enabled", lambda: True)
    result = run(
        search_terms=["output only, early state", "same output, final state beside its source device"],
        scene_durations=[1, 1],
        scene_routes=["standard", "standard"],
        scene_subjects=["output", "output and device"],
        scene_reference_targets=["output", "output"],
        scene_includes_primary_subject=[False, True],
        scene_continuity_keys=["same_output"] * 2,
        scene_continuity_descriptions=["the same printed landscape and border"] * 2,
        scene_edit_operations=[
            "Keep the output at its early visible state",
            "Advance only the output to its final visible state",
        ],
    )
    assert len(result) == len(calls) == 2
    assert calls[0]["route"] == "standard"
    assert "omit incidental background objects" not in calls[0]["search_term"]

    second = calls[1]
    assert second["route"] == "precision"
    assert second["reference_images"] == ["stable-anchor.png", "identity.png"]
    assert second["reference_info"]["primary_identity_only"] is True
    prompt = material._qwen_precision_prompt_with_references(
        second["search_term"],
        second["reference_subject"],
        len(second["reference_images"]),
        reference_info=second["reference_info"],
    )
    assert prompt.startswith("Edit <image1>.")
    assert "Advance only the output to its final visible state" in prompt
    assert "<image1> is the canvas and stable continuity anchor" in prompt
    assert "<image2> is the identity source only for the separate visible primary subject" in prompt
    assert "preserve all untargeted canvas content" in prompt
    assert "Remove incidental background objects" not in prompt
    assert diagnostics[-1]["plan_scenes"][1]["routing_reason"] == "continuity_edit_chain"
    assert diagnostics[-1]["plan_scenes"][1]["continuity_strategy"] == "stable_anchor_delta"


def test_three_stage_continuity_reuses_root_not_previous_generated_stage(pipeline, monkeypatch):
    run, diagnostics = pipeline
    calls = []

    def generate(**kw):
        calls.append(kw)
        return [item("stage" + str(len(calls)))]

    monkeypatch.setattr(material, "generate_images_openai", generate)
    monkeypatch.setattr(
        material, "_near_duplicate_assessment",
        lambda *a, **kw: {"actionable": False, "best_similarity": .5},
    )
    monkeypatch.setattr(
        material,
        "_upload_reference_to_comfyui",
        lambda path: str(path).replace("\\", "/").rsplit("/", 1)[-1],
    )
    monkeypatch.setattr(material, "_continuity_edit_chain_enabled", lambda: True)

    result = run(
        search_terms=["early print", "mid print", "final print"],
        scene_durations=[1, 1, 1],
        scene_routes=["standard"] * 3,
        scene_subjects=["instant print"] * 3,
        scene_reference_targets=["output"] * 3,
        scene_includes_primary_subject=[False] * 3,
        scene_continuity_keys=["print_progress"] * 3,
        scene_continuity_descriptions=["same instant print and depicted landscape"] * 3,
        scene_edit_operations=[
            "Keep the print at its early low-contrast state",
            "Increase only visible contrast and color to a middle stage",
            "Increase only visible contrast and color to the final stage",
        ],
    )

    assert len(result) == len(calls) == 3
    assert calls[0]["route"] == "standard"
    assert calls[1]["reference_images"] == ["stage1.png"]
    assert calls[2]["reference_images"] == ["stage1.png"]
    assert "stage2.png" not in calls[2]["reference_images"]

    final_plan = diagnostics[-1]["plan_scenes"]
    assert final_plan[0]["continuity_strategy"] == "anchor_root"
    assert final_plan[1]["continuity_strategy"] == "stable_anchor_delta"
    assert final_plan[2]["continuity_strategy"] == "stable_anchor_delta"
    assert final_plan[1]["continuity_source_scene"] == 1
    assert final_plan[2]["continuity_source_scene"] == 1
