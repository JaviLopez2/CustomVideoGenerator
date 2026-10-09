"""Private pipeline injection; generators, HTTP and rendering are offline substitutes."""
import copy
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.config import config
from app.services import material, paired_visual_observation_diagnostics as bridge
from test.services.test_corrective_continuity import pipeline, item  # noqa: F401
from test.services.test_paired_visual_observation_diagnostics import paired  # noqa: F401
from test.test_retained_paired_observations import bundle, cue_plan, shape_plan, prepared  # noqa: F401


def generated(path, model="qwen-image-2.1"):
    value = item("unused"); value.url = str(path); value.source_info["model"] = model
    return value


def prepare(paired, monkeypatch, paths=None, model="qwen-image-2.1"):
    args, observer, store, kind = paired
    paths = paths or [args["reference"] or args["previous"], args["candidate"]]
    items = [generated(p, model) for p in paths]
    generator = Mock(side_effect=[[v] for v in items])
    monkeypatch.setattr(material, "generate_images_openai", generator)
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": False})
    monkeypatch.setattr(material, "_continuity_edit_chain_enabled", lambda: True)
    monkeypatch.setattr(material, "_upload_reference_to_comfyui", lambda path: "uploaded-root.png")
    monkeypatch.setitem(config.app, "openai_image_visual_qa_experimental_enabled", False)
    return args, observer, kind, items, generator


def options(args, count=2):
    return {"search_terms": ["object"] * count, "scene_durations": [1] * count,
            "scene_routes": ["standard"] * count, "scene_subjects": [args["subject"]] * count,
            "scene_continuity_keys": ["phase_one"] * count, "scene_includes_primary_subject": [True] * count,
            "paired_visual_observers": args["observers"],
            "scene_paired_observation_contexts": [None] * (count - 1) + [copy.deepcopy(args["contexts"])]}


@pytest.mark.parametrize("qa_verdict", ["pass", "fail", "uncertain", "unavailable"])
@pytest.mark.parametrize("observation", ["valid", "exception", "invalid", "missing_context"])
def test_paired_diagnostic_cannot_change_qa_or_generation_count(pipeline, paired, monkeypatch, qa_verdict, observation):
    run, diagnostics = pipeline
    args, observer, kind, items, generator = prepare(paired, monkeypatch, model="flux-klein-4b-t2i-exp")
    kwargs = options(args)
    if observation == "exception": observer.side_effect = RuntimeError("reader unavailable")
    elif observation == "invalid": observer.side_effect = None; observer.return_value = {"verdict": "pass", "admission_allowed": True}
    elif observation == "missing_context": kwargs["scene_paired_observation_contexts"] = None
    monkeypatch.setitem(config.app, "openai_image_visual_qa_experimental_enabled", True)
    engine = Mock()
    engine.assess.side_effect = [{"verdict": "pass", "available": True},
                                {"verdict": qa_verdict, "available": qa_verdict != "unavailable"}]
    monkeypatch.setattr(material, "_new_visual_qa_engine", Mock(return_value=engine))
    result = run(**kwargs, scene_qa_contracts=[{"identity_critical": True}] * 2)
    assert bool(result) == (qa_verdict == "pass")
    assert generator.call_count == engine.assess.call_count == 2
    assert observer.call_count == (0 if observation == "missing_context" else 1)
    diagnostic = diagnostics[-1]["plan_scenes"][1]["paired_visual_observation_diagnostic"]
    assert not diagnostic["admission_allowed"] and not diagnostic["automatic_rejection"]
    assert diagnostic["candidate_stage"] == "before_semantic_qa"
    assert items[1].source_info["visual_qa"]["verdict"] == qa_verdict
    if observation == "valid":
        before = diagnostic.get("before_qa_observations", diagnostic["observations"])
        assert before[kind]["status"] == "uncertain"


def test_default_does_not_read_or_hash_paired_diagnostics(pipeline, monkeypatch):
    run, diagnostics = pipeline
    monkeypatch.setattr(material, "generate_images_openai", Mock(return_value=[item("default")]))
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": False})
    reader = Mock(side_effect=AssertionError("Default read")); hasher = Mock(side_effect=AssertionError("Default hash"))
    monkeypatch.setattr(bridge, "diagnose", reader); monkeypatch.setattr(bridge, "_digest", hasher)
    assert run(search_terms=["object"], scene_routes=["standard"])
    reader.assert_not_called(); hasher.assert_not_called()
    assert "paired_visual_observation_diagnostic" not in diagnostics[-1]["plan_scenes"][0]


