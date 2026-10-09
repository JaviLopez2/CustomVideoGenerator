"""Retained images through the private MPT caller; all runtime/rendering mocked."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock

import pytest

from app.config import config
from app.services import material
from scripts.retained_paired_observations import RetainedPairedObservations
from test.services.test_corrective_continuity import pipeline, item


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/validation/paired-diagnostic-bridge-execution-plan-2026-10-09.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_mock_pipeline(paths, contexts, store, kind, subject, directory, enabled):
    with pytest.MonkeyPatch.context() as patch:
        run, ledger = pipeline.__wrapped__(patch, directory)
        patch.setitem(config.app, "openai_image_visual_qa_experimental_enabled", False)
        patch.setattr(material, "_continuity_edit_chain_enabled", lambda: True)
        patch.setattr(material, "_near_duplicate_assessment", lambda *a, **kw: {"actionable": False})
        patch.setattr(material, "_upload_reference_to_comfyui", lambda path: "retained-root-upload.png")
        values = []
        for path in paths:
            value = item("unused"); value.url = str(path); value.source_info["model"] = "offline_legacy_generator_substitute"
            values.append(value)
        generator = Mock(side_effect=[[value] for value in values])
        patch.setattr(material, "generate_images_openai", generator)
        observer = Mock(wraps=store.lookup)
        options = {"search_terms": ["retained input"] * len(paths), "scene_routes": ["standard"] * len(paths),
                   "scene_durations": [1] * len(paths), "scene_subjects": [subject] * len(paths),
                   "scene_continuity_keys": ["retained_phase"] * len(paths), "scene_includes_primary_subject": [True] * len(paths)}
        if enabled:
            options.update(paired_visual_observers={kind: observer}, scene_paired_observation_contexts=contexts)
        videos = run(**options)
        assert len(videos) == generator.call_count == len(paths)
        assert all(not Path(path).exists() for path in videos), "Rendering must remain a substitute"
        return videos, generator.call_count, observer.call_count, ledger[-1]["plan_scenes"]


def main():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    for binding in plan["sources"]:
        assert digest(ROOT / binding["path"]) == binding["sha256"], binding["path"]
    design_binding = plan["retained_design"]
    assert digest(ROOT / design_binding["path"]) == design_binding["sha256"]
    design = json.loads((ROOT / design_binding["path"]).read_text(encoding="utf-8"))
    results = []
    for declared in design["initial_cohorts"]:
        store = RetainedPairedObservations.from_files(declared["raw"], declared["plan"], kind=declared["kind"], root=ROOT)
        recorded = store.contexts()
        selected = recorded if declared["kind"] == "cue" else [recorded[0], recorded[2]]
        paths = [Path(context["images"][1]) for context in selected]
        contexts = []
        for context in selected:
            data = {k: copy.deepcopy(context[k]) for k in ("subject", "region_ids")}
            if declared["kind"] == "cue": data["cue_query"] = context["cue_query"]
            contexts.append({declared["kind"]: data})
        with tempfile.TemporaryDirectory(prefix="mpt-paired-bridge-") as temporary:
            directory = Path(temporary)
            baseline = run_mock_pipeline(paths, contexts, store, declared["kind"], selected[0]["subject"], directory, False)
            injected = run_mock_pipeline(paths, contexts, store, declared["kind"], selected[0]["subject"], directory, True)
        assert baseline[0] == injected[0] and baseline[1] == injected[1]
        assert all("paired_visual_observation_diagnostic" not in row for row in baseline[3])
        rows = []
        for context, scene in zip(selected, injected[3]):
            diagnostic = scene["paired_visual_observation_diagnostic"]
            assert diagnostic["admission_allowed"] is False and diagnostic["automatic_rejection"] is False
            assert all(diagnostic[k] is None for k in ("identity_score", "state_score", "progression_score"))
            rows.append({"retained_case_id": context["case_id"], "scene": scene["scene"], "diagnostic": diagnostic})
        results.append({"kind": declared["kind"], "raw_sha256": declared["raw"]["sha256"], "source_subject": selected[0]["subject"],
                        "selected_raw_case_ids": [context["case_id"] for context in selected], "mock_scene_count": len(paths),
                        "mock_generation_calls_per_run": injected[1], "retained_reader_calls": injected[2],
                        "baseline_and_injected_outputs_equal": True, "rows": rows})
    statuses = [row["diagnostic"]["status"] for cohort in results for row in cohort["rows"]]
    assert len(statuses) == 12 and statuses.count("uncertain") == 4 and statuses.count("unavailable") == 8
    report = {"protocol": "paired-diagnostic-bridge-cpu-proof-1", "execution_plan_sha256": digest(PLAN),
              "test_scope": "Real retained images/reader through actual private MPT loop; generators, uploads, QA policy/runtime and render replaced offline",
              "real_model_requests": 0, "real_generation_requests": 0, "real_uploads": 0, "real_rendered_videos": 0,
              "services_changed": 0, "human_labels_added": False, "qa_accuracy_measured": False, "judge_selected": False,
              "app_defaults_activated": False, "mock_scenes": 12, "diagnostic_statuses": {"uncertain": 4, "unavailable": 8},
              "cohorts": results,
              "evidence_gap": "Hot cue raw compares baseline->hot. Actual adjacent pipeline image is warm->hot; retained lookup remains unavailable. First scene has no prior/reference; no fake self-pair. Missing Qwen3-VL rows remain unavailable."}
    with (ROOT / plan["output"]).open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write("\n")
    print(json.dumps({"mock_scenes": 12, "statuses": report["diagnostic_statuses"], "real_model_requests": 0,
                      "baseline_and_injected_outputs_equal": True}))


if __name__ == "__main__":
    main()
