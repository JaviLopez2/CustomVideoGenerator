"""Bounded synthetic geometry controls; retained roles are audited without scores."""
import argparse
import hashlib
import importlib.metadata
import json
import math
import runpy
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from skimage.transform import ProjectiveTransform, SimilarityTransform

VERSION = "component-pose-limits-1"
FLAGS = {"admission_allowed": False, "automatic_rejection": False,
         "physical_identity_established": False, "pixel_truth_verified": False}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def coordinates(points, dimensions):
    values = np.asarray(points, dtype=float)
    if values.ndim != 2 or values.shape[1] != dimensions or not 1 <= len(values) <= 64 or not np.isfinite(values).all():
        raise ValueError("Invalid bounded finite coordinates")
    return values


def project(points, rx=0, ry=0, depth=6, focal=600):
    xyz = coordinates(points, 3)
    if not all(math.isfinite(n) for n in (rx, ry, depth, focal)) or depth <= 0 or focal <= 0:
        raise ValueError("Invalid camera parameters")
    x, y = np.deg2rad([rx, ry])
    rotation_x = np.array([[1, 0, 0], [0, np.cos(x), -np.sin(x)], [0, np.sin(x), np.cos(x)]])
    rotation_y = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    camera = xyz @ (rotation_y @ rotation_x).T + [0, 0, depth]
    if np.any(camera[:, 2] <= 1e-9):
        raise ValueError("Point at or behind camera")
    return focal*camera[:, :2]/camera[:, 2, None] + [320, 240]


def fit_diagnostic(source, target, kind, anchors, heldout):
    a, b = coordinates(source, 2), coordinates(target, 2)
    if a.shape != b.shape or kind not in ("similarity", "projective"):
        raise ValueError("Invalid paired geometry or transform")
    indices = anchors + heldout
    if any(type(i) is not int or not 0 <= i < len(a) for i in indices) or len(set(indices)) != len(indices):
        raise ValueError("Anchor/check indices must be unique, disjoint and in bounds")
    result = {**FLAGS, "domain": "synthetic_geometry_only", "kind": kind, "fit_available": False,
              "anchors": anchors, "heldout": heldout, "heldout_count": len(heldout), "matrix": None,
              "anchor_max_residual_pixels": None, "heldout_max_residual_pixels": None,
              "anchor_residuals_pixels": [], "heldout_residuals_pixels": [], "predicted_xy": None}
    minimum = 4 if kind == "projective" else 2
    if len(anchors) < minimum:
        return {**result, "reason": "insufficient_anchors"}
    if kind == "projective" and any(np.linalg.matrix_rank(np.column_stack((p[anchors], np.ones(len(anchors))))) < 3 for p in (a, b)):
        return {**result, "reason": "collinear_anchor_geometry"}
    constructor = ProjectiveTransform if kind == "projective" else SimilarityTransform
    model = constructor.from_estimate(a[anchors], b[anchors])
    if not model or not np.isfinite(model.params).all():
        return {**result, "reason": "no_finite_estimate"}
    prediction = model(a)
    if not np.isfinite(prediction).all():
        return {**result, "reason": "nonfinite_projection"}
    residual = np.linalg.norm(prediction-b, axis=1)
    return {**result, "fit_available": True, "matrix": model.params.tolist(), "predicted_xy": prediction.tolist(),
            "anchor_max_residual_pixels": float(max(residual[anchors])),
            "heldout_max_residual_pixels": float(max(residual[heldout])) if heldout else None,
            "anchor_residuals_pixels": residual[anchors].tolist(), "heldout_residuals_pixels": residual[heldout].tolist(),
            "reason": "synthetic fit only; exact anchors do not certify unused parts or physical identity"}


def distance_interval(a, b, radius_a, radius_b):
    xy = coordinates([a, b], 2)
    if any(not math.isfinite(r) or r < 0 for r in (radius_a, radius_b)):
        raise ValueError("Invalid drawing uncertainty")
    distance = float(np.linalg.norm(xy[0]-xy[1])); radius = radius_a+radius_b
    return [max(0, distance-radius), distance+radius]


def ratio_interval(numerator, denominator):
    for interval in (numerator, denominator):
        if len(interval) != 2 or not all(math.isfinite(n) for n in interval) or not 0 <= interval[0] <= interval[1]:
            raise ValueError("Invalid distance bounds")
    return [numerator[0]/denominator[1], numerator[1]/denominator[0]] if denominator[0] > 0 else None


