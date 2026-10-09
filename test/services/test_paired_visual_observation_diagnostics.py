"""CPU bridge controls against the source-bound synthetic replay fixtures."""
import copy
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.services import paired_visual_observation_diagnostics as bridge
from test.test_retained_paired_observations import bundle, load  # noqa: F401
from test.test_retained_paired_observations import cue_plan, shape_plan, prepared  # noqa: F401


@pytest.fixture
def paired(bundle):
    store = load(bundle)
    context = store.contexts()[2]
    caller_context = {k: copy.deepcopy(context[k]) for k in ("region_ids", "subject")}
    if bundle.kind == "cue": caller_context["cue_query"] = context["cue_query"]
    source = Path(context["images"][0])
    observer = Mock(wraps=store.lookup)
    return {"candidate": Path(context["images"][1]), "reference": source if bundle.kind == "shape" else None,
            "previous": source if bundle.kind == "cue" else None, "subject": context["subject"],
            "contexts": {bundle.kind: caller_context}, "observers": {bundle.kind: observer}}, observer, store, bundle.kind


def finish(result, args, candidate=None):
    return bridge.finalize(result, args["candidate"] if candidate is None else candidate,
                           reference=args["reference"], previous=args["previous"])


def assert_no_authority(result):
    assert result["status"] in {"uncertain", "unavailable"}
    assert result["verdict"] == result["status"]
    assert all(result[k] is None for k in ("identity_score", "state_score", "progression_score"))
    assert all(result[k] is False for k in ("admission_allowed", "automatic_rejection", "physical_identity_established", "pixel_truth_verified"))
    assert result["model_requests"] == result["generation_requests"] == 0


def test_original_pair_replayed_with_pipeline_roles_and_stage(paired):
    args, observer, store, kind = paired
    result = bridge.diagnose(**args)
    assert_no_authority(result)
    assert result["status"] == "uncertain" and result["candidate_stage"] == "before_semantic_qa"
    recorded = store.lookup(**{k: v for k, v in store.contexts()[2].items() if k != "case_id"})
    assert result["observations"][kind]["raw_observation"] == recorded["raw_observation"]
    assert result["observations"][kind]["snapshot_key"] == recorded["snapshot_key"]
    assert observer.call_count == 1
    assert list(observer.call_args.args[0]) == [args["reference"] or args["previous"], args["candidate"]]
    assert observer.call_args.kwargs["subject"] == args["subject"]


@pytest.mark.parametrize("fault", ["missing_context", "empty_context", "unknown_kind", "missing_subject", "other_subject", "bad_regions", "wrong_region", "wrong_query", "missing_observer", "invalid_observer", "missing_role"])
def test_missing_or_wrong_context_never_becomes_evidence(paired, fault):
    args, observer, store, kind = paired
    if fault == "missing_context": args["contexts"] = None
    elif fault == "empty_context": args["contexts"] = {}
    elif fault == "unknown_kind": args["contexts"] = {"unknown": args["contexts"][kind]}
    elif fault == "missing_subject": args["subject"] = ""
    elif fault == "other_subject": args["subject"] = "different subject"
    elif fault == "bad_regions": args["contexts"][kind]["region_ids"] = []
    elif fault == "wrong_region": args["contexts"][kind]["region_ids"] = ["unknown", "unknown"]
    elif fault == "wrong_query": args["contexts"][kind]["cue_query"] = "different cue"
    elif fault == "missing_observer": args["observers"] = {}
    elif fault == "invalid_observer": args["observers"] = {kind: object()}
    else: args["reference" if kind == "shape" else "previous"] = None
    result = bridge.diagnose(**args)
    assert_no_authority(result)
    assert result["status"] == "unavailable"
    if fault in {"missing_context", "empty_context", "unknown_kind", "missing_subject", "other_subject", "bad_regions", "missing_observer", "invalid_observer", "missing_role"}:
        observer.assert_not_called()


