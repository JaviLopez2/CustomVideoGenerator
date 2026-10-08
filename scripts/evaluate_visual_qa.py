"""Evaluate retained local artifacts; never submit image generation requests."""

import argparse
import json
import os
import statistics
import time
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from app.config import config
from app.services import material, visual_qa


def normalized_legacy(result):
    if not result.get("available"):
        return "unavailable"
    return {"reject": "fail", "pass": "pass", "uncertain": "uncertain"}.get(result.get("verdict"), "uncertain")


def confusion(rows, field):
    counts = dict(true_positives=0, true_negatives=0, false_positives=0,
                  false_negatives=0, uncertain=0, unavailable=0)
    for row in rows:
        expected, actual = row["expected"], row[field]["verdict"]
        if actual in {"uncertain", "unavailable"}:
            counts[actual] += 1
        elif expected == "fail":
            counts["true_positives" if actual == "fail" else "false_negatives"] += 1
        elif expected == "pass":
            counts["false_positives" if actual == "fail" else "true_negatives"] += 1
    times = [row[field]["seconds"] for row in rows]
    counts.update(mean_seconds=statistics.mean(times), median_seconds=statistics.median(times),
                  max_seconds=max(times), decided_cases=sum(row[field]["verdict"] in {"pass", "fail"} for row in rows),
                  cases_with_uncertain_expected=sum(row["expected"] == "uncertain" for row in rows))
    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--legacy-fast", action="store_true", help="Replay legacy logic with opt-in bounded no-thinking transport")
    args = parser.parse_args()
    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    output = Path(args.output)
    if output.exists():
        raise ValueError("Preserve existing evidence; choose a new output file")
    config.app["openai_image_precision_semantic_device"] = "cpu"
    config.app["openai_image_qa_fast_local_judge"] = True
    engine = material._new_visual_qa_engine()
    report = {"dataset": args.dataset, "schema_version": 1, "rows": [],
              "baseline_label": "Legacy decision logic + fast local transport, NOT historical unbounded-thinking latency",
              "generation_requests": 0, "automatic_qa_retries": 0}
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save()
    for case in dataset["cases"]:
        assert visual_qa.digest(case["artifact"]) == case["sha256"]
        row = {"id": case["id"], "expected": case["expected_verdict"], "review_reason": case["review_reason"]}
        try:
            row["new"] = engine.assess(case["artifact"], case["contract"])
        except (OSError, ValueError, RuntimeError, TypeError) as exc:
            row["new"] = {"verdict": "unavailable", "seconds": 0, "exception_type": type(exc).__name__}
        if args.legacy_fast:
            candidate = material.MaterialInfo()
            candidate.url = case["artifact"]
            contract = case["contract"]
            required = [f"exactly {r['expected_count']} {r['subject']}" for r in contract.get("counts", [])]
            required += contract.get("geometry_constraints", [])
            started = time.perf_counter()
            old = material._scene_gross_semantic_assessment(
                candidate, subject=contract["subject"], required_features=required,
                forbidden_features=["unrequested lettering"] if contract.get("forbid_text") else [],
                require_single=False,
            )
            old_result = {"verdict": normalized_legacy(old), "seconds": time.perf_counter() - started,
                          "gross_status": old.get("status"), "caption": old.get("caption")}
            if contract.get("temporal"):
                temporal = contract["temporal"]
                previous_caption = ""
                if temporal.get("previous_image"):
                    previous_caption, _ = material._precision_florence_caption(temporal["previous_image"])
                state = material._scene_temporal_semantic_assessment(
                    candidate, subject=contract["subject"], requested_state=temporal["expected_state"],
                    previous_state=temporal.get("previous_state", ""), previous_caption=previous_caption,
                )
                old_result["temporal"] = {k: state.get(k) for k in ["available", "status", "verdict", "state_score", "progression_score"]}
                old_result["verdict"] = visual_qa.overall([{"status": old_result["verdict"]}, {"status": normalized_legacy(state)}])
                old_result["seconds"] = time.perf_counter() - started
            row["legacy_fast"] = old_result
        report["rows"].append(row)
        save()
        print(json.dumps({"id": row["id"], "expected": row["expected"], "new": row["new"]["verdict"],
                          "new_seconds": round(row["new"]["seconds"], 3),
                          "legacy_fast": row.get("legacy_fast", {}).get("verdict"),
                          "legacy_fast_seconds": round(row.get("legacy_fast", {}).get("seconds", 0), 3)}), flush=True)
    report["metrics"] = {"new": confusion(report["rows"], "new")}
    if args.legacy_fast:
        report["metrics"]["legacy_fast"] = confusion(report["rows"], "legacy_fast")
    report["repeat_identical"] = engine.assess(dataset["cases"][0]["artifact"], dataset["cases"][0]["contract"])
    report["limits"] = ["16 curated cases, no independent human adjudication; metrics preliminary.",
                        "Unknown expected case excluded from binary confusion counts; abstentions reported separately.",
                        "No p95 reported for this small dataset.", "New geometry masks do not certify internal structure."]
    save()
    material._release_precision_semantic_model()
    print(json.dumps(report["metrics"]), flush=True)


if __name__ == "__main__":
    main()
