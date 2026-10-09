"""Independent checks of audit provenance, coordinates and retained uncertainty."""
import hashlib
import runpy
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

M = runpy.run_path(str(Path(__file__).parents[1] / "scripts/audit_spatial_geometry.py"))


@pytest.mark.parametrize("box", [[-1, 0, 10, 10], [0, 0, 11, 10], [2, 2, 2, 3],
                                 [0, 0, True, 8], [0, 0, 5.5, 8]])
def test_invalid_or_ambiguous_roi_is_rejected(box):
    with pytest.raises(ValueError):
        M["validate_box"](box, (10, 10))


def test_pixels_are_hash_bound_before_processing(tmp_path):
    path = tmp_path / "source.png"
    Image.new("RGB", (40, 30), "red").save(path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    record = {"path": str(path), "sha256": sha, "roi": [1, 2, 30, 25]}
    assert M["load_pixels"](record).shape == (30, 40, 3)
    Image.new("RGB", (40, 30), "blue").save(path)
    with pytest.raises(ValueError, match="hash"):
        M["load_pixels"](record)


def test_similarity_fit_uses_cartesian_coordinates_and_ignores_outlier():
    source = np.array([[0, 0], [30, 0], [0, 40], [25, 40], [12, 19], [45, 12]], dtype=float)
    target = source * 1.5 + [13, -7]
    target[-1] = [2000, 800]
    result = M["registration"](source, target)
    assert result["inlier_count"] == 5
    assert result["transform_matrix"][0][2] == pytest.approx(13)
    assert result["transform_matrix"][1][2] == pytest.approx(-7)
    assert result["status"] == "uncertain" and not result["physical_identity_established"]


def test_too_few_matches_abstain_without_repair():
    result = M["registration"](np.array([[0, 0], [1, 1]]), np.array([[0, 0], [1, 1]]))
    assert not result["fit_available"] and result["reason"] == "insufficient_correspondences"
    assert not result["admission_allowed"]


def test_degenerate_points_preserve_failed_estimation_as_uncertain():
    points = np.array([[12, 13], [12, 13], [12, 13]], dtype=float)
    result = M["registration"](points, points)
    assert not result["fit_available"] and result["reason"] == "no_finite_similarity_fit"
    assert result["status"] == "uncertain" and not result["admission_allowed"]


def test_failed_estimation_return_object_is_checked_before_attributes(monkeypatch):
    points = np.array([[12, 13], [12, 13], [12, 13]], dtype=float)
    failed = M["SimilarityTransform"].from_estimate(points, points)
    assert not failed
    monkeypatch.setitem(M["registration"].__globals__, "ransac",
                        lambda *args, **kwargs: (failed, np.ones(3, dtype=bool)))
    result = M["registration"](points, points)
    assert not result["fit_available"] and result["reason"] == "no_finite_similarity_fit"
    assert not result["admission_allowed"]


def test_perfect_mask_overlap_cannot_approve_identity():
    mask = np.zeros((80, 70), dtype=bool)
    mask[15:65, 20:50] = True
    result = M["compare_masks"](mask, mask)
    assert result["dice"] == pytest.approx(1)
    assert result["status"] == "uncertain"
    assert not result["admission_allowed"] and not result["physical_identity_established"]


def test_normalization_preserves_large_internal_opening():
    mask = np.zeros((100, 80), dtype=bool)
    mask[10:90, 10:70] = True
    mask[35:65, 25:55] = False
    normalized = M["normalize_mask"](mask)
    from scipy.ndimage import binary_fill_holes
    assert np.count_nonzero(binary_fill_holes(normalized) & ~normalized) > 100


def test_empty_segmentation_is_unavailable():
    empty = np.zeros((30, 30), dtype=bool)
    result = M["compare_masks"](empty, empty)
    assert result["status"] == "unavailable" and result["dice"] is None


def test_existing_outputs_are_preserved(tmp_path):
    output = tmp_path / "evidence.json"
    output.write_text("retained", encoding="utf-8")
    figures = tmp_path / "figures"
    with pytest.raises(ValueError, match="existing"):
        M["reserve_outputs"](output, figures)
    assert output.read_text(encoding="utf-8") == "retained" and not figures.exists()
