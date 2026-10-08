"""Review priorities must not turn model guesses into physical identity or a gate."""
import copy
import runpy
from pathlib import Path

import pytest

M = runpy.run_path(str(Path(__file__).parents[1] / "scripts/triage_geometry_observations.py"))


def inventory():
    return {f: {"visibility": "present", "observed_count": 1, "description": "Visible component"}
            for f in M["OBSERVER"]["FEATURES"]}


def review(shape="preserved", localized_change=False):
    return {"shape": shape, "localized_change": localized_change, "note": "Direct image review", "source": "human"}


@pytest.mark.parametrize("human", [None, review(), review("changed"), review(localized_change=True), review("uncertain")])
def test_no_review_priority_can_make_an_automatic_decision(human):
    result = M["triage"](inventory(), inventory(), human)
    assert result["status"] == "uncertain"
    assert not result["admission_allowed"] and not result["automatic_rejection"]
    assert not result["physical_identity_established"] and result["tolerance_decision"] == "not_defined"


def test_model_presence_signal_is_unverified_structure_review():
    candidate = inventory()
    candidate["openings"].update(visibility="absent", observed_count=0)
    result = M["triage"](inventory(), candidate)
    assert result["priority"] == "model_structure_review"
    assert result["human_review_pending"] and result["hints"]


def test_count_difference_cannot_be_assumed_minor_or_structural():
    candidate = inventory()
    candidate["edge_cutouts"]["observed_count"] = 2
    result = M["triage"](inventory(), candidate)
    assert result["priority"] == "model_count_review"
    with_review = M["triage"](inventory(), candidate, review())
    assert with_review["priority"] == "model_human_disagreement"
    assert with_review["hints"] == result["hints"]


def test_matching_inventory_does_not_erase_reported_local_variation():
    result = M["triage"](inventory(), inventory(), review(localized_change=True))
    assert result["priority"] == "human_reported_local_variation"
    assert result["human_review"]["localized_change"] and not result["human_review_pending"]


def test_unknown_observation_survives_human_preservation_review():
    candidate = inventory()
    candidate["openings"].update(visibility="uncertain", observed_count=None)
    result = M["triage"](inventory(), candidate, review())
    assert result["model_observation_incomplete"] and result["hints"]
    assert not result["admission_allowed"]


@pytest.mark.parametrize("bad", [None, {}, {"invented": "part"}])
def test_missing_or_invalid_inventory_remains_unavailable(bad):
    result = M["triage"](bad, inventory(), review("changed"))
    assert result["status"] == "unavailable" and result["priority"] == "obtain_observation"


@pytest.mark.parametrize("update", [{"source": "model"}, {"localized_change": "false"}, {"shape": "pass"}, {"note": ""}])
def test_model_labels_cannot_be_passed_as_human_review(update):
    human = review()
    human.update(update)
    with pytest.raises(ValueError):
        M["triage"](inventory(), inventory(), human)


def test_replay_refuses_annotation_for_different_image_or_duplicate_case():
    observations = {"rows": [], "comparisons": [{"id": "case", "reference_sha256": "ref", "candidate_sha256": "candidate"}]}
    case = {"source_case_id": "case", "reference_sha256": "ref", "candidate_sha256": "other", "review": review()}
    with pytest.raises(ValueError):
        M["replay"](observations, {"cases": [case]})
    case["candidate_sha256"] = "candidate"
    with pytest.raises(ValueError):
        M["replay"](observations, {"cases": [case, copy.deepcopy(case)]})


def test_incomplete_transport_cannot_supply_an_inventory():
    observations = {"rows": [{"sha256": sha, "inventory": inventory(), "transport_status": status}
                    for sha, status in [("ref", "completed"), ("candidate", "unavailable")]],
                    "comparisons": [{"id": "case", "reference_sha256": "ref", "candidate_sha256": "candidate"}]}
    result = M["replay"](observations, {"cases": []})[0]["model_only"]
    assert result["status"] == "unavailable" and not result["admission_allowed"]
