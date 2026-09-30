"""Offline regressions: real TTS timing serialization, no provider/model calls."""
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.models.schema import VideoParams
from app.services import task as tm
from app.services.state import MemoryState


@pytest.fixture
def narration(tmp_path, monkeypatch):
    # Twelve semantic units force the real planner to enforce the nine-scene cap.
    lines = [f"Esta es la escena {i}." for i in range(12)]
    maker = SimpleNamespace(cues=[SimpleNamespace(
        content=line, start=timedelta(seconds=i * 6),
        end=timedelta(seconds=(i + 1) * 6),
    ) for i, line in enumerate(lines)])
    monkeypatch.setattr(tm.utils, "task_dir", lambda *_: str(tmp_path))
    monkeypatch.setattr(tm.config, "app", {
        "openai_image_base_url": "http://127.0.0.1:8090/v1",
        "openai_image_model": "qwen-image-2.1-precision",
        "openai_image_performance_profile": "balanced",
        "openai_image_balanced_scene_budget": 9,
        # Even a configured Whisper must not be invoked for hidden TTS timing.
        "subtitle_provider": "whisper",
    })
    monkeypatch.setattr(tm.subtitle, "create", Mock(side_effect=AssertionError("No Whisper")))
    monkeypatch.setattr(tm.llm, "generate_script", Mock(side_effect=AssertionError("Fixed script")))
    monkeypatch.setattr(tm.sm, "state", MemoryState())
    monkeypatch.setattr(tm.utils, "check_ffmpeg_ready", lambda: True)
    monkeypatch.setattr(tm.upload_post.upload_post_service, "is_configured", lambda: False)
    return "\n\n".join(lines), maker


def run_pipeline(monkeypatch, script, maker, *, visible=False, custom_audio=None):
    params = VideoParams(video_subject="Camera", video_source="openai_image",
                         video_script=script, subtitle_enabled=visible,
                         custom_audio_file=custom_audio, bgm_type="")
    monkeypatch.setattr(tm, "generate_audio", Mock(return_value=("audio.mp3", 72, maker)))
    references = [{"role": "identity", "description": "Whole camera", "anchor": True}]
    monkeypatch.setattr(tm, "_load_openai_image_reference_inventory", lambda *_: references)
    planner = Mock(side_effect=lambda **kw: [
        {"prompt": scene["narration"], "route": "precision", "reference_need": "identity",
         "reference_target": "primary_subject", "reference_critical": True,
         "includes_primary_subject": True, "planner_validation": "pass"}
        for scene in kw["scene_plan"]])
    monkeypatch.setattr(tm.llm, "generate_scene_image_plan", planner)
    fallback = Mock(side_effect=lambda **kw: ["Uniform scene"] * kw["amount"])
    monkeypatch.setattr(tm.llm, "generate_image_prompts", fallback)
    materials = Mock(return_value=["scene.mp4"])
    monkeypatch.setattr(tm, "get_video_materials", materials)
    render = Mock(return_value=(["final.mp4"], ["combined.mp4"], []))
    monkeypatch.setattr(tm, "generate_final_videos", render)
    warning = Mock()
    monkeypatch.setattr(tm.logger, "warning", warning)
    result = tm.start("timeline-test", params)
    return params, result, planner, fallback, materials, render, warning


def test_hidden_tts_timeline_runs_structured_planner_and_keeps_render_disabled(narration, tmp_path, monkeypatch):
    script, maker = narration
    params, result, planner, fallback, materials, render, warning = run_pipeline(monkeypatch, script, maker)
    assert result["videos"] == ["final.mp4"]
    assert result["script"] == script
    assert params.subtitle_enabled is False
    assert result["subtitle_path"] == ""
    assert render.call_args.args[4] == ""
    assert not (tmp_path / "subtitle.srt").exists()
    assert tm.subtitle.file_to_subtitles(str(tmp_path / "narration.srt"))
    planner.assert_called_once()
    plan = planner.call_args.kwargs["scene_plan"]
    assert len(plan) == 9
    assert sum(s["duration"] for s in plan) == pytest.approx(72)
    assert planner.call_args.kwargs["reference_inventory"][0]["anchor"] is True
    assert planner.call_args.kwargs["precision_budget_ratio"] == 0.65
    assert "precision" in materials.call_args.kwargs["openai_image_scene_routes"]
    assert materials.call_args.kwargs["openai_image_scene_reference_needs"] == ["identity"] * 9
    fallback.assert_not_called()
    assert not any("semantic subtitle timeline unavailable" in str(c) for c in warning.call_args_list)
    tm.subtitle.create.assert_not_called()
    tm.llm.generate_script.assert_not_called()


