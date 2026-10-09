"""Structural validity and provenance are separate from independent region review."""
import copy
import hashlib
import runpy
from pathlib import Path

import pytest
from PIL import Image

M = runpy.run_path(str(Path(__file__).parents[1] / "scripts/prepare_spatial_annotation_review.py"))


def row():
    return {"id": "object_0", "size": [80, 60], "path": "retained.png", "sha256": "0"*64,
            "outer": [[10, 10], [70, 10], [70, 50], [10, 50]],
            "holes": [{"id": "hole_0", "polygon": [[25, 20], [45, 20], [45, 40], [25, 40]]}],
            "landmarks": [{"id": "contact", "point": [15, 25], "region": "foreground", "uncertainty_pixels": 3},
                          {"id": "opening", "point": [35, 30], "region": "hole_0", "uncertainty_pixels": 3}],
            "boundary_uncertainty_pixels": 3, "independent_review_status": "pending"}


@pytest.mark.parametrize("ring", [ [[-1, 0], [10, 0], [10, 10]],
    [[0, 0], [80, 0], [10, 10]], [[0, 0], [True, 4], [5, 10]],
    [[0, 0], [3, 3], [6, 6]], [[0, 0], [20, 20], [0, 20], [20, 0]],
    [[0, 0], [0, 20], [20, 20], [20, 0], [10, 0], [10, 25]] ])
def test_out_of_bounds_degenerate_or_self_intersecting_ring_is_rejected(ring):
    with pytest.raises(ValueError):
        M["validate_ring"](ring, (80, 60))


def test_mask_retains_full_foreground_and_cuts_only_declared_hole():
    mask, stats = M["rasterize"](row())
    assert mask.getpixel((15, 25)) == 255
    assert mask.getpixel((35, 30)) == 0 and mask.getpixel((5, 5)) == 0
    assert stats["holes_annotated"] == 1 and stats["landmarks_annotated"] == 2
    assert not stats["pixel_truth_verified"] and not stats["admission_allowed"]


def test_hole_outside_outer_contour_is_rejected():
    value = row(); value["holes"][0]["polygon"] = [[5, 5], [30, 5], [30, 30], [5, 30]]
    with pytest.raises(ValueError, match="hole"):
        M["rasterize"](value)


def test_overlapping_holes_are_rejected():
    value = row(); value["holes"].append({"id": "hole_1", "polygon": [[35, 25], [55, 25], [55, 45], [35, 45]]})
    with pytest.raises(ValueError, match="overlap"):
        M["rasterize"](value)


def test_landmark_region_is_verified_without_guessing_its_role():
    value = row(); value["landmarks"][0]["point"] = [35, 30]
    with pytest.raises(ValueError, match="landmark"):
        M["rasterize"](value)


def test_duplicate_landmarks_are_rejected():
    value = row(); value["landmarks"].append(copy.deepcopy(value["landmarks"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        M["rasterize"](value)


def test_draft_cannot_claim_independent_human_region_verification():
    document = {"protocol": "retained-spatial-annotation-draft-1", "annotation_source": "assistant_manual_draft",
                "independent_review_status": "pending", "pixel_truth_verified": True,
                "admission_allowed": False, "rows": [row()]}
    with pytest.raises(ValueError):
        M["validate_document"](document)


def test_pending_regions_cannot_be_declared_reviewed_at_document_level():
    document = {"protocol": "retained-spatial-annotation-draft-1", "annotation_source": "assistant_manual_draft",
                "independent_review_status": "reviewed", "rows": [row()]}
    with pytest.raises(ValueError, match="pending"):
        M["validate_document"](document)


def test_landmark_cannot_claim_certified_physical_correspondence():
    value = row(); value["landmarks"][0]["physical_correspondence_established"] = True
    with pytest.raises(ValueError, match="correspondence"):
        M["rasterize"](value)


def test_hash_and_declared_size_bind_source_without_modifying_bytes(tmp_path):
    path = tmp_path / "source.png"; Image.new("RGB", (80, 60), "red").save(path)
    before = path.read_bytes(); value = row(); value.update(path=str(path), sha256=hashlib.sha256(before).hexdigest())
    assert M["load_source"](value) == before and path.read_bytes() == before
    value["size"] = [70, 60]
    with pytest.raises(ValueError, match="size"):
        M["load_source"](value)
    value["size"] = [80, 60]; Image.new("RGB", (80, 60), "blue").save(path)
    with pytest.raises(ValueError, match="hash"):
        M["load_source"](value)


def test_review_output_does_not_replace_existing_artifacts(tmp_path):
    path = tmp_path / "review.json"; path.write_text("retained", encoding="utf-8")
    with pytest.raises(ValueError):
        M["preserve_outputs"](path, tmp_path / "figures")
    assert path.read_text(encoding="utf-8") == "retained"
