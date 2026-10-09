"""Explicitly injected paired replay diagnostics; no scene decision authority."""
import copy
import hashlib
import json
from pathlib import Path
import re


VERSION = "paired-visual-diagnostic-bridge-1"
REPLAY_VERSION = "retained-paired-visual-diagnostic-1"
ROLES = {"shape": ("reference", "candidate"), "cue": ("previous", "current")}
PROTOCOLS = {"shape": "paired-major-shape-observations-1", "cue": "pairwise-visible-cue-observations-1"}
PUBLIC_FIELDS = {"version", "status", "verdict", "available", "reason", "availability_scope", "identity_score", "state_score",
                 "progression_score", "admission_allowed", "automatic_rejection", "physical_identity_established",
                 "physical_temperature_measured", "pixel_truth_verified", "model_requests", "generation_requests",
                 "raw_observation", "observation", "input_consistency_violation", "visible_transition", "hints", "protocol",
                 "source_report_sha256", "source_plan_sha256", "reported_model_repo", "reported_model_fingerprint",
                 "preparation_sha256", "manifest_sha256", "snapshot_key", "ordered_regions", "subject", "cue_query", "inputs"}


def _base(reason, status="unavailable"):
    return {"version": VERSION, "status": status, "verdict": status, "available": status == "uncertain", "reason": reason,
            "availability_scope": "recorded_output_only", "identity_score": None, "state_score": None, "progression_score": None,
            "admission_allowed": False, "automatic_rejection": False, "physical_identity_established": False,
            "physical_temperature_measured": False, "pixel_truth_verified": False, "model_requests": 0, "generation_requests": 0}


def _digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def selected_reference_path(inputs, info):
    """Bind the first input actually sent, without guessing a basename's folder."""
    if not isinstance(inputs, list) or not inputs or not isinstance(info, dict):
        return None
    first = inputs[0]
    pack = info.get("reference_pack_all", info.get("reference_pack", []))
    if not isinstance(pack, list):
        return None
    matches = [row for row in pack if isinstance(row, dict) and row.get("comfyui_input") == first]
    if len(matches) > 1:
        return None
    path = matches[0].get("local_path") if matches else None
    if not path and info.get("comfyui_input") == first:
        path = info.get("local_path")
    return path if isinstance(path, str) and Path(path).is_absolute() else None


def _public_output(value, kind, context, source_hashes):
    if (not isinstance(value, dict) or value.get("version") != REPLAY_VERSION
            or value.get("status") not in {"uncertain", "unavailable"} or value.get("verdict") != value["status"]
            or value.get("available") is not (value["status"] == "uncertain")
            or value.get("availability_scope") != "recorded_output_only"
            or any(k not in value or value[k] is not None for k in ("identity_score", "state_score", "progression_score"))
            or any(value.get(k) is not False for k in ("admission_allowed", "automatic_rejection", "physical_identity_established",
                                                       "physical_temperature_measured", "pixel_truth_verified"))
            or any(type(value.get(k)) is not int or value[k] != 0 for k in ("model_requests", "generation_requests"))):
        raise ValueError("Invalid paired diagnostic envelope")
    if value["status"] == "uncertain" or "inputs" in value:
        inputs = value.get("inputs")
        if (value.get("protocol") != PROTOCOLS[kind] or value.get("subject") != context["subject"]
                or value.get("cue_query") != context.get("cue_query") or value.get("ordered_regions") != context["region_ids"]
                or not isinstance(inputs, list) or len(inputs) != 2
                or any(not isinstance(row, dict) or row.get("role") != role or row.get("source_sha256") != source_hash
                       or not _sha(row.get("prepared_sha256")) for row, role, source_hash in zip(inputs, ROLES[kind], source_hashes))
                or any(not _sha(value.get(k)) for k in ("source_report_sha256", "source_plan_sha256", "snapshot_key",
                                                        "reported_model_fingerprint", "preparation_sha256", "manifest_sha256"))):
            raise ValueError("Paired diagnostic input context mismatch")
    if value["status"] == "uncertain":
        raw = value.get("raw_observation")
        if (not isinstance(value.get("observation"), dict) or not isinstance(raw, dict)
                or not isinstance(raw.get("final_content"), str) or not raw["final_content"].strip()
                or len(raw["final_content"]) > 65536
                or raw.get("recorded_transport_status") != "completed" or raw.get("finish_reason") != "stop"
                or type(raw.get("reasoning_characters")) is not int or raw["reasoning_characters"] != 0):
            raise ValueError("Missing/incomplete retained paired output")
    public = {k: v for k, v in value.items() if k in PUBLIC_FIELDS}
    encoded = json.dumps(public, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode("utf-8")) > 1024 * 1024:
        raise ValueError("Oversized paired diagnostic")
    return json.loads(encoded)


