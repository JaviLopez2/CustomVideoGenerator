"""Offline point/box localization diagnostics; never physical identity or masks."""
import argparse
import base64
import hashlib
import json
import math
import runpy
import subprocess
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

L = runpy.run_path(str(Path(__file__).with_name("visual_location_observations.py")))
A = runpy.run_path(str(Path(__file__).with_name("prepare_spatial_annotation_review.py")))
VERSION = "retained-component-site-audit-1"
FLAGS = {"pixel_truth_verified": False, "admission_allowed": False,
         "automatic_rejection": False, "physical_identity_established": False,
         "mask_precision_verified": False}
SITE_MAP = {"handle_opening": ["handle_opening_center"],
            "handle_body_contacts": ["upper_handle_attachment", "lower_handle_attachment"]}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound_json(path, sha256):
    data = Path(path).read_bytes()
    if len(data) > 2*1024*1024 or hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError("Input hash/size mismatch")
    return json.loads(data)


def box_pixels(box, size):
    if (len(size) != 2 or any(type(n) is not int or not 1 <= n <= 4096 for n in size)
            or not isinstance(box, list) or len(box) != 4
            or any(type(n) is not int or not 0 <= n <= 1000 for n in box)
            or box[0] >= box[2] or box[1] >= box[3]):
        raise ValueError("Invalid full-image normalized box or image size")
    return [box[0]*size[0]/1000, box[1]*size[1]/1000,
            box[2]*size[0]/1000, box[3]*size[1]/1000]


def disk_to_box(point, radius, rectangle):
    if (len(point) != 2 or len(rectangle) != 4
            or any(type(n) not in (int, float) or not math.isfinite(n) for n in point+rectangle+[radius])
            or not 0 < radius <= 32 or rectangle[0] >= rectangle[2] or rectangle[1] >= rectangle[3]):
        raise ValueError("Invalid point/drawing disk or rectangle")
    x, y = point; left, top, right, bottom = rectangle
    dx, dy = max(left-x, 0, x-right), max(top-y, 0, y-bottom)
    distance = math.hypot(dx, dy)
    inside = left <= x <= right and top <= y <= bottom
    margin = min(x-left, right-x, y-top, bottom-y) if inside else -distance
    relation = "disk_contained" if inside and margin >= radius else (
        "disk_intersects_boundary" if distance <= radius else "disk_disjoint")
    return {**FLAGS, "relation": relation, "nominal_inside": inside,
            "signed_margin_pixels": margin, "nominal_distance_to_box_pixels": distance,
            "outside_distance_lower_bound_pixels": max(0, distance-radius),
            "scope": "conditional geometry of an estimated drawing disk; not measured confidence or component truth"}


def maximum_matching(edges):
    @lru_cache(None)
    def visit(index, used):
        if index == len(edges):
            return 0
        result = visit(index+1, used)
        for box in edges[index]:
            if not used & (1 << box):
                result = max(result, 1+visit(index+1, used | (1 << box)))
        return result
    return visit(0, 0)


def site_support(sites, boxes, size):
    if not 1 <= len(sites) <= 4 or len(boxes) > 16:
        raise ValueError("Unbounded site audit")
    ids = [s["id"] for s in sites]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate reviewed site id")
    rectangles = [box_pixels(b, size) for b in boxes]
    if len({tuple(b) for b in boxes}) != len(boxes):
        raise ValueError("Duplicate model boxes")
    rows = []
    for site in sites:
        x, y = site["point"]
        if not 0 <= x < size[0] or not 0 <= y < size[1]:
            raise ValueError("Nominal site outside image")
        relations = [disk_to_box(site["point"], site["uncertainty_pixels"], rectangle) for rectangle in rectangles]
        rows.append({"id": site["id"], "point": site["point"], "drawing_radius_pixels": site["uncertainty_pixels"],
                     "box_relations": relations})
    contained = [[j for j, r in enumerate(s["box_relations"]) if r["relation"] == "disk_contained"] for s in rows]
    possible = [[j for j, r in enumerate(s["box_relations"]) if r["relation"] != "disk_disjoint"] for s in rows]
    box_hits = [sum(j in e for e in possible) for j in range(len(boxes))]
    exclusive_contained = [[j for j in e if box_hits[j] == 1] for e in contained]
    exclusive_possible = [[j for j in e if box_hits[j] == 1] for e in possible]
    return {**FLAGS, "sites": rows, "box_count": len(boxes), "site_count": len(sites),
            "normalized_boxes": boxes, "pixel_boxes": rectangles,
            "box_area_fractions": [(b[2]-b[0])*(b[3]-b[1])/size[0]/size[1] for b in rectangles],
            "nominal_site_covered_count": sum(any(r["nominal_inside"] for r in s["box_relations"]) for s in rows),
            "disk_contained_site_count": sum(bool(e) for e in contained),
            "disk_intersected_site_count": sum(bool(e) for e in possible),
            "maximum_distinct_contained_matching": maximum_matching(contained),
            "maximum_distinct_intersecting_matching": maximum_matching(possible),
            "maximum_exclusive_contained_matching": maximum_matching(exclusive_contained),
            "maximum_exclusive_intersecting_matching": maximum_matching(exclusive_possible),
            "grouped_or_ambiguous_box_indices": [j for j, n in enumerate(box_hits) if n > 1],
            "interpretation": "point support and exclusivity diagnostics only; no physical count, contour precision or identity decision"}


