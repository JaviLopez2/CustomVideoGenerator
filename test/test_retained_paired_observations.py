"""Source-bound offline pair replay, synthetic CPU fixtures, no model calls."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image

from scripts import retained_paired_observations as replay
from scripts import observe_pairwise_cue as cue_runner
from scripts import observe_paired_shape as shape_runner
from scripts import pairwise_cue_observations as cue
from scripts import paired_shape_observations as shape
from scripts import paired_shape_preflight as checks
from scripts import prepare_visual_regions as regions
from test.test_pairwise_cue_runner import plan as cue_plan  # noqa: F401
from test.test_paired_shape_preflight import prepared, plan as shape_plan  # noqa: F401


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path), "sha256": sha(path)}


def sync(b):
    if b.kind == "cue":
        b.plan["design"] = write_json(Path(b.plan["design"]["path"]), b.method)
        b.raw["design"] = copy.deepcopy(b.plan["design"])
    b.plan_binding = write_json(b.root / "replay-plan.json", b.plan)
    b.raw["plan_sha256"] = b.plan_binding["sha256"]
    b.raw_binding = write_json(b.root / "replay-report.json", b.raw)


def load(b):
    return replay.RetainedPairedObservations.from_files(b.raw_binding, b.plan_binding, kind=b.kind, root=b.root)


def args_for(b, index=0):
    case = b.method["cases"][index]
    ids = [case[role + "_region_id"] for role in b.roles]
    return {"images": [Path(b.regions[i]["source"]["path"]) for i in ids],
            "region_ids": ids, "subject": b.method["subject"],
            "cue_query": b.method.get("cue_query")}


@pytest.fixture(params=["cue", "shape"])
def bundle(request, tmp_path):
    kind = request.param
    plan = copy.deepcopy(request.getfixturevalue(kind + "_plan"))
    method = json.loads(Path(plan["design"]["path"]).read_text(encoding="utf-8")) if kind == "cue" else plan
    if kind == "cue":
        # Three sources give four distinct ordered contexts, rather than hiding
        # two repeated fixture pairs behind different case names.
        prep = json.loads(Path(method["region_preparation"]["path"]).read_text(encoding="utf-8"))
        path = tmp_path / "source2.png"; Image.new("RGB", (8, 12), "green").save(path)
        prep["preparation"]["regions"].append({"id": "frame2", "source": {"path": str(path), "sha256": sha(path), "size": [8, 12]},
                                                "box": [0, 0, 8, 12], "required_box": [0, 0, 8, 12]})
        manifest = regions.prepare(prep["preparation"], tmp_path / "replay-frames", workspace_root=tmp_path)
        method["region_preparation"] = write_json(tmp_path / "replay-preparation.json", prep)
        method["artifact_manifest"] = {"path": str(tmp_path / "replay-frames/manifest.json"), "sha256": sha(tmp_path / "replay-frames/manifest.json")}
        method["source_preparation"] = write_json(tmp_path / "replay-preparation-result.json", {"plan": method["region_preparation"], "manifest": method["artifact_manifest"]})
        method["cases"][2]["current_region_id"] = "frame2"
        method["cases"][3]["previous_region_id"] = "frame2"; method["cases"][3]["current_region_id"] = "frame1"
        by_id = {r["id"]: r for r in manifest["regions"]}
        for case in method["cases"]:
            for role in ("previous", "current"):
                case[role] = {k: by_id[case[role + "_region_id"]]["crop"][k] for k in ("path", "sha256", "size")}
    model = {"repo": "unsloth/Qwen3.5-9B-GGUF", "revision": "a" * 40,
             "files": [{"file": "model.gguf", "size": 1, "sha256": "b" * 64},
                       {"file": "projector.gguf", "size": 1, "sha256": "c" * 64}]}
    method["assets_manifest"] = write_json(tmp_path / "assets.json", {"models": [model]})
    roles = ("previous", "current") if kind == "cue" else ("reference", "candidate")
    obs = cue if kind == "cue" else shape
    if kind == "shape":
        plan["implementation"] = [{"path": str(Path(p).resolve()), "sha256": sha(p)} for p in
                                  (shape_runner.__file__, checks.__file__, shape.__file__)]
    raw = {"protocol": obs.VERSION, "execution_head": plan.get("execution_base_head", "a" * 40),
           "model": model, "subject": method["subject"], "rows": []}
    if kind == "cue":
        raw.update(implementation=copy.deepcopy(plan["implementation"]), design=copy.deepcopy(plan["design"]),
                   cue_query=method["cue_query"])
    else:
        raw.update(harness_sha256=sha(shape_runner.__file__), observer_sha256=sha(shape.__file__),
                   input_checks_sha256=sha(checks.__file__))
    for case in method["cases"]:
        if kind == "cue":
            value = {role + "_" + field: text for role in roles for field, text in
                     (("subject_presence", "present"), ("cue_visibility", "not_observed"), ("evidence", "Visible area checked"))}
            body = obs.payload(*(case[r] for r in roles), method["subject"], method["cue_query"])
        else:
            value = {"reference_subject_presence": "present", "candidate_subject_presence": "present",
                     "major_shape_change": "not_observed", "difference_evidence": "No reported major change"}
            body = obs.payload(*(case[r] for r in roles), method["subject"])
        raw["rows"].append({"case_id": case["case_id"], "transport_status": "completed", "request_attempted": True,
                            "request_sha256": hashlib.sha256(checks.canonical(body).encode()).hexdigest(),
                            "inputs": [{"role": r, "sha256": case[r]["sha256"]} for r in roles],
                            "final_content": json.dumps(value), "observation": value,
                            "finish_reason": "stop", "reasoning_characters": 0,
                            "diagnostic": {"verdict": "pass", "admission_allowed": True},
                            "path": "NEVER_FOLLOW_THIS_PATH"})
    manifest_key = "artifact_manifest" if kind == "cue" else "region_manifest"
    manifest = json.loads(Path(method[manifest_key]["path"]).read_text(encoding="utf-8"))
    b = SimpleNamespace(kind=kind, root=tmp_path, plan=plan, method=method, raw=raw, roles=roles,
                        regions={row["id"]: row for row in manifest["regions"]})
    sync(b)
    if kind == "cue":
        raw["design"] = copy.deepcopy(plan["design"])
        sync(b)
    return b


def test_valid_pair_is_raw_uncertain_diagnostic_with_context(bundle):
    store = load(bundle)
    result = store.lookup(**args_for(bundle, 2))
    assert result["status"] == result["verdict"] == "uncertain" and result["available"]
    assert result["availability_scope"] == "recorded_output_only"
    assert result["raw_observation"]["final_content"] == bundle.raw["rows"][2]["final_content"]
    assert result["source_report_sha256"] == bundle.raw_binding["sha256"]
    assert result["source_plan_sha256"] == bundle.plan_binding["sha256"]
    assert all(result[k] is None for k in ("identity_score", "state_score", "progression_score"))
    assert not any(result[k] for k in ("admission_allowed", "automatic_rejection", "physical_identity_established", "pixel_truth_verified"))
    assert "NEVER_FOLLOW" not in json.dumps(result)


@pytest.mark.parametrize("fault", ["raw_sha", "plan_sha", "protocol", "model", "model_files", "reported_plan", "subject", "public_query", "order", "duplicate", "request_sha", "input_role", "input_sha", "too_many", "code"])
def test_bad_provenance_rejected_before_replay(bundle, fault):
    load(bundle)  # Confirm a valid fixture before mutation.
    raw = bundle.raw
    if fault == "raw_sha": bundle.raw_binding["sha256"] = "0" * 64
    elif fault == "plan_sha": bundle.plan_binding["sha256"] = "0" * 64
    else:
        if fault == "protocol": raw["protocol"] = "single-image-inventory"
        elif fault == "model": raw["model"]["repo"] = "unknown/model"
        elif fault == "model_files": raw["model"]["files"][0]["sha256"] = "d" * 64
        elif fault == "reported_plan": raw["plan_sha256"] = "0" * 64
        elif fault == "subject": raw["subject"] = "different target"
        elif fault == "public_query":
            if bundle.kind == "cue": raw["cue_query"] = "different cue"
            else: raw["subject"] = "different target"
        elif fault == "order": raw["rows"][0], raw["rows"][1] = raw["rows"][1], raw["rows"][0]
        elif fault == "duplicate": raw["rows"][1] = copy.deepcopy(raw["rows"][0])
        elif fault == "request_sha": raw["rows"][0]["request_sha256"] = "0" * 64
        elif fault == "input_role": raw["rows"][0]["inputs"][0]["role"] = "wrong-role"
        elif fault == "input_sha": raw["rows"][0]["inputs"][0]["sha256"] = "0" * 64
        elif fault == "too_many": raw["rows"].append(copy.deepcopy(raw["rows"][0]))
        elif bundle.kind == "cue": raw["implementation"]["observer"]["sha256"] = "0" * 64
        else: raw["harness_sha256"] = "0" * 64
        bundle.raw_binding = write_json(Path(bundle.raw_binding["path"]), raw)
    with pytest.raises(ValueError): load(bundle)


@pytest.mark.parametrize("fault", ["invalid_json", "duplicate_key", "truncated", "reasoning", "reasoning_bool", "extra_field", "tampered_observation", "presence_conflict", "recorded_unavailable", "self_contradiction"])
def test_invalid_output_is_preserved_unavailable_without_rescue(bundle, fault):
    row = bundle.raw["rows"][0]
    if fault == "invalid_json": row["final_content"] = "Not JSON, looks good"
    elif fault == "duplicate_key": row["final_content"] = '{"a":1,"a":2}'
    elif fault == "truncated": row["finish_reason"] = "length"
    elif fault == "reasoning": row["reasoning_characters"] = 3
    elif fault == "reasoning_bool": row["reasoning_characters"] = False
    elif fault == "extra_field": row["final_content"] = json.dumps({**row["observation"], "verdict": "pass"})
    elif fault == "tampered_observation": row["observation"] = {}
    elif fault == "recorded_unavailable": row["transport_status"] = "unavailable"
    else:
        value = copy.deepcopy(row["observation"])
        if fault == "presence_conflict": value[bundle.roles[0] + "_subject_presence"] = "uncertain"
        elif bundle.kind == "cue": value["current_cue_visibility"] = "observed"
        else: value["major_shape_change"] = "observed"
        row.update(observation=value, final_content=json.dumps(value))
    bundle.raw["rows"] = [row]  # Cohort stopped; no invented later rows.
    bundle.raw_binding = write_json(Path(bundle.raw_binding["path"]), bundle.raw)
    store = load(bundle)
    result = store.lookup(**args_for(bundle))
    assert result["status"] == "unavailable" and not result["available"]
    assert result["raw_observation"]["final_content"] == row["final_content"]
    assert result["raw_observation"]["recorded_transport_status"] == row["transport_status"]
    assert not result["admission_allowed"] and all(result[k] is None for k in ("identity_score", "state_score", "progression_score"))
    absent = store.lookup(**args_for(bundle, 2))
    assert absent["status"] == "unavailable" and absent["reason"] == "no_recorded_pair"
    assert "raw_observation" not in absent


@pytest.mark.parametrize("field", ["subject", "cue_query", "order", "region", "source"])
def test_wrong_lookup_context_never_reuses_candidate_alone(bundle, field):
    store = load(bundle); kwargs = args_for(bundle, 2)
    if field == "subject": kwargs[field] = "different subject"
    elif field == "cue_query": kwargs[field] = "different cue"
    elif field == "order": kwargs["images"] = list(reversed(kwargs["images"])); kwargs["region_ids"] = list(reversed(kwargs["region_ids"]))
    elif field == "region": kwargs["region_ids"][0] = "unknown"
    else:
        path = bundle.root / "different.png"; path.write_bytes(b"different source bytes"); kwargs["images"][0] = path
    result = store.lookup(**kwargs)
    assert result["status"] == "unavailable" and not result["admission_allowed"]
    assert "raw_observation" not in result


@pytest.mark.parametrize("when,target", [("before", "source"), ("before", "prepared"), ("after", "source"), ("after", "prepared")])
def test_source_or_prepared_change_invalidates_without_http(bundle, when, target):
    region = bundle.regions[bundle.method["cases"][0][bundle.roles[0] + "_region_id"]]
    path = Path(region["source" if target == "source" else "crop"]["path"])
    if when == "before":
        path.write_bytes(b"changed")
        with pytest.raises(ValueError): load(bundle)
    else:
        store = load(bundle); path.write_bytes(b"changed")
        result = store.lookup(**args_for(bundle))
        assert result["status"] == "unavailable" and result["reason"] == "source_or_preparation_changed"


def test_snapshot_inputs_and_results_are_isolated(bundle):
    store = load(bundle); kwargs = args_for(bundle, 2)
    wanted = bundle.raw["rows"][2]["final_content"]
    Path(bundle.raw_binding["path"]).write_text("changed after snapshot")
    Path(bundle.plan_binding["path"]).write_text("changed after snapshot")
    bundle.raw["model"]["repo"] = "mutated caller"
    result = store.lookup(**kwargs); result["raw_observation"]["final_content"] = "mutated result"
    contexts = store.contexts(); contexts[0]["region_ids"][0] = "mutated context"
    assert store.lookup(**kwargs)["raw_observation"]["final_content"] == wanted
    assert store.contexts()[0]["region_ids"][0] != "mutated context"


def test_raw_json_duplicate_keys_and_size_bounds(bundle):
    path = Path(bundle.raw_binding["path"])
    path.write_text('{"protocol":"a","protocol":"b"}', encoding="utf-8")
    bundle.raw_binding["sha256"] = sha(path)
    with pytest.raises(ValueError): load(bundle)
    path.write_bytes(b" " * (4 * 1024 * 1024 + 1)); bundle.raw_binding["sha256"] = sha(path)
    with pytest.raises(ValueError): load(bundle)


def test_outside_root_top_level_binding_rejected(bundle, tmp_path):
    outside = tmp_path.parent / (tmp_path.name + '-outside-report.json')
    outside.write_bytes(Path(bundle.raw_binding["path"]).read_bytes())
    bundle.raw_binding = {"path": str(outside), "sha256": sha(outside)}
    with pytest.raises(ValueError): load(bundle)


def test_reader_never_calls_model_runtime_or_network(bundle, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("Offline replay called runtime/network")
    monkeypatch.setattr(shape_runner.base, "request", forbidden)
    monkeypatch.setattr(shape_runner.base, "gpu_memory", forbidden)
    monkeypatch.setattr(shape_runner, "owned_server", forbidden)
    monkeypatch.setattr(shape_runner, "verify_runtime", forbidden)
    store = load(bundle)
    assert store.lookup(**args_for(bundle))["status"] == "uncertain"


@pytest.mark.parametrize("fault", ["outside", "existing"])
def test_export_write_scope_before_loading_reports(bundle, monkeypatch, fault):
    design = write_json(bundle.root / "export-design.json", {"protocol": "retained-paired-replay-design-1"})
    output = bundle.root.parent / (bundle.root.name + '-outside-export.json') if fault == "outside" else bundle.root / "existing.json"
    if fault == "existing": output.write_bytes(b"preserve this file")
    def forbidden(*args, **kwargs): raise AssertionError("Invalid output must not load reports")
    monkeypatch.setattr(replay.RetainedPairedObservations, "from_files", forbidden)
    with pytest.raises((ValueError, FileExistsError)): replay.export_replay(design, output, root=bundle.root)
    if fault == "existing": assert output.read_bytes() == b"preserve this file"
    else: assert not output.exists()


def refresh_case_bindings(b):
    if b.kind == "shape":
        path = Path(b.method["evidence_provenance"]["path"])
        design = json.loads(path.read_text(encoding="utf-8"))
        for case, declared in zip(b.method["cases"], design["planned_cases"]):
            declared["reference_region"] = case["reference_region_id"]
            declared["candidate_region"] = case["candidate_region_id"]
        b.method["evidence_provenance"] = write_json(path, design)
    observer = cue if b.kind == "cue" else shape
    for case, row in zip(b.method["cases"], b.raw["rows"]):
        body = observer.payload(*(case[r] for r in b.roles), b.method["subject"],
                                *([b.method["cue_query"]] if b.kind == "cue" else []))
        row["request_sha256"] = hashlib.sha256(checks.canonical(body).encode()).hexdigest()
        row["inputs"] = [{"role": r, "sha256": case[r]["sha256"]} for r in b.roles]
    sync(b)


def test_explicitly_recorded_reverse_pair_uses_its_own_context(bundle):
    original = args_for(bundle, 2)
    old_key = load(bundle).lookup(**original)["snapshot_key"]
    case = bundle.method["cases"][2]; first, second = bundle.roles
    case[first], case[second] = case[second], case[first]
    case[first + "_region_id"], case[second + "_region_id"] = case[second + "_region_id"], case[first + "_region_id"]
    refresh_case_bindings(bundle)
    store = load(bundle)
    reversed_result = store.lookup(**args_for(bundle, 2))
    assert reversed_result["status"] == "uncertain" and reversed_result["snapshot_key"] != old_key
    assert store.lookup(**original)["reason"] == "no_recorded_pair"


def test_incomplete_region_rejected_with_consistent_plan_and_request(bundle):
    load(bundle)
    if bundle.kind == "shape":
        case = bundle.method["cases"][2]; case["reference_region_id"] = "partial"
        case["reference"] = {k: bundle.regions["partial"]["crop"][k] for k in ("path", "sha256", "size")}
        expected = "wholly covered"
    else:
        prep = json.loads(Path(bundle.method["region_preparation"]["path"]).read_text(encoding="utf-8"))
        prep["preparation"]["regions"][0].update(box=[0, 0, 4, 12], required_box=[0, 0, 4, 12])
        manifest = regions.prepare(prep["preparation"], bundle.root / "partial-fullframes", workspace_root=bundle.root)
        bundle.method["region_preparation"] = write_json(bundle.root / "partial-preparation.json", prep)
        bundle.method["artifact_manifest"] = {"path": str(bundle.root / "partial-fullframes/manifest.json"),
                                              "sha256": sha(bundle.root / "partial-fullframes/manifest.json")}
        bundle.method["source_preparation"] = write_json(bundle.root / "partial-source-result.json", {
            "plan": bundle.method["region_preparation"], "manifest": bundle.method["artifact_manifest"]})
        by_id = {r["id"]: r for r in manifest["regions"]}
        for case in bundle.method["cases"]:
            for role in bundle.roles: case[role] = {k: by_id[case[role + "_region_id"]]["crop"][k] for k in ("path", "sha256", "size")}
        expected = "native full frames"
    refresh_case_bindings(bundle)
    with pytest.raises(ValueError, match=expected): load(bundle)


def test_nested_source_path_outside_root_rejected_before_reconstruction(bundle):
    prep_path = Path(bundle.method["region_preparation"]["path"])
    prep = json.loads(prep_path.read_text(encoding="utf-8"))
    source = prep["preparation"]["regions"][0]["source"]
    outside = bundle.root.parent / (bundle.root.name + '-outside-source.png')
    outside.write_bytes(Path(source["path"]).read_bytes()); source["path"] = str(outside)
    bundle.method["region_preparation"] = write_json(prep_path, prep)
    refresh_case_bindings(bundle)
    with pytest.raises(ValueError, match="escapes replay root"): load(bundle)


def test_rows_after_invalid_output_rejected_without_selecting_favorable_row(bundle):
    bundle.raw["rows"][0]["final_content"] = "invalid"
    bundle.raw_binding = write_json(Path(bundle.raw_binding["path"]), bundle.raw)
    with pytest.raises(ValueError, match="continues after"): load(bundle)


def test_duplicate_pair_context_not_hidden_by_different_case_ids(bundle):
    case, other = bundle.method["cases"][2], bundle.method["cases"][1]
    for role in bundle.roles:
        case[role] = copy.deepcopy(other[role]); case[role + "_region_id"] = other[role + "_region_id"]
    refresh_case_bindings(bundle)
    with pytest.raises(ValueError, match="Duplicate ordered pair context"): load(bundle)


def rebind_region_metadata(b, preparation, manifest):
    b.method["region_preparation"] = write_json(Path(b.method["region_preparation"]["path"]), preparation)
    manifest["plan_canonical_sha256"] = hashlib.sha256(checks.canonical(preparation["preparation"]).encode()).hexdigest()
    manifest_key = "artifact_manifest" if b.kind == "cue" else "region_manifest"
    b.method[manifest_key] = write_json(Path(b.method[manifest_key]["path"]), manifest)
    if b.kind == "cue":
        source_path = Path(b.method["source_preparation"]["path"])
        source_result = json.loads(source_path.read_text(encoding="utf-8"))
        source_result.update(plan=b.method["region_preparation"], manifest=b.method[manifest_key])
        b.method["source_preparation"] = write_json(source_path, source_result)
    else:
        evidence_path = Path(b.method["evidence_provenance"]["path"])
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        source_path = Path(evidence["source_preparation"]["path"])
        source_result = json.loads(source_path.read_text(encoding="utf-8"))
        source_result.update(plan=b.method["region_preparation"], manifest=b.method[manifest_key])
        evidence["source_preparation"] = write_json(source_path, source_result)
        evidence["artifact_manifest"] = b.method[manifest_key]
        b.method["evidence_provenance"] = write_json(evidence_path, evidence)


@pytest.mark.parametrize("target", ["source", "crop", "case"])
def test_relative_image_descriptors_rejected_before_cwd_dependent_reads(bundle, monkeypatch, target):
    load(bundle)  # The original absolute fixture is valid.
    manifest_key = "artifact_manifest" if bundle.kind == "cue" else "region_manifest"
    preparation = json.loads(Path(bundle.method["region_preparation"]["path"]).read_text(encoding="utf-8"))
    manifest = json.loads(Path(bundle.method[manifest_key]["path"]).read_text(encoding="utf-8"))
    descriptor = (preparation["preparation"]["regions"][0]["source"] if target == "source" else
                  manifest["regions"][0]["crop"] if target == "crop" else
                  bundle.method["cases"][0][bundle.roles[0]])
    original = Path(descriptor["path"])
    relative = original.relative_to(bundle.root)
    outside = bundle.root.parent / (bundle.root.name + "-other-cwd")
    homonym = outside / relative
    homonym.parent.mkdir(parents=True, exist_ok=True)
    homonym.write_bytes(original.read_bytes())
    descriptor["path"] = str(relative)
    if target == "source":
        # Keep every declaration coherent. The legacy reconstruction can now
        # read the valid external homonym instead of the changed rooted file.
        for row in preparation["preparation"]["regions"]:
            if row["source"]["path"] == str(original): row["source"]["path"] = str(relative)
        for row in manifest["regions"]:
            if row["source"]["path"] == str(original): row["source"]["path"] = str(relative)
        original.write_bytes(b"changed source inside replay root")
        assert sha(original) != descriptor["sha256"] and sha(homonym) == descriptor["sha256"]
    rebind_region_metadata(bundle, preparation, manifest)
    monkeypatch.chdir(outside)
    refresh_case_bindings(bundle)
    runner = cue_runner if bundle.kind == "cue" else shape_runner
    delegated, old_preflight = [], runner.preflight_plan
    def tracked(*args, **kwargs):
        delegated.append(True)
        return old_preflight(*args, **kwargs)
    monkeypatch.setattr(runner, "preflight_plan", tracked)
    with pytest.raises(ValueError, match="absolute"):
        load(bundle)
    assert delegated == []


def test_absolute_image_descriptors_work_from_another_cwd(bundle, monkeypatch):
    kwargs = args_for(bundle, 2)
    outside = bundle.root.parent / (bundle.root.name + "-absolute-cwd")
    outside.mkdir()
    monkeypatch.chdir(outside)
    assert load(bundle).lookup(**kwargs)["status"] == "uncertain"