def _invalidate(result, reason):
    result.setdefault("before_qa_observations", copy.deepcopy(result["observations"]))
    result["observations"] = {kind: _base(reason) for kind in result["observations"]}
    result.update(_base(reason))
    return result


def diagnose(candidate, *, reference, previous, subject, contexts, observers):
    """Use actual pipeline inputs with an explicitly supplied retained reader.

    Callbacks are trusted local code supplied by the experimental caller, not
    configuration or report paths. This module never discovers/loads a reader.
    """
    result = {**_base("no_requested_pairs"), "candidate_stage": "before_semantic_qa",
              "applicability_stage": "before_semantic_qa", "observations": {}, "input_sha256s": {}}
    if not isinstance(contexts, dict) or not contexts:
        return result
    if (set(contexts) - ROLES.keys() or not isinstance(subject, str) or not subject.strip()
            or not isinstance(observers, dict)):
        return {**result, **_base("invalid_pair_context")}
    paths = {"reference": reference, "previous": previous, "candidate": candidate}
    for kind, context in contexts.items():
        first = ROLES[kind][0]
        fields = {"region_ids", "subject"} | ({"cue_query"} if kind == "cue" else set())
        if (not isinstance(context, dict) or set(context) != fields or context.get("subject") != subject
                or not isinstance(context.get("region_ids"), list) or len(context["region_ids"]) != 2
                or any(not isinstance(i, str) or not i for i in context["region_ids"])
                or (kind == "cue" and (not isinstance(context["cue_query"], str) or not context["cue_query"].strip()))):
            result["observations"][kind] = _base("invalid_pair_context")
            continue
        observer = observers.get(kind)
        if not callable(observer):
            result["observations"][kind] = _base("missing_pair_observer")
            continue
        if not paths[first] or not candidate:
            result["observations"][kind] = _base("missing_pair_input")
            continue
        try:
            images = [Path(paths[first]).resolve(), Path(candidate).resolve()]
            before = [_digest(p) for p in images]
            for name, value in zip((first, "candidate"), before):
                result["input_sha256s"].setdefault(name, value)
            value = observer(images, region_ids=copy.deepcopy(context["region_ids"]), subject=subject,
                             cue_query=context.get("cue_query"))
            if before != [_digest(p) for p in images]:
                result["observations"][kind] = _base("pair_inputs_changed_during_observation")
                continue
            result["observations"][kind] = _public_output(value, kind, context, before)
        except Exception:
            # Reader bugs/invalid data remain diagnostic; user interrupts still propagate.
            result["observations"][kind] = _base("paired_observer_unavailable")
    try:
        if any(_digest(paths[name]) != value for name, value in result["input_sha256s"].items()):
            return _invalidate(result, "pair_inputs_changed_during_observation")
    except (OSError, ValueError, TypeError):
        return _invalidate(result, "pair_input_unavailable")
    if any(row["status"] == "uncertain" for row in result["observations"].values()):
        result.update(_base("paired_diagnostic_only", "uncertain"))
    elif result["observations"]:
        result.update(_base("paired_diagnostic_unavailable"))
    return result


def finalize(diagnostic, candidate, *, reference, previous):
    """Check final applicability without another reader/model invocation."""
    result = copy.deepcopy(diagnostic)
    result["applicability_stage"] = "after_image_postprocessing"
    paths = {"reference": reference, "previous": previous, "candidate": candidate}
    try:
        if not candidate:
            return {**_invalidate(result, "no_final_candidate"), "final_applicability": "no_final_candidate"}
        if any(_digest(paths[name]) != value for name, value in result["input_sha256s"].items()):
            return {**_invalidate(result, "pair_inputs_changed_after_observation"), "final_applicability": "input_bytes_changed"}
        result["final_applicability"] = "same_input_bytes" if result["input_sha256s"] else "no_observed_inputs"
    except (OSError, ValueError, TypeError):
        return {**_invalidate(result, "pair_input_unavailable"), "final_applicability": "input_unavailable"}
    return result
