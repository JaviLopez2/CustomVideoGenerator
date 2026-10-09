"""Point coverage and separate localization are different, conditional evidence."""
import copy
import json
import runpy
from pathlib import Path

import pytest

M = runpy.run_path(str(Path(__file__).parents[1] / "scripts/audit_retained_component_sites.py"))
PROFILE = {"version": "target-location-observations-1", "components": {
    "handle_body_contacts": "Separate directly visible handle/body attachment sites."}}


def sites():
    return [{"id": "upper_handle_attachment", "point": [50, 25], "uncertainty_pixels": 3},
            {"id": "lower_handle_attachment", "point": [50, 75], "uncertainty_pixels": 3}]


def archived_row():
    answer = {"target_presence": {"status": "present", "evidence": "Visible vessel."}, "components": {
        "handle_body_contacts": {"state": "observed", "evidence": "Visible sites.", "locations": [
            {"box": [400, 150, 600, 350], "evidence": "One site."},
            {"box": [400, 650, 600, 850], "evidence": "Another site."}]}}}
    return {"transport_status": "completed", "finish_reason": "stop", "final_content": json.dumps(answer), "inventory": answer}


def annotation():
    return {"size": [100, 100], "family": "mug", "landmarks": sites()}


def test_normalized_box_uses_full_image_extent_without_rounding():
    assert M["box_pixels"]([650, 400, 700, 450], [512, 512]) == pytest.approx([332.8, 204.8, 358.4, 230.4])
    assert M["box_pixels"]([0, 0, 1000, 1000], [512, 512]) == [0, 0, 512, 512]


@pytest.mark.parametrize("box", [[-1, 0, 50, 50], [0, 0, 1001, 50], [0, 0, 0, 50],
                                [0, 10, 20, 5], [0, 0, True, 20], [0, 0, 2.5, 30]])
def test_invalid_boxes_are_not_clamped_or_repaired(box):
    with pytest.raises(ValueError):
        M["box_pixels"](box, [100, 100])


@pytest.mark.parametrize("point,expected", [([15, 15], "disk_contained"),
                                          ([10, 15], "disk_intersects_boundary"),
                                          ([9, 15], "disk_intersects_boundary"),
                                          ([8, 15], "disk_disjoint")])
def test_closed_disk_boundary_and_tangent_cases(point, expected):
    result = M["disk_to_box"](point, 1, [10, 10, 20, 20])
    assert result["relation"] == expected
    assert not result["pixel_truth_verified"] and not result["admission_allowed"]


def test_point_inside_fractional_edge_does_not_guarantee_uncertainty_disk_inside():
    result = M["disk_to_box"]([348, 221], 3, [317.44, 194.56, 348.16, 235.52])
    assert result["nominal_inside"] and result["relation"] == "disk_intersects_boundary"
    assert result["signed_margin_pixels"] == pytest.approx(.16)


def test_one_grouped_box_reaches_two_points_but_cannot_separate_two_sites():
    result = M["site_support"](sites(), [[400, 150, 600, 850]], [100, 100])
    assert result["disk_contained_site_count"] == 2
    assert result["maximum_distinct_contained_matching"] == 1
    assert result["maximum_exclusive_contained_matching"] == 0
    assert result["grouped_or_ambiguous_box_indices"] == [0]


def test_two_wide_boxes_do_not_manufacture_separate_localization():
    result = M["site_support"](sites(), [[0, 0, 1000, 1000], [10, 10, 990, 990]], [100, 100])
    assert result["maximum_distinct_contained_matching"] == 2
    assert result["maximum_exclusive_contained_matching"] == 0
    assert not result["physical_identity_established"]


def test_two_small_distinct_boxes_locate_each_reviewed_site_separately():
    result = M["site_support"](sites(), [[400, 150, 600, 350], [400, 650, 600, 850]], [100, 100])
    assert result["maximum_exclusive_contained_matching"] == 2
    assert result["grouped_or_ambiguous_box_indices"] == []


def test_two_entries_covering_only_upper_site_do_not_become_two_parts():
    result = M["site_support"](sites(), [[400, 150, 600, 350], [410, 160, 590, 340]], [100, 100])
    assert result["disk_intersected_site_count"] == 1
    assert result["maximum_distinct_intersecting_matching"] == 1


def test_nearby_disk_is_possible_support_without_contained_support():
    result = M["site_support"]([sites()[0]], [[400, 150, 490, 350]], [100, 100])
    assert result["nominal_site_covered_count"] == 0
    assert result["maximum_exclusive_contained_matching"] == 0
    assert result["maximum_exclusive_intersecting_matching"] == 1


def test_no_boxes_preserves_missing_coordinate_evidence():
    result = M["site_support"](sites(), [], [100, 100])
    assert result["maximum_exclusive_intersecting_matching"] == 0
    assert result["disk_intersected_site_count"] == 0


def test_full_frame_box_over_hole_center_never_certifies_mask_precision():
    result = M["site_support"]([sites()[0]], [[0, 0, 1000, 1000]], [100, 100])
    assert result["disk_contained_site_count"] == 1
    assert result["box_area_fractions"] == [1]
    assert not result["mask_precision_verified"]


def test_duplicate_sites_are_rejected():
    with pytest.raises(ValueError):
        M["site_support"]([sites()[0], copy.deepcopy(sites()[0])], [], [100, 100])


def test_inventory_replay_rejects_modified_stored_answer():
    row = archived_row(); row["inventory"] = copy.deepcopy(row["inventory"])
    row["inventory"]["components"]["handle_body_contacts"]["locations"][0]["box"] = [0, 0, 1000, 1000]
    with pytest.raises(ValueError):
        M["replay_inventory"](row, PROFILE)


def test_truncated_output_remains_unavailable_without_json_salvage():
    row = archived_row(); row.update(finish_reason="length", final_content='{"target_presence":')
    assert M["replay_inventory"](row, PROFILE) is None
    result = M["audit_row"](row, PROFILE, annotation())
    assert result["status"] == "unavailable" and result["site_analysis"] is None


def test_target_absence_is_nonapplicable_and_not_missing_contact_score():
    row = archived_row(); answer = row["inventory"]
    answer["target_presence"]["status"] = "absent"
    answer["components"]["handle_body_contacts"].update(state="not_applicable", locations=[])
    row["final_content"] = json.dumps(answer)
    result = M["audit_row"](row, PROFILE, annotation())
    assert result["status"] == "not_applicable" and result["site_analysis"] is None


def test_valid_report_replay_keeps_authority_false():
    row = archived_row(); result = M["audit_row"](row, PROFILE, annotation())
    assert result["site_analysis"]["maximum_exclusive_contained_matching"] == 2
    assert result["real_identity_score"] is None and not result["admission_allowed"]