def audit_roles(document, pairs):
    if document.get("eligible_for_identity_metrics", False) is not False:
        raise ValueError("This audit does not accept real metric eligibility")
    rows = {r["id"]: r for r in document["rows"]}
    result = []
    for left, right in pairs:
        a, b = rows[left], rows[right]
        roles_a = {p["id"] for p in a["landmarks"]}; roles_b = {p["id"] for p in b["landmarks"]}
        result.append({**FLAGS, "source": left, "candidate": right,
                       "shared_nominal_roles": sorted(roles_a & roles_b),
                       "source_only_roles": sorted(roles_a-roles_b), "candidate_only_roles": sorted(roles_b-roles_a),
                       "source_uncertainty_pixels": [p["uncertainty_pixels"] for p in a["landmarks"]],
                       "candidate_uncertainty_pixels": [p["uncertainty_pixels"] for p in b["landmarks"]],
                       "full_mask_use": "excluded_disputed_boundary" if "image_2" in (left, right) else "not_used_unverified_draft",
                       "real_identity_score": None, "real_transform": None,
                       "reason": "nominal label overlap only; reviewed positions do not certify physical correspondences"})
    return result


def read_bound_json(path, expected_hash):
    data = Path(path).read_bytes()
    if len(data) > 2*1024*1024 or hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError("Bound JSON hash/size mismatch")
    return json.loads(data)


def preserve_outputs(report, figure):
    if Path(report).exists() or Path(figure).exists():
        raise ValueError("Preserve existing checkpoint artifacts")


def synthetic_controls(settings):
    plane = coordinates(settings["plane_xyz"], 3)
    if len(plane) != 8 or np.any(plane[:, 2] != 0):
        raise ValueError("Protocol requires eight fixed coplanar synthetic landmarks")
    nonplane = plane.copy(); nonplane[6, 2], nonplane[7, 2] = settings["part_depths"]
    cases = []
    def add(name, source, target, truth, metadata):
        anchors, heldout = [0, 1, 2, 3], list(range(4, len(source)))
        cases.append({"id": name, "domain": "synthetic", "truth_by_construction": truth, **metadata,
                      "source_xy": source.tolist(), "target_xy": target.tolist(),
                      "fits": [fit_diagnostic(source, target, kind, anchors, heldout) for kind in ("similarity", "projective")]})
    xs, ys = settings["rx_degrees"], settings["ry_degrees"]
    if len(xs)*len(ys) > 24 or not all(type(n) in (int, float) and math.isfinite(n) and abs(n) <= 75 for n in xs+ys):
        raise ValueError("Unbounded pose grid")
    for name, xyz in (("plane", plane), ("depth_parts", nonplane)):
        source = project(xyz, depth=settings["camera_depth"], focal=settings["focal_pixels"])
        for rx in xs:
            for ry in ys:
                target = project(xyz, rx, ry, settings["camera_depth"], settings["focal_pixels"])
                add(f"{name}_rx{rx}_ry{ry}", source, target, "same_rigid_synthetic_object",
                    {"model": name, "rx_degrees": rx, "ry_degrees": ry})
    source = project(plane, depth=settings["camera_depth"], focal=settings["focal_pixels"])
    angle = math.radians(settings["in_plane_rotation_degrees"])
    rotation = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    add("in_plane_similarity", source, settings["uniform_scale"]*source@rotation.T+settings["translation_xy"],
        "same_2d_synthetic_geometry", {"model": "plane"})
    target = source.copy(); target[6] += settings["part_displacement_xy"]
    add("deformed_unused_part", source, target, "one_synthetic_check_point_displaced", {"model": "plane"})
    target = source[:4].copy(); target[2] += settings["corner_displacement_xy"]
    add("deformed_four_corners_only", source[:4], target, "one_synthetic_anchor_displaced_no_check_points", {"model": "plane"})
    return cases


