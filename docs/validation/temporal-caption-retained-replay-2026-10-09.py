"""Frozen CPU audit recipe. No model calls; preserve existing raw reports."""
import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.services import visual_qa as qa


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


PLAN = "docs/validation/temporal-caption-retained-replay-plan-2026-10-09.json"
OUTPUT = ROOT / "docs/validation/temporal-caption-retained-replay-2026-10-09.json"
assert not OUTPUT.exists(), "Preserve previous audit output"
plan = load(PLAN)
assert plan["protocol"] == "temporal-caption-retained-replay-plan-1"
for binding in plan["sources"]:
    assert digest(ROOT / binding["path"]) == binding["sha256"]

binding = plan["legacy_source"]
raw = subprocess.check_output(["git", "show", binding["git_ref"] + ":" + binding["path"]], cwd=ROOT)
assert hashlib.sha256(raw).hexdigest() == binding["git_blob_content_sha256"]
tree = ast.parse(raw.decode("utf-8"))
allowed_imports = {"copy", "hashlib", "json", "math", "re", "time", "collections", "pathlib", "numpy", "PIL"}
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        assert all(alias.name.split(".")[0] in allowed_imports for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
        assert node.module.split(".")[0] in allowed_imports
# This is the hash-pinned pure QA module from the declared trusted Git commit.
# FlorenceEvidence remains inert: both engines receive only ArchivedEvidence.
legacy = types.ModuleType("retained_qa_v2")
exec(compile(tree, "<trusted Git QA v2>", "exec"), legacy.__dict__)
assert legacy.VERSION == binding["qa_version"] and qa.VERSION == plan["current_qa_version"]

dataset_path, result_path = plan["sources"][0]["path"], plan["sources"][1]["path"]
dataset, source_report = load(dataset_path), load(result_path)
cases = {row["id"]: row for row in dataset["cases"]}
saved = {row["id"]: row for row in source_report["rows"]}


class ArchivedEvidence:
    model_identity = "archived-only/" + digest(ROOT / result_path)

    def __init__(self, observations):
        self.observations, self.calls = observations, []

    def read(self, image, task="<MORE_DETAILED_CAPTION>", query="", crop=None):
        assert query == "" and crop is None
        image_hash = digest(image)
        matches = [(i, row) for i, row in enumerate(self.observations)
                   if row.get("image_sha256") == image_hash and row.get("task") == task]
        assert matches, "Missing saved observation; never infer"
        canonical = {json.dumps((row.get("available"), row.get("value"), row.get("size")),
                                sort_keys=True, ensure_ascii=False) for _, row in matches}
        assert len(canonical) == 1, "Conflicting saved evidence"
        i, row = matches[0]
        self.calls.append({"image_sha256": image_hash, "task": task, "source_observation_index": i})
        # Do not present historical inference timings as a new measurement.
        result = copy.deepcopy(row)
        result.update(load_seconds=0, infer_seconds=0, seconds=0, cache_hit=False,
                      archived_replay=True)
        return result


rows, input_bindings = [], {}
for case_id in plan["retained_case_ids"]:
    case, historical = cases[case_id], saved[case_id]["new"]
    assert historical["qa_version"] == legacy.VERSION
    assert digest(case["artifact"]) == case["sha256"] == historical["image_sha256"]
    contract = case["contract"]
    inputs = [case["artifact"], contract["temporal"]["previous_image"]]
    if contract.get("reference_image"):
        inputs.append(contract["reference_image"])
    for image in inputs:
        path = Path(image).resolve()
        assert path.is_relative_to(ROOT.resolve())
        input_bindings[str(path)] = digest(path)
    observations = historical["observations"]
    before_evidence, after_evidence = ArchivedEvidence(observations), ArchivedEvidence(observations)
    before = legacy.VisualQA(before_evidence).assess(case["artifact"], contract)
    after = qa.VisualQA(after_evidence).assess(case["artifact"], contract)
    assert before["checks"] == historical["checks"] and before["verdict"] == historical["verdict"]
    assert before_evidence.calls == after_evidence.calls
    rows.append({"case_id": case_id, "contract": contract,
                 "expected_verdict_original": case["expected_verdict"],
                 "label_provenance_original": case["review_provenance"],
                 "saved_caption": historical["caption"], "read_calls": after_evidence.calls,
                 "v2": {key: before[key] for key in ["qa_version", "verdict", "checks", "seconds"]},
                 "v3": {key: after[key] for key in ["qa_version", "verdict", "checks", "seconds"]},
                 "timing_scope": "CPU replay of saved evidence only; no inference latency",
                 "overall_verdict_changed": before["verdict"] != after["verdict"]})

probes = []
for example in plan["synthetic_negation_probes"]:
    actual = qa.state_check(example["caption"], example["contract"])
    probes.append({**example, "actual_v3": actual,
                   "matches_declared_literal_policy": actual["status"] == example["expected_status"]})

report = {"protocol": "temporal-caption-retained-replay-1",
          "checked_utc": datetime.now(timezone.utc).isoformat(),
          "execution_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
          "plan": {"path": PLAN, "sha256": digest(ROOT / PLAN)},
          "recipe_sha256": digest(__file__), "sources": plan["sources"],
          "legacy_source": binding, "image_bindings": input_bindings,
          "retained_rows": rows, "retained_overall_verdict_changes": sum(row["overall_verdict_changed"] for row in rows),
          "literal_negation_probes": probes,
          "literal_policy_mismatches": sum(not row["matches_declared_literal_policy"] for row in probes),
          "independent_human_truth_added": False, "raw_reports_or_labels_modified": False,
          "generation_requests": 0, "model_requests": 0, "downloads": 0,
          "service_changes": 0, "population_accuracy_or_new_inference_latency_claimed": False,
          "decision": "Retained captions still omit literal evidence; parser safety does not repair visual extraction. Inspect failed explicit-negation probes before extending the parser."}
OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"retained_cases": len(rows), "verdict_changes": report["retained_overall_verdict_changes"],
                  "negation_probes": len(probes), "policy_mismatches": report["literal_policy_mismatches"],
                  "output": str(OUTPUT)}))