@pytest.mark.parametrize("contexts", [None, [], ["invalid"], {"wrong": "container"}])
def test_diagnostic_metadata_does_not_abort_scene(pipeline, paired, monkeypatch, contexts):
    run, diagnostics = pipeline
    args, observer, kind, items, generator = prepare(paired, monkeypatch)
    kwargs = options(args); kwargs["scene_paired_observation_contexts"] = contexts
    assert len(run(**kwargs)) == 2 and generator.call_count == 2
    observer.assert_not_called()


def test_reference_stays_root_while_cue_previous_advances(pipeline, paired, monkeypatch, tmp_path):
    run, diagnostics = pipeline
    args = paired[0]
    middle = tmp_path / "intermediate.png"; middle.write_bytes(b"distinct intermediate image")
    source = args["reference"] or args["previous"]
    args, observer, kind, items, generator = prepare(paired, monkeypatch, paths=[source, middle, args["candidate"]])
    assert len(run(**options(args, 3))) == 3
    assert observer.call_count == 1 and generator.call_count == 3
    assert observer.call_args.args[0] == [source if kind == "shape" else middle, args["candidate"]]
    if kind == "cue":
        assert diagnostics[-1]["plan_scenes"][2]["paired_visual_observation_diagnostic"]["status"] == "unavailable"


@pytest.mark.parametrize("phase_change", ["key", "root_reset"])
def test_previous_never_crosses_phase_or_root_reset(pipeline, paired, monkeypatch, phase_change):
    run, diagnostics = pipeline
    args, observer, kind, items, generator = prepare(paired, monkeypatch)
    kwargs = options(args)
    if phase_change == "key": kwargs["scene_continuity_keys"] = ["phase_one", "phase_two"]
    else: kwargs["scene_includes_primary_subject"] = [True, False]
    assert len(run(**kwargs)) == 2
    observer.assert_not_called()
    assert diagnostics[-1]["plan_scenes"][1]["paired_visual_observation_diagnostic"]["status"] == "unavailable"


def test_valid_observation_does_not_verify_klein_when_qa_not_required(pipeline, paired, monkeypatch):
    run, diagnostics = pipeline
    args, observer, kind, items, generator = prepare(paired, monkeypatch, model="flux-klein-4b-t2i-exp")
    monkeypatch.setitem(config.app, "openai_image_visual_qa_experimental_enabled", True)
    engine = Mock()
    engine.assess.side_effect = [{"verdict": "pass", "available": True},
                                {"verdict": "pass", "available": False, "status": "not_required"}]
    monkeypatch.setattr(material, "_new_visual_qa_engine", Mock(return_value=engine))
    assert run(**options(args), scene_qa_contracts=[{"identity_critical": True}, {}]) == []
    assert generator.call_count == engine.assess.call_count == 2 and observer.call_count == 1
    scene = diagnostics[-1]["plan_scenes"][1]
    assert scene["experimental_qa_status"] == "unverified_rejected"
    assert scene["paired_visual_observation_diagnostic"]["before_qa_observations"][kind]["status"] == "uncertain"


def test_unrendered_frame_does_not_become_temporal_previous(pipeline, paired, monkeypatch):
    run, diagnostics = pipeline
    args, observer, kind, items, generator = prepare(paired, monkeypatch)
    renderer = Mock(side_effect=[None, str(args["candidate"]) + ".mp4"])
    monkeypatch.setattr(material, "_render_openai_image_video", renderer)
    kwargs = options(args); kwargs.pop("scene_durations")
    assert run(**kwargs) == [str(args["candidate"]) + ".mp4"]
    assert observer.call_count == (1 if kind == "shape" else 0)


@pytest.mark.parametrize("change", ["replacement", "same_path"])
def test_postprocessing_invalidates_old_observation_without_requery(pipeline, paired, monkeypatch, tmp_path, change):
    run, diagnostics = pipeline
    args, observer, kind, items, generator = prepare(paired, monkeypatch)
    monkeypatch.setattr(material, "_openai_image_color_grading_enabled", lambda: True)
    monkeypatch.setattr(material, "_image_lab_style_profile", lambda path: {"style": 1})
    def grade(path, profile):
        new = tmp_path / "graded.png" if change == "replacement" else Path(path)
        new.write_bytes(b"graded output"); return str(new), {"applied": True}
    monkeypatch.setattr(material, "_color_grade_precision_image", grade)
    kwargs = options(args); kwargs["scene_routes"] = ["standard", "precision"]
    assert len(run(**kwargs)) == 2 and generator.call_count == 2 and observer.call_count == 1
    diagnostic = items[1].source_info["paired_visual_observation_diagnostic"]
    assert diagnostic["status"] == "unavailable" and diagnostic["final_applicability"] == "input_bytes_changed"
    assert diagnostic["before_qa_observations"][kind]["status"] == "uncertain"