def replay_inventory(row, profile):
    if row["transport_status"] != "completed" or row.get("finish_reason") != "stop":
        return None
    answer = L["validate"](json.loads(row["final_content"]), profile)
    if answer != row["inventory"]:
        raise ValueError("Stored inventory differs from original final JSON")
    return answer


def audit_row(row, profile, annotation):
    result = {**FLAGS, "status": "unavailable", "real_identity_score": None, "site_analysis": None,
              "transport_status": row["transport_status"], "finish_reason": row.get("finish_reason")}
    answer = replay_inventory(row, profile)
    if answer is None:
        return {**result, "reason": "incomplete_transport_or_output; no JSON salvage"}
    presence = answer["target_presence"]["status"]
    component, = profile["components"]
    value = answer["components"][component]
    result.update(target_presence=presence, component=component, component_state=value["state"],
                  original_box_count=len(value["locations"]))
    if presence == "absent":
        return {**result, "status": "not_applicable", "reason": "recorded target absence; no contact/point score"}
    if presence != "present" or value["state"] != "observed":
        return {**result, "reason": "no usable positive location observation"}
    if component not in SITE_MAP or annotation["family"] != "mug":
        raise ValueError("Unreviewed component/family mapping")
    by_id = {p["id"]: p for p in annotation["landmarks"]}
    sites = [by_id[name] for name in SITE_MAP[component]]
    boxes = [location["box"] for location in value["locations"]]
    return {**result, "status": "diagnostic", "site_analysis": site_support(sites, boxes, annotation["size"]),
            "reason": "same-image box/drawing-point geometry; no cross-view fit or physical correspondence claim"}