def figure(cases):
    svg = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "width": "1400", "height": "930", "viewBox": "0 0 1400 930"})
    ET.SubElement(svg, "rect", {"width": "1400", "height": "930", "fill": "#171b22"})
    def text(x, y, value, size=19, color="white"):
        ET.SubElement(svg, "text", {"x": str(x), "y": str(y), "font-family": "Arial", "font-size": str(size), "fill": color}).text = value
    text(25, 32, "Controles sintéticos: perspectiva, partes y sobreajuste", 28)
    text(25, 65, "Cian: puntos proyectados. Amarillo: predicción del ajuste. Ninguna foto MPT se mide o modifica.")
    selected = [("in_plane_similarity", "similarity", "Rotación en plano + escala uniforme"),
                ("plane_rx0_ry45", "similarity", "Mismo plano inclinado: similitud insuficiente"),
                ("depth_parts_rx0_ry45", "projective", "Partes a distinta profundidad: homografía insuficiente"),
                ("deformed_unused_part", "projective", "Parte deformada fuera de los puntos de ajuste"),
                ("deformed_four_corners_only", "projective", "Cuatro puntos deformados: encaje sin control independiente"),
                ("plane_rx0_ry45", "projective", "Plano conocido: comprobar puntos que no ajustaron el modelo")]
    by_id = {r["id"]: r for r in cases}
    for i, (name, kind, title) in enumerate(selected):
        row = by_id[name]; fit = next(f for f in row["fits"] if f["kind"] == kind)
        left, top = 20+(i%2)*690, 100+(i//2)*275
        ET.SubElement(svg, "rect", {"x": str(left), "y": str(top), "width": "670", "height": "260", "fill": "#242b35"})
        text(left+12, top+28, title, 18)
        a = np.array(row["target_xy"]); b = np.array(fit["predicted_xy"])
        values = np.vstack((a, b)); lower, upper = values.min(axis=0), values.max(axis=0)
        scale = min(540/max(upper[0]-lower[0], 1), 155/max(upper[1]-lower[1], 1))
        center = (lower+upper)/2
        for points, color in ((a, "#00ffff"), (b, "#ffe600")):
            plotted = (points-center)*scale+[left+335, top+137]
            for j, (x, y) in enumerate(plotted):
                ET.SubElement(svg, "circle", {"cx": str(x), "cy": str(y), "r": "5" if color == "#00ffff" else "3", "fill": "none", "stroke": color, "stroke-width": "2"})
                if color == "#00ffff": text(x+7, y-5, str(j), 12)
        error = fit["heldout_max_residual_pixels"]
        label = f"Puntos de control: {fit['heldout_count']}; residuo máx.: {error:.3f} px" if error is not None else "Sin puntos de control: el encaje no verifica otras partes"
        text(left+12, top+245, label, 17, "#c9dde8")
    return ET.tostring(svg, encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--plan", required=True); parser.add_argument("--report", required=True); parser.add_argument("--figure", required=True)
    args = parser.parse_args()
    report, plot = Path(args.report).resolve(), Path(args.figure).resolve()
    if any(not p.is_relative_to(Path.cwd().resolve()) for p in (report, plot)):
        raise ValueError("Outputs must stay in current worktree")
    preserve_outputs(report, plot)
    plan = json.loads(Path(args.plan).read_bytes())
    if plan["protocol"] != VERSION or plan["real_identity_metrics_allowed"] is not False:
        raise ValueError("Wrong protocol or metric scope")
    annotation = read_bound_json(**plan["annotation"])
    reviews = [read_bound_json(**r) for r in plan["human_region_reviews"]]
    if reviews[-1]["image_2_full_mask_use"] != "excluded from identity measurement and calibration until metal/shadow ambiguity and pose policy are resolved":
        raise ValueError("Preserve disputed B mask exclusion")
    validator = runpy.run_path(str(Path(__file__).with_name("prepare_spatial_annotation_review.py")))
    validator["validate_document"](annotation)
    for row in annotation["rows"]: validator["load_source"](row)
    roles = audit_roles(annotation, plan["retained_pairs"])
    cases = synthetic_controls(plan["synthetic"])
    assumed = plan["synthetic_uncertainty"]
    distances = [distance_interval([0, 0], [n, 0], assumed["point_radius_pixels"], assumed["point_radius_pixels"]) for n in assumed["nominal_separations_pixels"]]
    ratios = [ratio_interval(d, assumed["reference_length_interval_pixels"]) for d in distances]
    plot.parent.mkdir(parents=True, exist_ok=True); plot.write_bytes(figure(cases))
    result = {"protocol": VERSION, **FLAGS, "execution_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "plan_sha256": digest(args.plan), "script_sha256": digest(__file__), "annotation_sha256": plan["annotation"]["expected_hash"],
              "human_review_sha256s": [r["expected_hash"] for r in plan["human_region_reviews"]],
              "versions": {n: importlib.metadata.version(n) for n in ("numpy", "scikit-image", "Pillow")},
              "synthetic_settings": plan["synthetic"], "synthetic_controls": cases, "synthetic_case_count": len(cases),
              "synthetic_fit_count": sum(len(c["fits"]) for c in cases), "retained_role_audit": roles,
              "synthetic_uncertainty": {"assumptions": assumed, "distance_intervals_pixels": distances, "ratio_intervals": ratios,
                                        "interpretation": "conditional deterministic bounds, not measured confidence or physical identity"},
              "figure_path": str(plot), "figure_sha256": digest(plot), "real_identity_comparisons": 0,
              "real_transform_estimates": 0, "vlm_requests": 0, "generation_requests": 0,
              "limits": "toy camera/geometry do not recover pose or identity of generated photos; no tolerance calibration or admission"}
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("x", encoding="utf-8") as stream: stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)+"\n")
    print(json.dumps({"synthetic_cases": len(cases), "synthetic_fits": result["synthetic_fit_count"], "retained_pairs_metadata_only": len(roles), "real_identity_comparisons": 0}))


if __name__ == "__main__":
    main()