@pytest.mark.parametrize("fault", ["pass", "admission", "rejection", "score", "requests", "generation", "budget_bool", "available", "version", "source", "roles", "protocol", "subject", "query", "object", "nonfinite", "exception", "missing_raw", "missing_observation", "raw_finish", "raw_transport", "raw_reasoning", "oversized_raw", "empty_raw", "blank_raw"])
def test_bad_provider_envelope_cannot_cross_bridge(paired, fault):
    args, observer, store, kind = paired
    output = store.lookup(**{k: v for k, v in store.contexts()[2].items() if k != "case_id"})
    if fault == "pass": output["verdict"] = "pass"
    elif fault == "admission": output["admission_allowed"] = True
    elif fault == "rejection": output["automatic_rejection"] = True
    elif fault == "score": output["identity_score"] = .99
    elif fault == "requests": output["model_requests"] = 1
    elif fault == "generation": output["generation_requests"] = 1
    elif fault == "budget_bool": output["model_requests"] = False
    elif fault == "available": output["available"] = False
    elif fault == "version": output["version"] = "unknown"
    elif fault == "source": output["inputs"][1]["source_sha256"] = "f" * 64
    elif fault == "roles": output["inputs"] = list(reversed(output["inputs"]))
    elif fault == "protocol": output["protocol"] = "unknown"
    elif fault == "subject": output["subject"] = "different subject"
    elif fault == "query": output["cue_query"] = "different cue"
    elif fault == "object": output["observation"] = object()
    elif fault == "nonfinite": output["observation"] = {"value": float('nan')}
    elif fault == "missing_raw": del output["raw_observation"]
    elif fault == "missing_observation": del output["observation"]
    elif fault == "raw_finish": output["raw_observation"]["finish_reason"] = "length"
    elif fault == "raw_transport": output["raw_observation"]["recorded_transport_status"] = "unavailable"
    elif fault == "raw_reasoning": output["raw_observation"]["reasoning_characters"] = 1
    elif fault == "oversized_raw": output["raw_observation"]["final_content"] = "x" * 65537
    elif fault == "empty_raw": output["raw_observation"]["final_content"] = ""
    elif fault == "blank_raw": output["raw_observation"]["final_content"] = "   \n\t"
    else: observer.side_effect = RuntimeError("provider unavailable")
    if fault != "exception": observer.side_effect = None; observer.return_value = output
    result = bridge.diagnose(**args)
    assert_no_authority(result)
    assert result["status"] == "unavailable" and not result["observations"][kind]["available"]


def test_result_is_deep_copied_and_unknown_provider_fields_not_copied(paired):
    args, observer, store, kind = paired
    output = store.lookup(**{k: v for k, v in store.contexts()[2].items() if k != "case_id"})
    output["private_settings"] = "DO_NOT_COPY"
    observer.side_effect = None; observer.return_value = output
    result = bridge.diagnose(**args)
    assert "private_settings" not in result["observations"][kind]
    result["observations"][kind]["raw_observation"]["final_content"] = "caller mutation"
    assert output["raw_observation"]["final_content"] != "caller mutation"


@pytest.mark.parametrize("when,role", [("before", "candidate"), ("before", "first"), ("during", "candidate"), ("during", "first")])
def test_changed_source_unavailable_without_scene_decision(paired, when, role):
    args, observer, store, kind = paired
    path = args["candidate"] if role == "candidate" else args["reference"] or args["previous"]
    if when == "before": path.write_bytes(b"different pixels")
    else:
        original = store.lookup(**{k: v for k, v in store.contexts()[2].items() if k != "case_id"})
        def change(*a, **kw): path.write_bytes(b"different pixels"); return original
        observer.side_effect = change
    result = bridge.diagnose(**args)
    assert_no_authority(result)
    assert result["status"] == "unavailable"


@pytest.mark.parametrize("target", ["candidate", "first", "missing_final", "same_bytes_copy"])
def test_final_image_applicability_preserves_before_qa_snapshot(paired, tmp_path, target):
    args, observer, store, kind = paired
    original = bridge.diagnose(**args)
    snapshot = copy.deepcopy(original)
    candidate = args["candidate"]
    if target == "candidate": candidate.write_bytes(b"graded/replaced pixels")
    elif target == "first": (args["reference"] or args["previous"]).write_bytes(b"changed input")
    elif target == "missing_final": candidate = None
    else:
        candidate = tmp_path / "same-bytes-copy.png"; candidate.write_bytes(args["candidate"].read_bytes())
    result = finish(original, args, candidate) if candidate is not None else bridge.finalize(original, None, reference=args["reference"], previous=args["previous"])
    assert_no_authority(result)
    assert original == snapshot and observer.call_count == 1
    assert result["status"] == ("uncertain" if target == "same_bytes_copy" else "unavailable")
    if target != "same_bytes_copy":
        assert result["before_qa_observations"][kind]["raw_observation"] == snapshot["observations"][kind]["raw_observation"]
        assert result["observations"][kind]["status"] == "unavailable"


def test_unchanged_final_image_stays_diagnostic_without_another_lookup(paired):
    args, observer, store, kind = paired
    result = finish(bridge.diagnose(**args), args)
    assert_no_authority(result)
    assert result["status"] == "uncertain" and result["final_applicability"] == "same_input_bytes"
    assert result["candidate_stage"] == "before_semantic_qa" and result["applicability_stage"] == "after_image_postprocessing"
    assert observer.call_count == 1


def test_requested_unavailable_pair_is_not_reported_as_unrequested(paired):
    args, observer, store, kind = paired
    args["contexts"][kind]["region_ids"] = ["unknown", "unknown"]
    result = bridge.diagnose(**args)
    assert result["status"] == "unavailable" and observer.call_count == 1
    assert result["reason"] == "paired_diagnostic_unavailable"