def render_figure(result, annotation, source, model_label):
    width, height = annotation["size"]
    svg = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "width": str(width+440),
                             "height": str(height+44), "viewBox": f"0 0 {width+440} {height+44}"})
    ET.SubElement(svg, "rect", {"width": "100%", "height": "100%", "fill": "#171b22"})
    def text(x, y, value, size=16, color="white"):
        ET.SubElement(svg, "text", {"x": str(x), "y": str(y), "font-family": "Arial", "font-size": str(size), "fill": color}).text = value
    text(12, 27, f"{model_label} / {annotation['display_label']} / {result['component']}", 18)
    ET.SubElement(svg, "image", {"x": "0", "y": "44", "width": str(width), "height": str(height),
        "href": "data:image/png;base64,"+base64.b64encode(source).decode()})
    data = result["site_analysis"]
    for index, (left, top, right, bottom) in enumerate(data["pixel_boxes"]):
        ET.SubElement(svg, "rect", {"x": str(left), "y": str(top+44), "width": str(right-left), "height": str(bottom-top),
            "fill": "none", "stroke": "#00ffff", "stroke-width": "1.5"})
        text(left+2, top+58, f"b{index}", 12, "#00ffff")
    for index, site in enumerate(data["sites"]):
        x, y = site["point"]
        ET.SubElement(svg, "circle", {"cx": str(x), "cy": str(y+44), "r": str(site["drawing_radius_pixels"]),
            "fill": "none", "stroke": "#ffe600", "stroke-width": "1"})
        ET.SubElement(svg, "circle", {"cx": str(x), "cy": str(y+44), "r": "1", "fill": "#ffe600"})
        text(x+5, y+39, f"p{index}", 12, "#ffe600")
    y = 80; x = width+14
    for label in ["Cian: boxes originales del modelo", "Amarillo: punto y margen de dibujo", "Sin verdad por píxel o identidad", f"Cajas: {data['box_count']} / sitios: {data['site_count']}",
                  f"Discos contenidos: {data['disk_contained_site_count']}",
                  f"Separación exclusiva (contenida): {data['maximum_exclusive_contained_matching']}",
                  f"Separación exclusiva (posible): {data['maximum_exclusive_intersecting_matching']}",
                  f"Cajas agrupadas/ambiguas: {data['grouped_or_ambiguous_box_indices']}"]:
        text(x, y, label, 15); y += 24
    for i, site in enumerate(data["sites"]):
        text(x, y+12, f"p{i}: {site['id']}", 13, "#ffe600"); y += 38
        for j, relation in enumerate(site["box_relations"]):
            text(x, y, f"b{j}: {relation['relation']}", 13); y += 20
            text(x, y, f"margen {relation['signed_margin_pixels']:.2f}px", 13); y += 23
    return ET.tostring(svg, encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--plan", required=True); parser.add_argument("--report", required=True); parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    report, directory = Path(args.report).resolve(), Path(args.output_dir).resolve()
    if any(not p.is_relative_to(Path.cwd().resolve()) for p in (report, directory)) or report.exists() or directory.exists():
        raise ValueError("Preserve outputs and keep them inside current worktree")
    plan = json.loads(Path(args.plan).read_bytes())
    if plan["protocol"] != VERSION or plan["identity_metrics_allowed"] is not False or len(plan["reports"]) != 4:
        raise ValueError("Wrong protocol/scope or cohort size")
    annotation = bound_json(**plan["annotation"])
    A["validate_document"](annotation)
    reviews = [bound_json(**r) for r in plan["human_reviews"]]
    if reviews[-1]["image_2_full_mask_use"] != "excluded from identity measurement and calibration until metal/shadow ambiguity and pose policy are resolved":
        raise ValueError("Preserve disputed B mask exclusion")
    by_hash = {r["sha256"]: r for r in annotation["rows"]}
    source_bytes = {sha: A["load_source"](row) for sha, row in by_hash.items()}
    results, figures = [], []
    for cohort in plan["reports"]:
        raw = bound_json(**cohort["raw"]); profile = bound_json(**cohort["profile"])
        L["validate_profile"](profile)
        if raw["inventory_protocol"] != L["VERSION"] or raw["component_profile_sha256"] != cohort["profile"]["sha256"] or len(raw["rows"]) != 3:
            raise ValueError("Archived profile/protocol mismatch or unbounded rows")
        for row in raw["rows"]:
            ann = by_hash[row["sha256"]]
            if digest(row["path"]) != row["sha256"]:
                raise ValueError("Original PNG changed")
            result = audit_row(row, profile, ann)
            if replay_inventory(row, profile) is not None and L["coverage"](row["inventory"], profile) != row["component_coverage"]:
                raise ValueError("Original coverage replay mismatch")
            result.update(model_id=cohort["model_id"], image_id=ann["id"], image_sha256=row["sha256"],
                          source_case_id=row["source_case_id"], raw_report_sha256=cohort["raw"]["sha256"],
                          request_sha256=row["request_sha256"], final_content_sha256=hashlib.sha256(row["final_content"].encode()).hexdigest())
            if result["site_analysis"] is not None:
                name = f"{cohort['model_id']}-{result['component']}-{ann['id']}.svg"
                data = render_figure(result, ann, source_bytes[ann["sha256"]], cohort["model_label"])
                result.update(svg_path=str(directory/name), svg_sha256=hashlib.sha256(data).hexdigest())
                figures.append((name, data))
            results.append(result)
    directory.mkdir(parents=True)
    for name, data in figures:
        with (directory/name).open("xb") as stream: stream.write(data)
    output = {"protocol": VERSION, **FLAGS, "execution_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "script_sha256": digest(__file__), "plan_sha256": digest(args.plan), "annotation_sha256": plan["annotation"]["sha256"],
              "human_review_sha256s": [r["sha256"] for r in plan["human_reviews"]], "rows": results,
              "archived_rows_replayed": len(results), "same_image_site_diagnostics": sum(r["site_analysis"] is not None for r in results),
              "not_applicable_rows": sum(r["status"] == "not_applicable" for r in results),
              "site_mapping": SITE_MAP, "drawing_uncertainty": "estimated 3px disk, not a statistical interval or ground-truth bound",
              "coordinate_mapping": "x*width/1000,y*height/1000 continuous extents; no rounding/clamping or added box uncertainty",
              "real_identity_comparisons": 0, "cross_view_transform_estimates": 0, "vlm_requests": 0, "generation_requests": 0,
              "scope": "retained localization diagnostics only; no segmentation accuracy, physical counts or candidate promotion"}
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("x", encoding="utf-8") as stream: stream.write(json.dumps(output, ensure_ascii=False, allow_nan=False, indent=2)+"\n")
    print(json.dumps({"archived_rows": len(results), "site_diagnostics": output["same_image_site_diagnostics"],
                      "not_applicable": output["not_applicable_rows"], "svg_figures": len(figures), "vlm_requests": 0}))


if __name__ == "__main__":
    main()