@pytest.mark.parametrize("word_level", [False, True])
def test_visible_subtitles_reused_without_second_timing_file(narration, tmp_path, monkeypatch, word_level):
    script, maker = narration
    tm.config.app["subtitle_provider"] = "edge"
    params = VideoParams(video_subject="Camera", subtitle_enabled=True,
                         subtitle_display_mode="word_by_word" if word_level else "sentence")
    visible = tm.generate_subtitle("visible", params, script, maker, "audio.mp3")
    assert Path(visible).name == "subtitle.srt"
    before = Path(visible).read_bytes()
    assert tm.prepare_narration_timeline("visible", script, maker, visible) == visible
    assert Path(visible).read_bytes() == before
    assert not (tmp_path / "narration.srt").exists()


def test_visible_pipeline_still_passes_subtitles_to_renderer(narration, tmp_path, monkeypatch):
    script, maker = narration
    tm.config.app["subtitle_provider"] = "edge"
    params, result, planner, fallback, _, render, _ = run_pipeline(monkeypatch, script, maker, visible=True)
    assert params.subtitle_enabled is True
    assert result["subtitle_path"] == str(tmp_path / "subtitle.srt")
    assert render.call_args.args[4] == result["subtitle_path"]
    planner.assert_called_once()
    fallback.assert_not_called()
    assert not (tmp_path / "narration.srt").exists()


@pytest.mark.parametrize("custom_audio", [None, "custom.wav"])
def test_missing_timing_keeps_bounded_fallback_without_whisper(narration, monkeypatch, custom_audio):
    script, _ = narration
    params, result, planner, fallback, materials, render, warning = run_pipeline(
        monkeypatch, script, None, custom_audio=custom_audio)
    assert result["videos"] == ["final.mp4"]
    planner.assert_not_called()
    fallback.assert_called_once()
    assert fallback.call_args.kwargs["amount"] == 9
    assert materials.call_args.kwargs["openai_image_scene_routes"] == ["standard"] * 9
    assert sum(materials.call_args.kwargs["openai_image_scene_durations"]) == pytest.approx(72)
    assert params.subtitle_enabled is False
    assert render.call_args.args[4] == ""
    assert any("semantic subtitle timeline unavailable" in str(c) for c in warning.call_args_list)
    tm.subtitle.create.assert_not_called()


def test_unusable_tts_alignment_returns_empty_without_transcription(narration, monkeypatch):
    script, _ = narration
    # A real empty SubMaker does not produce sentence timing.
    assert tm.prepare_narration_timeline("empty", script, tm.voice.SubMaker()) == ""
    tm.subtitle.create.assert_not_called()


def test_existing_timing_reused_for_custom_audio(narration, tmp_path):
    script, maker = narration
    timeline = tm.prepare_narration_timeline("timed", script, maker)
    assert tm.prepare_narration_timeline("custom", script, None, timeline) == timeline


def test_invalid_existing_subtitles_use_tts_alignment(narration, tmp_path):
    script, maker = narration
    bad = tmp_path / "invalid.srt"
    bad.write_text("not an SRT", encoding="utf-8")
    timeline = tm.prepare_narration_timeline("invalid", script, maker, str(bad))
    assert Path(timeline).name == "narration.srt"
    assert len(tm.build_openai_image_scene_plan(timeline, 72, max_scenes=9)) == 9


@pytest.mark.parametrize("legacy", [False, True])
def test_real_edge_and_legacy_submaker_timing(narration, legacy):
    script, source = narration
    maker = tm.voice.SubMaker()
    if legacy:
        maker = tm.voice.ensure_legacy_submaker_fields(maker)
        maker.subs = [c.content for c in source.cues]
        maker.offset = [(i * 60_000_000, (i + 1) * 60_000_000) for i in range(12)]
    else:
        for i, cue in enumerate(source.cues):
            maker.feed({"type": "WordBoundary", "offset": i * 60_000_000,
                        "duration": 60_000_000, "text": cue.content})
    timeline = tm.prepare_narration_timeline("real-submaker", script, maker)
    assert timeline
    plan = tm.build_openai_image_scene_plan(timeline, 72, max_scenes=9)
    assert len(plan) == 9
    assert sum(s["duration"] for s in plan) == pytest.approx(72)
