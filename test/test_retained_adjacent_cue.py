import copy
import hashlib
import json
from pathlib import Path

import pytest
from scripts import retained_paired_observations as replay
from scripts import pairwise_cue_observations as cue
from scripts import paired_shape_preflight as checks
from test.test_retained_paired_observations import bundle, cue_plan, shape_plan, prepared, sync, write_json, sha  # noqa: F401

pytestmark = pytest.mark.parametrize("bundle", ["cue"], indirect=True)


@pytest.fixture
def adjacent(bundle, monkeypatch):
    b = bundle
    ids = ["previous_same_bytes", "retained_warm_512", "retained_hot_768", "retained_cooled_768"]
    for case, raw, identifier in zip(b.method["cases"], b.raw["rows"], ids):
        case["case_id"] = raw["case_id"] = identifier
    b.method["execution"]["case_order"] = ids
    b.plan["execution_base_head"] = b.raw["execution_head"] = "a" * 40
    sync(b)
    b.published = copy.deepcopy(b.plan_binding)
    warm, hot = b.method["cases"][1:3]
    b.case = {"case_id": "retained_warm_to_hot_adjacent", "previous_region_id": warm["current_region_id"],
              "current_region_id": hot["current_region_id"], "previous": warm["current"], "current": hot["current"]}
    recipe_path = b.root / "known-recipe.py"
    recipe_path.write_text("raise RuntimeError('Never execute this fixture')", encoding="utf-8")
    monkeypatch.setattr(replay, "ADJACENT_RECIPE", recipe_path, raising=False)
    b.plan = {"protocol": "retained-adjacent-cue-plan-1", "execution_base_head": "a" * 40,
              "recipe": {"path": str(recipe_path), "sha256": sha(recipe_path)}, "published_source_plan": b.published,
              "budget": {"requests_per_model": 1, "maximum_requests_total": 2, "automatic_retries": 0,
                         "new_generation_requests": 0, "new_downloads": 0, "stop_at_first_invalid_or_unavailable": True},
              "cases": [b.case], "comparison_candidates": b.method["comparison_candidates"],
              "human_gold": False, "expected_cue_visibility": None}
    b.raw = {k: copy.deepcopy(v) for k, v in b.raw.items() if k not in ["plan_sha256", "design", "rows"]}
    row = {"case_id": b.case["case_id"], "inputs": [{"role": r, "sha256": b.case[r]["sha256"]} for r in b.roles],
           "request_sha256": hashlib.sha256(checks.canonical(cue.payload(b.case["previous"], b.case["current"],
                                                        b.method["subject"], b.method["cue_query"])).encode()).hexdigest(),
           "request_attempted": True, "transport_status": "completed", "finish_reason": "stop", "reasoning_characters": 0,
           "observation": {r + "_" + f: v for r in b.roles for f, v in
                            [("subject_presence", "present"), ("cue_visibility", "observed"), ("evidence", "Visible wisps")]}}
    row["final_content"] = json.dumps(row["observation"])
    b.raw.update(protocol="retained-adjacent-cue-result-1", observer_version=cue.VERSION,
                 source_plan=b.published, recipe=b.plan["recipe"], rows=[row], http_model_requests_attempted=1,
                 automatic_retries=0, generation_requests=0, human_gold=False, admission_allowed=False,
                 physical_identity_established=False, physical_temperature_measured=False, unattempted_cases=[])
    store(b, load=False)
    return b


def store(b, *, load=True):
    b.plan_binding = write_json(b.root / "adjacent-plan.json", b.plan)
    b.raw["plan"] = copy.deepcopy(b.plan_binding)
    b.raw_binding = write_json(b.root / "adjacent-report.json", b.raw)
    if load:
        return replay.RetainedPairedObservations.from_files(b.raw_binding, b.plan_binding, kind="cue", root=b.root)


def context(store):
    result = store.contexts()[0]; result.pop("case_id")
    return result


def test_original_adjacent_context_raw_and_diagnostic_are_source_bound(adjacent):
    s = store(adjacent); ctx = context(s); result = s.lookup(**ctx)
    assert ctx["images"] == [adjacent.regions[i]["source"]["path"] for i in ctx["region_ids"]]
    assert result["status"] == "uncertain" and result["visible_transition"] == "reported_visible_in_both"
    assert result["raw_observation"]["final_content"] == adjacent.raw["rows"][0]["final_content"]
    assert all(result[k] is None for k in ["identity_score", "state_score", "progression_score"])
    assert result["admission_allowed"] is False and result["model_requests"] == 0


def test_current_private_bridge_accepts_original_adjacent_context_without_admission(adjacent):
    from app.services import paired_visual_observation_diagnostics as bridge
    s = store(adjacent); ctx = context(s)
    previous, candidate = ctx["images"]
    result = bridge.diagnose(candidate, reference=None, previous=previous, subject=ctx["subject"],
               contexts={"cue": {k: ctx[k] for k in ["subject", "cue_query", "region_ids"]}},
               observers={"cue": s.lookup})
    result = bridge.finalize(result, candidate, reference=None, previous=previous)
    assert result["observations"]["cue"]["status"] == "uncertain"
    assert result["observations"]["cue"]["visible_transition"] == "reported_visible_in_both"
    assert result["admission_allowed"] is False and result["automatic_rejection"] is False


