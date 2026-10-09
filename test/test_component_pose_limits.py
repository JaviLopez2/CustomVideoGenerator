"""Known synthetic geometry cannot certify an unknown generated object's identity."""
import copy
import hashlib
import json
import runpy
from pathlib import Path

import numpy as np
import pytest

M = runpy.run_path(str(Path(__file__).parents[1] / "scripts/probe_component_pose_limits.py"))
PLANE = np.array([[-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0],
                  [0, -.55, 0], [0, .55, 0], [.3, .2, 0], [-.2, .35, 0]])


def test_pinhole_projection_known_coordinates():
    assert np.allclose(M["project"]([[0, 0, 0], [1, 0, 0], [0, 1, 0]]),
                       [[320, 240], [420, 240], [320, 340]])


@pytest.mark.parametrize("points", [[[0, 0, -6]], [[0, 0, float("nan")]], [[1, 2]]])
def test_invalid_or_behind_camera_geometry_is_rejected(points):
    with pytest.raises(ValueError):
        M["project"](points)


def test_in_plane_uniform_similarity_has_zero_synthetic_residual():
    a = np.array([[0., 0.], [100, 0], [100, 100], [0, 100], [35, 60]])
    angle = .4
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    b = 1.3*a@rotation.T + [10, -20]
    r = M["fit_diagnostic"](a, b, "similarity", [0, 1, 2, 3], [4])
    assert r["fit_available"] and r["heldout_max_residual_pixels"] < 1e-8
    assert not r["physical_identity_established"] and not r["admission_allowed"]


def test_unchanged_tilted_plane_defeats_similarity_but_homography_predicts_unused_points():
    a, b = M["project"](PLANE), M["project"](PLANE, ry=45)
    s = M["fit_diagnostic"](a, b, "similarity", [0, 1, 2, 3], [4, 5, 6, 7])
    h = M["fit_diagnostic"](a, b, "projective", [0, 1, 2, 3], [4, 5, 6, 7])
    assert s["heldout_max_residual_pixels"] > 1
    assert h["heldout_max_residual_pixels"] < 1e-8


def test_plane_homography_does_not_correct_points_with_different_depth():
    xyz = PLANE.copy(); xyz[6, 2] = .8; xyz[7, 2] = -.6
    a, b = M["project"](xyz), M["project"](xyz, ry=45)
    h = M["fit_diagnostic"](a, b, "projective", [0, 1, 2, 3], [4, 5, 6, 7])
    assert h["anchor_max_residual_pixels"] < 1e-8
    assert h["heldout_max_residual_pixels"] > 5


def test_fitting_four_deformed_corners_is_not_independent_shape_validation():
    a = np.array([[0., 0.], [100, 0], [100, 100], [0, 100]])
    b = a.copy(); b[2] += [25, -10]
    r = M["fit_diagnostic"](a, b, "projective", [0, 1, 2, 3], [])
    assert r["anchor_max_residual_pixels"] < 1e-8
    assert r["heldout_max_residual_pixels"] is None and r["heldout_count"] == 0
    assert not r["physical_identity_established"]


def test_deformed_unused_part_remains_visible_despite_exact_anchor_fit():
    a = M["project"](PLANE); b = a.copy(); b[6] += [12, 0]
    r = M["fit_diagnostic"](a, b, "projective", [0, 1, 2, 3], [4, 5, 6, 7])
    assert r["anchor_max_residual_pixels"] < 1e-8
    assert r["heldout_max_residual_pixels"] == pytest.approx(12)


@pytest.mark.parametrize("anchors,heldout", [([0, 1, 2, 3], [3, 4]), ([0, 1, 2, 2], [4]),
                                            ([0, 1, 2, 99], [4]), ([0, 1, 2, True], [4])])
def test_anchor_and_check_points_are_disjoint_unique_in_bounds(anchors, heldout):
    a = np.array([[0, 0], [100, 0], [100, 100], [0, 100], [50, 60]])
    with pytest.raises(ValueError):
        M["fit_diagnostic"](a, a, "projective", anchors, heldout)


def test_collinear_homography_remains_unavailable_without_nan_json():
    a = np.array([[0., 0.], [10, 0], [20, 0], [30, 0]])
    r = M["fit_diagnostic"](a, a, "projective", [0, 1, 2, 3], [])
    assert not r["fit_available"] and r["matrix"] is None
    json.dumps(r, allow_nan=False)


def test_uncertainty_bounds_overlap_for_small_part_difference():
    a = M["distance_interval"]([0, 0], [30, 0], 3, 3)
    b = M["distance_interval"]([0, 0], [35, 0], 3, 3)
    assert a == [24, 36] and b == [29, 41] and a[1] >= b[0]
    assert M["ratio_interval"](a, [194, 206]) == pytest.approx([24/206, 36/194])
    assert M["ratio_interval"](a, [0, 10]) is None


def test_negative_point_uncertainty_is_rejected():
    with pytest.raises(ValueError):
        M["distance_interval"]([0, 0], [30, 0], -1, 3)


def test_role_names_and_reviewed_positions_never_certify_correspondence():
    p = {"id": "cap", "point": [0, 0], "uncertainty_pixels": 3,
         "physical_correspondence_established": False}
    doc = {"eligible_for_identity_metrics": False, "rows": [
        {"id": "image_0", "landmarks": [p]},
        {"id": "image_1", "landmarks": [copy.deepcopy(p)]},
        {"id": "image_2", "landmarks": [{**p, "id": "connection"}]}]}
    rows = M["audit_roles"](doc, [["image_0", "image_1"], ["image_0", "image_2"]])
    assert rows[0]["shared_nominal_roles"] == ["cap"]
    assert rows[1]["shared_nominal_roles"] == []
    assert all(r["real_identity_score"] is None and not r["physical_identity_established"] for r in rows)
    assert rows[1]["full_mask_use"] == "excluded_disputed_boundary"


def test_bound_json_refuses_changed_review_input(tmp_path):
    p = tmp_path/"review.json"; p.write_text('{"review":"pending"}')
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    assert M["read_bound_json"](p, sha) == {"review": "pending"}
    p.write_text('{"review":"approved"}')
    with pytest.raises(ValueError):
        M["read_bound_json"](p, sha)


def test_report_does_not_overwrite_existing_checkpoint(tmp_path):
    p = tmp_path/"report.json"; p.write_text("retained")
    with pytest.raises(ValueError):
        M["preserve_outputs"](p, tmp_path/"figure.svg")
    assert p.read_text() == "retained"
