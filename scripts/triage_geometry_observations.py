"""Offline experimental review priorities; no automatic acceptance or rejection."""
import argparse
import hashlib
import json
import runpy
import subprocess
from pathlib import Path

OBSERVER = runpy.run_path(str(Path(__file__).with_name("observe_visual_geometry.py")))
VERSION = "geometry-review-priorities-1"


def validate_review(review):
    if not isinstance(review, dict) or set(review) != {"shape", "localized_change", "note", "source"}:
        raise ValueError("Incomplete human review")
    if review["source"] != "human" or review["shape"] not in {"preserved", "changed", "uncertain"}:
        raise ValueError("Review is not a valid human annotation")
    if type(review["localized_change"]) is not bool or not isinstance(review["note"], str) or not review["note"].strip():
        raise ValueError("Invalid human review details")


def triage(reference, candidate, review=None):
    """Separate verified reviewer statements from categorical, unverified model hints."""
    if review is not None:
        validate_review(review)
    result = {"policy_version": VERSION, "status": "uncertain", "admission_allowed": False,
              "automatic_rejection": False, "human_review": review, "hints": [],
              "model_evidence_status": "available", "human_review_pending": review is None,
              "tolerance_decision": "not_defined", "physical_identity_established": False,
              "limitations": ["Categorical observations do not measure shape or size.",
                              "Model hints are unverified; even agreement cannot prove identity."]}
    try:
        comparison = OBSERVER["compare"](reference, candidate)
        result["hints"] = comparison["hints"]
    except (ValueError, TypeError):
        result.update(status="unavailable", model_evidence_status="unavailable", priority="obtain_observation")
        return result
    kinds = {h["kind"] for h in result["hints"]}
    if review is not None:
        if review["shape"] == "changed":
            result["priority"] = "human_reported_structural_change"
        elif review["shape"] == "uncertain":
            result["priority"] = "human_observation_inconclusive"
        elif review["localized_change"]:
            result["priority"] = "human_reported_local_variation"
        elif kinds & {"presence_disagreement", "count_disagreement"}:
            result["priority"] = "model_human_disagreement"
        else:
            result["priority"] = "human_reports_preservation"
    elif "presence_disagreement" in kinds:
        result["priority"] = "model_structure_review"
    elif kinds & {"insufficient_observation", "insufficient_count"}:
        result["priority"] = "observation_incomplete"
    elif "count_disagreement" in kinds:
        result["priority"] = "model_count_review"
    else:
        result["priority"] = "no_detected_signal"
    # Human conclusions do not silently repair incomplete model observations.
    result["model_observation_incomplete"] = bool(kinds & {"insufficient_observation", "insufficient_count"})
    return result


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replay(observations, reviews):
    inventories = {row["sha256"]: row.get("inventory") if row.get("transport_status") == "completed" else None
                   for row in observations["rows"]}
    comparisons = {c["id"]: c for c in observations["comparisons"]}
    supplied = reviews["cases"]
    ids = [c["source_case_id"] for c in supplied]
    if len(ids) != len(set(ids)) or set(ids) - set(comparisons):
        raise ValueError("Unknown or duplicate review case")
    for supplied_case in supplied:
        comparison = comparisons[supplied_case["source_case_id"]]
        if supplied_case["reference_sha256"] != comparison["reference_sha256"] or supplied_case["candidate_sha256"] != comparison["candidate_sha256"]:
            raise ValueError("Review images do not match observations")
        validate_review(supplied_case["review"])
    by_id = {c["source_case_id"]: c for c in supplied}
    rows = []
    for comparison in observations["comparisons"]:
        review = by_id.get(comparison["id"], {}).get("review")
        reference = inventories.get(comparison["reference_sha256"])
        candidate = inventories.get(comparison["candidate_sha256"])
        rows.append({"id": comparison["id"], "reference_sha256": comparison["reference_sha256"],
                     "candidate_sha256": comparison["candidate_sha256"],
                     "model_only": triage(reference, candidate),
                     "with_human_review": triage(reference, candidate, review)})
    return rows


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--observations", required=True)
    parser.add_argument("--reviews", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Preserve prior evidence")
    observations = json.loads(Path(args.observations).read_text(encoding="utf-8"))
    reviews = json.loads(Path(args.reviews).read_text(encoding="utf-8"))
    if reviews["observation_evidence_sha256"] != digest(args.observations):
        raise ValueError("Observations changed")
    report = {"execution_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "policy_version": VERSION, "source_sha256": digest(__file__),
              "observations_sha256": digest(args.observations), "reviews_sha256": digest(args.reviews),
              "new_model_requests": 0, "new_generation_requests": 0,
              "automatic_decisions": 0, "rows": replay(observations, reviews)}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pairs": len(report["rows"]), "automatic_decisions": 0}))


if __name__ == "__main__":
    main()
