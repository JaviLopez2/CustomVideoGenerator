"""CPU proof for the fixed retained replay; never sends a model request."""
import collections
import hashlib
import json
from pathlib import Path

from scripts import retained_paired_observations as replay


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/validation/retained-paired-replay-execution-plan-2026-10-09.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(binding):
    path = (ROOT / binding["path"]).resolve()
    assert path.is_relative_to(ROOT) and sha(path) == binding["sha256"]
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    for binding in plan["sources"]:
        assert sha(ROOT / binding["path"]) == binding["sha256"], binding["path"]
    design = read(plan["design"])
    result_path = ROOT / plan["output"]
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["protocol"] == replay.VERSION
    assert result["design_sha256"] == plan["design"]["sha256"]
    assert result["adapter_sha256"] == sha(replay.__file__)
    assert all(type(result[k]) is int and result[k] == 0 for k in
               ("model_requests", "generation_requests", "downloads", "service_changes"))
    assert result["admission_allowed"] is False and result["human_gold_added"] is False
    assert len(result["cohorts"]) == len(design["initial_cohorts"]) == 4
    statuses, reasons, raw_count, controls, summaries, mappings = collections.Counter(), collections.Counter(), 0, [], [], {}
    for declared, exported in zip(design["initial_cohorts"], result["cohorts"]):
        raw = read(declared["raw"])
        store = replay.RetainedPairedObservations.from_files(declared["raw"], declared["plan"], kind=declared["kind"], root=ROOT)
        contexts = store.contexts()
        assert exported["kind"] == declared["kind"] and exported["raw_sha256"] == declared["raw"]["sha256"]
        assert len(exported["rows"]) == len(contexts)
        recorded = {row["case_id"]: row for row in raw["rows"]}
        cohort_statuses = collections.Counter()
        for context, row in zip(contexts, exported["rows"]):
            assert row["case_id"] == context["case_id"]
            observed = row["result"]
            assert observed["status"] in {"uncertain", "unavailable"}
            assert observed["verdict"] == observed["status"] and observed["available"] == (observed["status"] == "uncertain")
            assert all(observed[k] is None for k in ("identity_score", "state_score", "progression_score"))
            assert all(observed[k] is False for k in ("admission_allowed", "automatic_rejection", "physical_identity_established",
                                                     "physical_temperature_measured", "pixel_truth_verified"))
            assert observed["model_requests"] == observed["generation_requests"] == 0
            statuses[observed["status"]] += 1; reasons[observed["reason"]] += 1; cohort_statuses[observed["status"]] += 1
            if row["case_id"] in recorded:
                original = recorded[row["case_id"]]
                assert observed["raw_observation"]["final_content"] == original["final_content"]
                assert observed["raw_observation"]["recorded_transport_status"] == original["transport_status"]
                assert observed["raw_observation"]["finish_reason"] == original["finish_reason"]
                assert observed["raw_observation"]["reasoning_characters"] == original["reasoning_characters"]
                assert observed["source_report_sha256"] == declared["raw"]["sha256"]
                assert observed["source_plan_sha256"] == declared["plan"]["sha256"]
                assert observed["ordered_regions"] == context["region_ids"] and observed["subject"] == context["subject"]
                assert observed["cue_query"] == context["cue_query"]
                raw_count += 1
                for region_id, descriptor in zip(context["region_ids"], observed["inputs"]):
                    mappings[(declared["kind"], region_id)] = {"kind": declared["kind"], "region_id": region_id, **descriptor}
            else:
                assert observed["reason"] == "no_recorded_pair" and "raw_observation" not in observed
            if observed["status"] == "uncertain":
                assert observed["observation"] == recorded[row["case_id"]]["observation"]
        last = {k: v for k, v in contexts[-1].items() if k != "case_id"}
        wrong_subject = store.lookup(**{**last, "subject": "different subject"})
        assert wrong_subject["reason"] == "context_mismatch" and wrong_subject["status"] == "unavailable"
        reversed_pair = store.lookup(**{**last, "images": list(reversed(last["images"])), "region_ids": list(reversed(last["region_ids"]))})
        assert reversed_pair["reason"] == "no_recorded_pair" and reversed_pair["status"] == "unavailable"
        if declared["kind"] == "cue":
            assert store.lookup(**{**last, "cue_query": "different cue"})["reason"] == "context_mismatch"
        controls.append({"raw_sha256": declared["raw"]["sha256"], "wrong_subject": "unavailable",
                         "unrecorded_reversed_pair": "unavailable", "wrong_cue": "unavailable" if declared["kind"] == "cue" else "not_applicable"})
        summaries.append({"kind": declared["kind"], "reported_model_repo": raw["model"]["repo"],
                          "planned_contexts": len(contexts), "retained_rows": len(recorded), "statuses": dict(cohort_statuses)})
    assert dict(statuses) == plan["expected_statuses"] and dict(reasons) == plan["expected_reasons"]
    assert raw_count == plan["expected_retained_rows"] == 11
    report = {"protocol": "retained-paired-replay-proof-1", "execution_plan_sha256": sha(PLAN), "result_sha256": sha(result_path),
              "retained_rows_preserved": raw_count, "planned_contexts": sum(statuses.values()), "statuses": dict(statuses),
              "reasons": dict(reasons), "cohorts": summaries, "lookup_controls": controls,
              "source_prepared_mappings": list(mappings.values()), "frozen_sources_unchanged": True,
              "model_requests": 0, "generation_requests": 0, "human_gold_added": False,
              "perceptual_accuracy_measured": False, "candidate_selected": False, "application_wired": False}
    with (ROOT / plan["verification_output"]).open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write("\n")
    print(json.dumps({"planned_contexts": sum(statuses.values()), "retained_rows": raw_count, "statuses": dict(statuses), "model_requests": 0}))


if __name__ == "__main__":
    main()