@pytest.mark.parametrize("mutation", ["protocol", "observer", "recipe", "recipe_path", "source_plan", "implementation", "head", "model",
                                     "fingerprint", "reversed", "baseline", "relative", "budget", "budget_bool", "retry", "generation", "gold", "extra_row",
                                     "head_missing", "head_invalid", "head_type"])
def test_changed_context_or_provenance_is_rejected(adjacent, mutation):
    b = adjacent
    if mutation == "protocol": b.raw["protocol"] = cue.VERSION
    if mutation == "observer": b.raw["observer_version"] = "other"
    if mutation == "recipe": b.raw["recipe"] = {**b.raw["recipe"], "sha256": "0" * 64}
    if mutation == "recipe_path": b.plan["recipe"] = b.published
    if mutation == "source_plan": b.raw["source_plan"] = {**b.published, "sha256": "0" * 64}
    if mutation == "implementation": b.raw["implementation"] = {}
    if mutation == "head": b.raw["execution_head"] = "b" * 40
    if mutation == "head_missing": b.plan.pop("execution_base_head"); b.raw["execution_head"] = "not-a-commit"
    if mutation == "head_invalid": b.plan["execution_base_head"] = b.raw["execution_head"] = "not-a-commit"
    if mutation == "head_type": b.plan["execution_base_head"] = b.raw["execution_head"] = 1
    if mutation == "model": b.raw["model"]["files"][0]["sha256"] = "0" * 64
    if mutation == "fingerprint": b.raw["rows"][0]["request_sha256"] = "0" * 64
    if mutation == "reversed": b.plan["cases"][0]["previous"], b.plan["cases"][0]["current"] = b.case["current"], b.case["previous"]
    if mutation == "baseline": b.plan["cases"][0]["previous"] = b.method["cases"][0]["previous"]
    if mutation == "relative": b.plan["cases"][0]["previous"]["path"] = "source.png"
    if mutation == "budget": b.plan["budget"]["requests_per_model"] = 2
    if mutation == "budget_bool": b.plan["budget"]["requests_per_model"] = True
    if mutation == "retry": b.raw["automatic_retries"] = 1
    if mutation == "generation": b.raw["generation_requests"] = 1
    if mutation == "gold": b.raw["human_gold"] = True
    if mutation == "extra_row": b.raw["rows"].append(copy.deepcopy(b.raw["rows"][0]))
    with pytest.raises(ValueError): store(b)


@pytest.mark.parametrize("bad", ["json", "reasoning", "truncated", "contradiction"])
def test_invalid_raw_is_preserved_as_unavailable_despite_saved_pass(adjacent, bad):
    b = adjacent; row = b.raw["rows"][0]; row["diagnostic"] = {"verdict": "pass", "admission_allowed": True}
    if bad == "json": row["final_content"] = "invalid JSON"
    if bad == "reasoning": row["reasoning_characters"] = 10
    if bad == "truncated": row["finish_reason"] = "length"
    if bad == "contradiction":
        row["observation"]["previous_subject_presence"] = "uncertain"
        row["final_content"] = json.dumps(row["observation"])
    s = store(b); result = s.lookup(**context(s))
    assert result["status"] == "unavailable" and result["admission_allowed"] is False
    assert result["raw_observation"]["final_content"] == row["final_content"]


@pytest.mark.parametrize("dependency", ["source", "recipe", "published", "preparation"])
def test_dependency_mutation_invalidates_lookup(adjacent, dependency):
    b = adjacent; s = store(b); ctx = context(s)
    p = {"source": Path(ctx["images"][0]), "recipe": Path(b.plan["recipe"]["path"]),
         "published": Path(b.published["path"]), "preparation": Path(b.method["region_preparation"]["path"])}[dependency]
    p.write_bytes(b"changed")
    assert s.lookup(**ctx)["status"] == "unavailable"


def test_top_level_file_changes_preserve_snapshot_and_returned_copies_are_isolated(adjacent):
    b = adjacent; s = store(b); ctx = context(s); before = s.lookup(**ctx)
    Path(b.raw_binding["path"]).write_bytes(b"changed")
    Path(b.plan_binding["path"]).write_bytes(b"changed")
    assert s.lookup(**ctx) == before
    changed = s.lookup(**ctx); changed["observation"]["previous_evidence"] = "edited"
    assert s.lookup(**ctx) == before


def test_request_not_attempted_remains_unavailable(adjacent):
    b = adjacent; b.raw["rows"] = []; b.raw["http_model_requests_attempted"] = 0
    b.raw["unattempted_cases"] = [b.case["case_id"]]
    s = store(b)
    assert s.lookup(**context(s))["status"] == "unavailable"


@pytest.mark.parametrize("state,count,allowed", [("unavailable", 0, True), ("completed", 0, False),
                                                ("unavailable", 2, False), ("unavailable", True, False)])
def test_row_preflight_failure_preserves_raw_without_inventing_http(adjacent, state, count, allowed):
    b = adjacent; row = b.raw["rows"][0]
    row["transport_status"] = state
    if state == "unavailable":
        row.update(final_content=None, finish_reason=None, reasoning_characters=0)
        row.pop("observation", None)
    b.raw["http_model_requests_attempted"] = count
    if allowed:
        s = store(b); result = s.lookup(**context(s))
        assert result["status"] == "unavailable" and result["raw_observation"]["final_content"] is None
    else:
        with pytest.raises(ValueError): store(b)
