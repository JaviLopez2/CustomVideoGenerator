"""Frozen CPU full-frame preparation; no resize, inference or overwrite."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from scripts import prepare_visual_regions as regions


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


plan_path = ROOT / "docs/validation/retained-temporal-visual-input-plan-2026-10-09.json"
if digest(plan_path) != "cba401a3f79661a036535bd43ce2545c853b31d225ad793ef465f679bbc2bf85":
    raise ValueError("Frozen plan changed")
plan = json.loads(plan_path.read_text(encoding="utf-8"))
head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
if head != plan["execution_base_head"]:
    raise ValueError("Recipe belongs to the declared execution base")
for key in ("dataset", "legacy_results", "prior_replay_v4", "helper"):
    binding = plan[key]
    if digest(ROOT / binding["path"]) != binding["sha256"]:
        raise ValueError("Retained binding changed")
report_path = ROOT / "docs/validation/retained-temporal-fullframes-result-2026-10-09.json"
if report_path.exists():
    raise FileExistsError("Preserve previous report")
manifest = regions.prepare(plan["preparation"], ROOT / plan["output_directory"], workspace_root=ROOT)
checks = []
for row in manifest["regions"]:
    assert row["coverage_relation"] == "contained" and row["semantic_coverage_review"] == "pending"
    assert row["effective_box"] == [0, 0, *row["source"]["size"]]
    assert digest(row["source"]["path"]) == row["source"]["sha256"]
    assert digest(row["crop"]["path"]) == row["crop"]["sha256"]
    with Image.open(row["source"]["path"]) as source, Image.open(row["crop"]["path"]) as output:
        assert source.size == output.size and source.mode == output.mode == "RGB"
        assert np.array_equal(np.asarray(source), np.asarray(output))
        assert output.info == {}
    checks.append({"id": row["id"], "source": row["source"], "output": row["crop"],
                   "full_native_frame_pixels_mode_dimensions_verified": True,
                   "ancillary_metadata_copied": False, "semantic_human_coverage": "pending"})
manifest_path = ROOT / plan["output_directory"] / "manifest.json"
assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
report = {"protocol": "retained-temporal-fullframes-result-1", "execution_head": head,
          "plan": {"path": plan_path.relative_to(ROOT).as_posix(), "sha256": digest(plan_path)},
          "recipe_sha256": digest(__file__), "helper": plan["helper"],
          "manifest": {"path": manifest_path.relative_to(ROOT).as_posix(), "sha256": digest(manifest_path)},
          "frames": checks, "model_requests": 0, "generation_requests": 0,
          "physical_temperature_measured": False, "physical_identity_established": False,
          "admission_allowed": False, "human_gold_added": False}
with report_path.open("x", encoding="utf-8") as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print("4 full native RGB frames verified; metadata removed; no image/model requests")