def test_existing_gross_retry_keeps_decision_and_invalidates_prior_candidate(pipeline, paired, monkeypatch, tmp_path):
    run, diagnostics = pipeline
    args = paired[0]; source = args["reference"] or args["previous"]
    retry = tmp_path / "retry.png"; retry.write_bytes(b"corrective retry output")
    args, observer, kind, items, generator = prepare(paired, monkeypatch, paths=[source, args["candidate"], retry])
    monkeypatch.setattr(material, "_gross_scene_semantic_qa_enabled", lambda: True)
    monkeypatch.setattr(material, "_gross_scene_semantic_retry_enabled", lambda: True)
    assessment = Mock(side_effect=[{"available": True, "status": "pass", "gross_failure": False},
                                   {"available": True, "status": "fail", "gross_failure": True},
                                   {"available": True, "status": "pass", "gross_failure": False}])
    monkeypatch.setattr(material, "_scene_gross_semantic_assessment", assessment)
    kwargs = options(args); kwargs["scene_planner_validation"] = ["valid", "coverage_fallback"]
    assert run(**kwargs)[-1] == str(retry) + ".mp4"
    assert generator.call_count == assessment.call_count == 3 and observer.call_count == 1
    diagnostic = items[2].source_info["paired_visual_observation_diagnostic"]
    assert diagnostic["status"] == "unavailable" and diagnostic["before_qa_observations"][kind]["status"] == "uncertain"


@pytest.mark.parametrize("selection", ["anchor", "environment", "unbound", "duplicate"])
def test_selected_pack_reference_is_bound_or_unavailable(pipeline, monkeypatch, tmp_path, selection):
    run, diagnostics = pipeline
    first, chosen, candidate = [tmp_path / name for name in ("first.png", "chosen.png", "candidate.png")]
    for path in (first, chosen, candidate): path.write_bytes(path.name.encode())
    pack = [{"slot": 1, "comfyui_input": "first-upload.png", "local_file": first.name, "local_path": str(first), "role": "identity", "anchor": False},
            {"slot": 2, "comfyui_input": "chosen-upload.png", "local_file": chosen.name, "local_path": str(chosen),
             "role": "context" if selection == "environment" else "identity", "anchor": True}]
    if selection == "unbound": del pack[1]["local_path"]
    if selection == "duplicate": pack.append({**pack[1], "slot": 3, "local_path": str(first)})
    info = {"local_path": str(first), "comfyui_input": "first-upload.png", "reference_pack": pack,
            "manual_reference_mode": "user_only"}
    monkeypatch.setattr(material, "_load_manual_precision_reference_manifest", lambda *a: ("user_only", [
        {"stored": row["local_file"], "role": row["role"]} for row in pack]))
    monkeypatch.setattr(material, "_prepare_manual_precision_reference_pack", lambda *a: (["first-upload.png", "chosen-upload.png"], copy.deepcopy(info)))
    old_select = material._select_manual_references_for_scene
    if selection == "environment":
        # The full caller currently suppresses this non-primary route. Exercise
        # its selector/binding directly instead of weakening that route guard.
        selected, selected_info = old_select(["first-upload.png", "chosen-upload.png"], info,
                                             "context", "", reference_target="environment", max_refs=1)
        assert selected == ["chosen-upload.png"]
        assert bridge.selected_reference_path(selected, selected_info) == str(chosen)
        return
    def select(*a, **kw): kw["max_refs"] = 1; return old_select(*a, **kw)
    monkeypatch.setattr(material, "_select_manual_references_for_scene", select)
    generator = Mock(return_value=[generated(candidate)])
    monkeypatch.setattr(material, "generate_images_openai", generator)
    monkeypatch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": False})
    monkeypatch.setitem(config.app, "openai_image_visual_qa_experimental_enabled", False)
    observer = Mock(side_effect=RuntimeError("diagnostic reader unavailable"))
    assert run(search_terms=["object"], scene_durations=[1], scene_routes=["precision"], scene_subjects=["object"],
               scene_reference_needs=["context" if selection == "environment" else "identity"],
               scene_reference_targets=["environment" if selection == "environment" else "primary_subject"],
               scene_includes_primary_subject=[selection != "environment"], paired_visual_observers={"shape": observer},
               scene_paired_observation_contexts=[{"shape": {"subject": "object", "region_ids": ["reference", "candidate"]}}])
    assert generator.call_args.kwargs["reference_images"] == ["chosen-upload.png"]
    if selection in {"unbound", "duplicate"}: observer.assert_not_called()
    else: assert observer.call_args.args[0][0] == chosen
