"""Experimental offline paired replay; no inference or admission authority."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from scripts import observe_pairwise_cue as cue_runner
from scripts import observe_paired_shape as shape_runner
from scripts import pairwise_cue_observations as cue
from scripts import paired_shape_observations as shape
from scripts import paired_shape_preflight as checks

VERSION = "retained-paired-visual-diagnostic-1"
MAX_REPORT_BYTES = 4 * 1024 * 1024
MAX_CONTENT_CHARACTERS = 65536
ROLES = {"cue": ("previous", "current"), "shape": ("reference", "candidate")}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def rooted(binding, root):
    path = checks.binding_path(binding, root)
    if path == root or not path.is_relative_to(root):
        raise ValueError("Metadata/image binding escapes replay root")
    return path


def rooted_image(binding, root):
    path = rooted(binding, root)
    # The retained reconstruction/payload helpers read image paths directly.
    # Reject relative descriptors instead of letting root and CWD disagree.
    if not Path(binding["path"]).is_absolute():
        raise ValueError("Replay image descriptors must be absolute")
    return path


def checked_json(binding, root):
    path = rooted(binding, root)
    with path.open("rb") as stream:
        data = stream.read(MAX_REPORT_BYTES + 1)
    if len(data) > MAX_REPORT_BYTES or digest(data) != binding["sha256"]:
        raise ValueError("Oversized or changed replay metadata")
    def unique(pairs):
        if len(dict(pairs)) != len(pairs):
            raise ValueError("Duplicate replay field")
        return dict(pairs)
    def invalid_constant(value):
        raise ValueError("Nonfinite replay JSON")
    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid_constant)


def check_code(binding, module_path, root):
    # Only the actual imported implementation may be read outside a fixture root.
    if checks.binding_path(binding, root) != Path(module_path).resolve():
        raise ValueError("Different replay dependency path")
    checks.checked_bytes(binding, root)


def preflight(plan, kind, root):
    if kind == "cue":
        method = checked_json(plan["design"], root)
    elif kind == "shape" and plan.get("protocol") == "paired-major-shape-probe-plan-2":
        method = plan
        modules = (shape_runner.__file__, checks.__file__, shape.__file__)
        bindings = plan.get("implementation")
        if not isinstance(bindings, list) or len(bindings) != len(modules):
            raise ValueError("Missing shape code bindings")
        for binding, module in zip(bindings, modules):
            check_code(binding, module, root)
    else:
        raise ValueError("Only current cue or neutral source-bound shape replay")
    checked_json(method["assets_manifest"], root)
    preparation = checked_json(method["region_preparation"], root)
    check_code(preparation["helper"], checks.regions.__file__, root)
    manifest = checked_json(method["artifact_manifest" if kind == "cue" else "region_manifest"], root)
    for item in preparation["preparation"]["regions"]:
        rooted_image(item["source"], root)
    for row in manifest["regions"]:
        rooted_image(row["source"], root); rooted_image(row["crop"], root)
    for case in method["cases"]:
        for role in ROLES[kind]:
            rooted_image(case[role], root)
    if kind == "cue":
        checked_json(method["source_preparation"], root)
        cue_runner.preflight_plan(plan, root)
    else:
        evidence = checked_json(method["evidence_provenance"], root)
        checked_json(evidence["source_preparation"], root)
        shape_runner.preflight_plan(plan, root)
    return method, {r["id"]: r for r in manifest["regions"]}


def base(status="unavailable", reason="no_recorded_pair"):
    return {"version": VERSION, "status": status, "verdict": status, "available": status == "uncertain",
            "reason": reason, "availability_scope": "recorded_output_only", "identity_score": None,
            "state_score": None, "progression_score": None, "admission_allowed": False, "automatic_rejection": False,
            "physical_identity_established": False, "physical_temperature_measured": False, "pixel_truth_verified": False,
            "model_requests": 0, "generation_requests": 0}


def output_row(row, kind, identical):
    raw = {"final_content": copy.deepcopy(row.get("final_content")),
           "recorded_transport_status": row.get("transport_status"), "finish_reason": row.get("finish_reason"),
           "reasoning_characters": row.get("reasoning_characters")}
    result = {**base(reason="recorded_output_unavailable"), "raw_observation": raw}
    content, reasoning = row.get("final_content"), row.get("reasoning_characters")
    if (not isinstance(content, str) or len(content) > MAX_CONTENT_CHARACTERS
            or type(reasoning) is not int or reasoning < 0):
        return result
    observer = cue if kind == "cue" else shape
    reply = {"choices": [{"finish_reason": row.get("finish_reason"), "message": {
        "content": content, "reasoning_content": "recorded reasoning" if reasoning else ""}}]}
    try:
        value = observer.parse_response(reply)
        diagnostic = cue.diagnostic(value, identical_inputs=identical) if kind == "cue" else shape.diagnostic(value)
        inconsistent = diagnostic.get("input_consistency_violation", False)
        if kind == "shape" and identical and value["major_shape_change"] == "observed":
            inconsistent = True
        if inconsistent:
            result.update(reason="input_consistency_violation", input_consistency_violation=True)
            return result
        if row.get("transport_status") != "completed" or value != row.get("observation"):
            return result
    except (ValueError, KeyError, TypeError):
        return result
    result.update(base("uncertain", "recorded_paired_output_only"), observation=value,
                  input_consistency_violation=False)
    if kind == "cue":
        result["visible_transition"] = diagnostic["visible_transition"]
    else:
        result["hints"] = diagnostic["hints"]
    return result


class RetainedPairedObservations:
    """Snapshot a cohort; recheck native sources on each ordered lookup.

    Report/plan file mutations cannot change the captured snapshot. Source,
    preparation, dependency or context changes invalidate lookup availability.
    No recorded row paths, summaries, verdicts or labels become authority.
    """
    @classmethod
    def from_files(cls, raw_binding, plan_binding, *, kind, root):
        root = Path(root).resolve()
        try:
            if kind not in ROLES:
                raise ValueError("Unknown pair kind")
            raw = checked_json(raw_binding, root); plan = checked_json(plan_binding, root)
            method, regions = preflight(plan, kind, root)
            observer = cue if kind == "cue" else shape
            if (raw.get("protocol") != observer.VERSION or raw.get("plan_sha256") != plan_binding["sha256"]
                    or raw.get("subject") != method["subject"]):
                raise ValueError("Report protocol/plan/subject mismatch")
            if kind == "cue":
                if (raw.get("cue_query") != method["cue_query"] or raw.get("implementation") != plan["implementation"]
                        or raw.get("design") != plan["design"]):
                    raise ValueError("Report cue/code/design mismatch")
            else:
                for field, module in (("harness_sha256", shape_runner.__file__), ("observer_sha256", shape.__file__),
                                      ("input_checks_sha256", checks.__file__)):
                    if raw.get(field) != digest(Path(module).read_bytes()):
                        raise ValueError("Report shape implementation mismatch")
            declared_head = plan.get("execution_base_head")
            if declared_head is not None and raw.get("execution_head") != declared_head:
                raise ValueError("Report execution base mismatch")
            assets = checked_json(method["assets_manifest"], root)
            model = shape_runner.select_model(assets, raw["model"]["repo"])
            if model != raw["model"]:
                raise ValueError("Reported model differs from pinned assets")
            rows, cases = raw.get("rows"), method["cases"]
            if not isinstance(rows, list) or len(rows) > min(128, len(cases)):
                raise ValueError("Invalid retained cohort budget")
            store = cls(); store._root = root; store._kind = kind
            store._plan = copy.deepcopy(plan); store._method = copy.deepcopy(method); store._regions = copy.deepcopy(regions)
            store._provenance = {"protocol": observer.VERSION, "source_report_sha256": raw_binding["sha256"],
                                 "source_plan_sha256": plan_binding["sha256"], "reported_model_repo": model["repo"],
                                 "reported_model_fingerprint": digest(checks.canonical(model).encode()),
                                 "preparation_sha256": method["region_preparation"]["sha256"],
                                 "manifest_sha256": method["artifact_manifest" if kind == "cue" else "region_manifest"]["sha256"]}
            store._rows, store._contexts = {}, []
            context_keys = set()
            for case in cases:
                ids = [case[r + "_region_id"] for r in ROLES[kind]]
                key = store._key(ids)
                if key in context_keys:
                    raise ValueError("Duplicate ordered pair context")
                context_keys.add(key)
                store._contexts.append({"case_id": case["case_id"], "region_ids": ids,
                                        "images": [regions[i]["source"]["path"] for i in ids],
                                        "subject": method["subject"], "cue_query": method.get("cue_query")})
            for index, row in enumerate(rows):
                case = cases[index]
                if (not isinstance(row, dict) or row.get("case_id") != case["case_id"]
                        or row.get("transport_status") not in {"completed", "unavailable"} or row.get("request_attempted") is not True
                        or row.get("inputs") != [{"role": r, "sha256": case[r]["sha256"]} for r in ROLES[kind]]):
                    raise ValueError("Recorded cohort order/input provenance mismatch")
                body = observer.payload(*(case[r] for r in ROLES[kind]), method["subject"],
                                        *([method["cue_query"]] if kind == "cue" else []))
                if row.get("request_sha256") != digest(checks.canonical(body).encode()):
                    raise ValueError("Recorded request fingerprint mismatch")
                identical = case[ROLES[kind][0]]["sha256"] == case[ROLES[kind][1]]["sha256"]
                output = output_row(row, kind, identical)
                if output["status"] == "unavailable" and index != len(rows) - 1:
                    raise ValueError("Recorded cohort continues after invalid/unavailable output")
                key = store._key([case[r + "_region_id"] for r in ROLES[kind]])
                store._rows[key] = output
            return store
        except (OSError, KeyError, TypeError, AttributeError) as exc:
            raise ValueError("Invalid paired replay provenance") from exc

    def _key(self, ids):
        inputs = [{"role": role, "region_id": i, "source_sha256": self._regions[i]["source"]["sha256"],
                   "prepared_sha256": self._regions[i]["crop"]["sha256"], "source_size": self._regions[i]["source"]["size"],
                   "prepared_size": self._regions[i]["crop"]["size"], "effective_box": self._regions[i]["effective_box"],
                   "margin_pixels": self._regions[i]["margin_pixels"]} for role, i in zip(ROLES[self._kind], ids)]
        return digest(checks.canonical({"version": VERSION, **self._provenance, "inputs": inputs,
                                       "subject": self._method["subject"], "cue_query": self._method.get("cue_query")}).encode())

    def contexts(self):
        return copy.deepcopy(self._contexts)

    def lookup(self, images, *, region_ids, subject, cue_query=None):
        if subject != self._method["subject"] or cue_query != self._method.get("cue_query"):
            return base(reason="context_mismatch")
        if (not isinstance(images, (tuple, list)) or len(images) != 2 or not isinstance(region_ids, (tuple, list))
                or len(region_ids) != 2 or any(not isinstance(i, str) or i not in self._regions for i in region_ids)):
            return base(reason="invalid_lookup_context")
        try:
            preflight(self._plan, self._kind, self._root)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            return base(reason="source_or_preparation_changed")
        try:
            for path, region_id in zip(images, region_ids):
                current = Path(path).resolve()
                if not current.is_relative_to(self._root) or digest(current.read_bytes()) != self._regions[region_id]["source"]["sha256"]:
                    return base(reason="lookup_source_mismatch")
            key = self._key(region_ids)
        except (OSError, ValueError, KeyError, TypeError):
            return base(reason="lookup_source_unavailable")
        if key not in self._rows:
            return base()
        result = {**copy.deepcopy(self._rows[key]), **copy.deepcopy(self._provenance), "snapshot_key": key,
                  "ordered_regions": copy.deepcopy(list(region_ids)), "subject": subject, "cue_query": cue_query}
        result["inputs"] = [{"role": r, "source_sha256": self._regions[i]["source"]["sha256"],
                            "prepared_sha256": self._regions[i]["crop"]["sha256"],
                            "coverage_relation": self._regions[i]["coverage_relation"],
                            "semantic_coverage_review": "pending"} for r, i in zip(ROLES[self._kind], region_ids)]
        return result


def export_replay(design_binding, output, *, root):
    root = Path(root).resolve(); output = Path(output).resolve()
    if output == root or not output.is_relative_to(root):
        raise ValueError("Replay export escapes workspace")
    if output.exists():
        raise FileExistsError("Preserve existing replay export")
    design = checked_json(design_binding, root)
    cohorts = design.get("initial_cohorts")
    if (design.get("protocol") != "retained-paired-replay-design-1" or not isinstance(cohorts, list)
            or len(cohorts) != 4 or any(design.get("policy", {}).get(k) != 0 for k in
                                       ("model_requests", "generation_requests", "downloads", "service_control"))):
        raise ValueError("Unknown/four-cohort offline design required")
    identities, results = set(), []
    for cohort in cohorts:
        identity = (cohort["kind"], cohort["raw"]["sha256"])
        if identity in identities:
            raise ValueError("Duplicate retained cohort")
        identities.add(identity)
        store = RetainedPairedObservations.from_files(cohort["raw"], cohort["plan"], kind=cohort["kind"], root=root)
        rows = [{"case_id": context["case_id"], "result": store.lookup(**{k: v for k, v in context.items() if k != "case_id"})}
                for context in store.contexts()]
        results.append({"kind": cohort["kind"], "raw_sha256": cohort["raw"]["sha256"], "rows": rows})
    report = {"protocol": VERSION, "design_sha256": design_binding["sha256"], "adapter_sha256": digest(Path(__file__).read_bytes()),
              "model_requests": 0, "generation_requests": 0, "downloads": 0, "service_changes": 0,
              "admission_allowed": False, "human_gold_added": False, "cohorts": results}
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2); stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--design", required=True); parser.add_argument("--design-sha256", required=True)
    parser.add_argument("--output", required=True); args = parser.parse_args()
    report = export_replay({"path": args.design, "sha256": args.design_sha256}, args.output,
                           root=Path(__file__).resolve().parents[1])
    print(json.dumps({"cohorts": len(report["cohorts"]), "model_requests": 0, "generation_requests": 0}), flush=True)


if __name__ == "__main__":
    main()
