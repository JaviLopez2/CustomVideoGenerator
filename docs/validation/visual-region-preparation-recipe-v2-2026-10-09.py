"""Frozen, one-cohort CPU recipe. Refuses overwrite and changed source bindings."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from scripts import prepare_visual_regions


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(binding):
    path = ROOT / binding["path"]
    if digest(path) != binding["sha256"]:
        raise ValueError("Retained binding changed")
    return path


plan_path = ROOT / "docs/validation/visual-region-preparation-plan-v2-2026-10-09.json"
if digest(plan_path) != "da77e1f7f8c73273740444ada5963d0e8e823faac28bb5b248bae79cece958ba":
    raise ValueError("Frozen plan changed")
plan = json.loads(plan_path.read_text(encoding="utf-8"))
head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
if head != plan["execution_base_head"]:
    raise ValueError("Recipe belongs to the declared execution base")
for binding in (plan["helper"], plan["prior_regions"], plan["comparison_binding"]):
    verify(binding)
report_path = ROOT / "docs/validation/visual-region-preparation-result-v2-2026-10-09.json"
if report_path.exists():
    raise FileExistsError("Preserve previous report")

manifest = prepare_visual_regions.prepare(
    plan["preparation"], ROOT / plan["output_directory"], workspace_root=ROOT
)
previous_result = json.loads(verify(plan["previous_result"]).read_text(encoding="utf-8"))
previous_manifest = json.loads(verify(previous_result["manifest"]).read_text(encoding="utf-8"))
previous_by_id = {row["id"]: row for row in previous_manifest["regions"]}
verify(plan["preserved_initial_helper"])
prior = json.loads(verify(plan["comparison_binding"]).read_text(encoding="utf-8"))
old_by_source = {row["source"]["sha256"]: row for row in prior["derivation"]["four_unique_images"]}
checks = []
for row in manifest["regions"]:
    source, crop = Path(row["source"]["path"]), Path(row["crop"]["path"])
    assert digest(source) == row["source"]["sha256"]
    assert digest(crop) == row["crop"]["sha256"]
    x0, y0, x1, y1 = row["effective_box"]
    with Image.open(source) as image, Image.open(crop) as region:
        assert image.mode == region.mode == row["source_mode"]
        assert np.array_equal(np.asarray(image)[y0:y1, x0:x1], np.asarray(region))
        assert region.info == {}
    assert row["coverage_relation"] == plan["expected_coverage"][row["id"]]
    assert row["semantic_coverage_review"] == "pending"
    check = {"id": row["id"], "source_sha256": row["source"]["sha256"],
             "crop_sha256": row["crop"]["sha256"], "size": row["crop"]["size"],
             "mode": row["crop"]["mode"], "effective_box": row["effective_box"],
             "coverage_relation": row["coverage_relation"],
             "native_pixel_subset_independently_verified": True,
             "crop_metadata_keys": [], "semantic_coverage_review": "pending"}
    previous_crop = verify(previous_by_id[row["id"]]["crop"])
    assert crop.read_bytes() == previous_crop.read_bytes()
    check["initial_cohort_crop_byte_identical"] = True
    old = old_by_source.get(row["source"]["sha256"])
    if old is not None:
        old_crop = verify(old["crop"])
        assert row["effective_box"] == old["crop_box_xyxy"]
        assert crop.read_bytes() == old_crop.read_bytes()
        check["historical_key_crop_byte_identical"] = True
    checks.append(check)
assert len(checks) == 8 and sum("historical_key_crop_byte_identical" in r for r in checks) == 4
assert not manifest["admission_allowed"] and not manifest["physical_identity_established"]
manifest_path = ROOT / plan["output_directory"] / "manifest.json"
assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
report = {"protocol": "visual-region-preparation-result-1", "execution_head": head,
          "plan": {"path": plan_path.relative_to(ROOT).as_posix(), "sha256": digest(plan_path)},
          "recipe_sha256": digest(__file__), "helper": plan["helper"],
          "manifest": {"path": manifest_path.relative_to(ROOT).as_posix(), "sha256": digest(manifest_path)},
          "regions": checks, "generation_requests": 0, "model_requests": 0,
          "admission_allowed": False, "physical_identity_established": False,
          "semantic_whole_object_coverage": "pending; technical rectangle coverage only"}
with report_path.open("x", encoding="utf-8") as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print("8 native pixel subsets verified; 4 historical key crops byte-identical")
print("Coverage: 6 contained, 1 partial, 1 disjoint; semantic review remains pending")
print("No generation/model requests; report:", report_path.relative_to(ROOT))
