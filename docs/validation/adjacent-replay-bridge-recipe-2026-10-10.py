"""Original retained adjacent images through MPT; all generation/rendering offline."""
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.retained_paired_observations import RetainedPairedObservations

PLAN = ROOT / "docs/validation/adjacent-replay-bridge-plan-2026-10-10.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    for binding in plan["implementation"]:
        assert digest(ROOT / binding["path"]) == binding["sha256"]
    helper_path = ROOT / "docs/validation/paired-diagnostic-bridge-recipe-2026-10-09.py"
    # Explicit local code, not a path from the report or other untrusted metadata.
    helper = runpy.run_path(str(helper_path))["run_mock_pipeline"]
    cohorts = []
    for declared in plan["cohorts"]:
        store = RetainedPairedObservations.from_files(declared["raw"], declared["plan"], kind="cue", root=ROOT)
        context = store.contexts()[0]
        paths = [Path(path) for path in context["images"]]
        for path in paths:
            assert path.is_relative_to(ROOT)
        scene_context = {"cue": {k: copy.deepcopy(context[k]) for k in ("subject", "region_ids", "cue_query")}}
        with tempfile.TemporaryDirectory(prefix="mpt-adjacent-proof-") as temporary:
            baseline = helper(paths, [scene_context] * 2, store, "cue", context["subject"], Path(temporary), False)
            injected = helper(paths, [scene_context] * 2, store, "cue", context["subject"], Path(temporary), True)
        assert baseline[:2] == injected[:2]
        assert baseline[2] == 0 and injected[2] == 1
        assert all("paired_visual_observation_diagnostic" not in row for row in baseline[3])
        diagnoses = [row["paired_visual_observation_diagnostic"] for row in injected[3]]
        assert diagnoses[0]["observations"]["cue"]["status"] == "unavailable"
        assert diagnoses[1]["observations"]["cue"]["status"] == "uncertain"
        assert diagnoses[1]["observations"]["cue"]["visible_transition"] == "reported_visible_in_both"
        for result in diagnoses:
            assert result["admission_allowed"] is False and result["automatic_rejection"] is False
            assert all(result[key] is None for key in ("identity_score", "state_score", "progression_score"))
        cohorts.append({"model": declared["model"], "raw_binding": declared["raw"], "context": context,
                        "mock_scene_count": 2, "mock_generation_calls_per_run": injected[1],
                        "retained_reader_calls": injected[2], "baseline_and_injected_outputs_equal": True,
                        "diagnoses": diagnoses})
    result = {"protocol": "retained-adjacent-mpt-cpu-proof-1", "execution_plan_sha256": digest(PLAN),
              "scope": "Actual private MPT loop/original files; generation, upload, QA policy and rendering substituted",
              "real_model_requests": 0, "real_generation_requests": 0, "real_uploads": 0, "real_rendered_videos": 0,
              "human_gold_added": False, "judge_selected": False, "qa_accuracy_measured": False,
              "mock_scenes": 4, "retained_reader_calls": 2, "cohorts": cohorts}
    with (ROOT / plan["output"]).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2); stream.write("\n")
    print(json.dumps({"mock_scenes": 4, "retained_reader_calls": 2, "statuses": ["unavailable", "uncertain"] * 2,
                      "outputs_equal": True, "real_model_requests": 0}))


if __name__ == "__main__":
    main()
