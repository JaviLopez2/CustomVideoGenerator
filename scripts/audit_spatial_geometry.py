"""Reproducible offline CPU probe; correspondences/masks never approve identity."""
import argparse
import base64
import hashlib
import importlib.metadata
import io
import json
import math
import platform
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import label, maximum_filter
from skimage.color import rgb2gray, rgb2hsv
from skimage.feature import SIFT, match_descriptors
from skimage.measure import find_contours, ransac
from skimage.transform import SimilarityTransform, resize

VERSION = "offline-spatial-geometry-audit-1"
ROI_MARGINS = (-8, 0, 8)
SATURATIONS = (0.15, 0.25, 0.35)
MIN_VALUE = 0.35


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def authority(status="uncertain"):
    return {"status": status, "admission_allowed": False, "automatic_rejection": False,
            "physical_identity_established": False, "pixel_truth_verified": False}


def validate_box(box, size):
    if not isinstance(box, list) or len(box) != 4 or any(type(n) is not int for n in box):
        raise ValueError("ROI must contain four integer pixel coordinates")
    left, top, right, bottom = box
    if not (0 <= left < right <= size[0] and 0 <= top < bottom <= size[1]):
        raise ValueError("ROI outside source or empty")
    return box


def load_pixels(record):
    data = Path(record["path"]).read_bytes()
    if len(data) > 16 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError("Image size or hash mismatch")
    with Image.open(io.BytesIO(data)) as image:
        if max(image.size) > 4096:
            raise ValueError("Image too large for bounded audit")
        validate_box(record["roi"], image.size)
        return np.asarray(image.convert("RGB"), dtype=np.uint8).copy()


def registration(source_xy, candidate_xy):
    result = {**authority(), "match_count": len(source_xy), "fit_available": False,
              "inlier_count": 0, "inlier_indices": [], "transform_matrix": None,
              "median_residual_pixels": None}
    if len(source_xy) < 3:
        return {**result, "reason": "insufficient_correspondences"}
    model, inliers = ransac((source_xy, candidate_xy), SimilarityTransform,
                           min_samples=3, residual_threshold=2, max_trials=1000,
                           stop_probability=0.99, rng=0)
    if not model or inliers is None or not np.isfinite(model.params).all():
        return {**result, "reason": "no_finite_similarity_fit"}
    indices = np.flatnonzero(inliers)
    if len(indices) < 3:
        return {**result, "reason": "insufficient_inliers"}
    return {**result, "fit_available": True, "inlier_count": len(indices),
            "inlier_indices": indices.tolist(), "transform_matrix": model.params.tolist(),
            "median_residual_pixels": float(np.median(model.residuals(source_xy, candidate_xy)[inliers])),
            "reason": "local_correspondences_only; neither complete shape nor identity certified"}


def normalize_mask(mask):
    yy, xx = np.nonzero(mask)
    if len(xx) < 16:
        return None
    image = Image.fromarray(mask.astype(np.uint8) * 255)
    image = image.crop(image.getbbox())
    yy, xx = np.nonzero(np.asarray(image))
    eigenvalues, vectors = np.linalg.eigh(np.cov(np.vstack((xx, yy))))
    axis = vectors[:, int(np.argmax(eigenvalues))]
    image = image.rotate(math.degrees(math.atan2(axis[1], axis[0])), expand=True,
                         resample=Image.Resampling.NEAREST)
    image = image.crop(image.getbbox())
    scale = 112 / max(image.size)
    image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                         Image.Resampling.NEAREST)
    canvas = Image.new("L", (128, 128))
    canvas.paste(image, ((128 - image.width) // 2, (128 - image.height) // 2))
    return np.asarray(canvas) > 0


def compare_masks(reference, candidate):
    a, b = normalize_mask(reference), normalize_mask(candidate)
    if a is None or b is None:
        return {**authority("unavailable"), "dice": None, "dilated_dice": None,
                "reason": "empty_or_tiny_threshold_component"}
    def dice(left, right):
        return float(2 * (left & right).sum() / max(1, left.sum() + right.sum()))
    alternatives = (b, np.rot90(b, 2))
    return {**authority(), "dice": max(dice(a, item) for item in alternatives),
            "dilated_dice": max(dice(maximum_filter(a, size=5), maximum_filter(item, size=5))
                                for item in alternatives),
            "reason": "normalized unverified threshold masks; no learned/calibrated decision threshold"}


def reserve_outputs(output, figures):
    if Path(output).exists() or Path(figures).exists():
        raise ValueError("Preserve existing evidence and figures")


def features(rgb, box=None):
    height, width = rgb.shape[:2]
    left, top, right, bottom = box or [0, 0, width, height]
    gray = rgb2gray(rgb[top:bottom, left:right])
    scale = min(1.0, 768 / max(gray.shape)) if box is None else 1.0
    if scale < 1:
        gray = resize(gray, tuple(max(1, round(n * scale)) for n in gray.shape), anti_aliasing=True)
    detector = SIFT()
    try:
        detector.detect_and_extract(gray)
    except RuntimeError as error:
        if "SIFT found no features" not in str(error):
            raise
        return {"xy": np.empty((0, 2)), "descriptors": None, "scale": scale}
    # SIFT positions are (row, col); transforms are Cartesian (x, y).
    return {"xy": detector.positions[:, ::-1] / scale + [left, top],
            "descriptors": detector.descriptors, "scale": scale}


def inside(points, box):
    return ((points[:, 0] >= box[0]) & (points[:, 0] < box[2]) &
            (points[:, 1] >= box[1]) & (points[:, 1] < box[3]))


def match(a, b, source_box, candidate_box):
    pairs = np.empty((0, 2), dtype=int)
    if a["descriptors"] is not None and b["descriptors"] is not None:
        pairs = match_descriptors(a["descriptors"], b["descriptors"],
                                  metric="euclidean", cross_check=True, max_ratio=0.75)
    source, candidate = a["xy"][pairs[:, 0]], b["xy"][pairs[:, 1]]
    result = registration(source, candidate)
    indices = result["inlier_indices"]
    local = inside(source, source_box) & inside(candidate, candidate_box)
    result.update({"reference_feature_count": len(a["xy"]), "candidate_feature_count": len(b["xy"]),
                   "matches_inside_both_manual_rois": int(local.sum()),
                   "inliers_inside_both_manual_rois": int(local[indices].sum()),
                   "source_xy": source.tolist(), "candidate_xy": candidate.tolist(),
                   "feature_image_scales": [a["scale"], b["scale"]]})
    return result


def threshold_masks(rgb, roi):
    left, top, right, bottom = roi
    hsv = rgb2hsv(rgb[top:bottom, left:right])
    masks, stats = [], []
    for saturation in SATURATIONS:
        selected = (hsv[:, :, 1] <= saturation) & (hsv[:, :, 2] >= MIN_VALUE)
        components, count = label(selected, structure=np.ones((3, 3)))
        areas = np.bincount(components.ravel())
        areas[0] = 0
        mask = components == int(np.argmax(areas)) if count and areas.max() >= 16 else np.zeros_like(selected)
        masks.append(mask)
        yy, xx = np.nonzero(mask)
        stats.append({"max_saturation": saturation, "min_value": MIN_VALUE,
                      "threshold_pixels": int(selected.sum()), "component_count": count,
                      "largest_component_pixels": int(mask.sum()),
                      "roi_area_fraction": float(mask.mean()),
                      "selected_bbox_pixels": [int(xx.min()+left), int(yy.min()+top),
                                               int(xx.max()+left+1), int(yy.max()+top+1)] if len(xx) else None,
                      "boundary_touched": bool(mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any()),
                      "semantic_target_verified": False})
    return masks, stats


def contours(svg, mask, color, offset=(0, 0)):
    for contour in find_contours(mask.astype(float), 0.5):
        points = " ".join(f"{x+offset[0]:.2f},{y+offset[1]:.2f}" for y, x in contour)
        ET.SubElement(svg, "polyline", {"points": points, "fill": "none", "stroke": color, "stroke-width": "1.5"})


def figure(record, rgb, masks, stats, destination):
    height, width = rgb.shape[:2]
    svg = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "width": str(width+260),
                             "height": str(height+44), "viewBox": f"0 0 {width+260} {height+44}"})
    ET.SubElement(svg, "rect", {"width": "100%", "height": "100%", "fill": "#171b22"})
    ET.SubElement(svg, "text", {"x": "12", "y": "25", "fill": "white", "font-size": "15"}).text = (
        "CPU masks / assistant ROI: unverified; no identity decision")
    ET.SubElement(svg, "image", {"x": "0", "y": "44", "width": str(width), "height": str(height),
        "href": "data:image/png;base64,"+base64.b64encode(Path(record["path"]).read_bytes()).decode()})
    left, top, right, bottom = record["roi"]
    ET.SubElement(svg, "rect", {"x": str(left), "y": str(top+44), "width": str(right-left),
        "height": str(bottom-top), "fill": "none", "stroke": "white", "stroke-width": "2"})
    for i, (mask, stat, color) in enumerate(zip(masks, stats, ("#00ffff", "#ff70e0", "#ffe600"))):
        contours(svg, mask, color, (left, top+44))
        y = 76+i*190
        ET.SubElement(svg, "text", {"x": str(width+14), "y": str(y), "fill": color, "font-size": "13"}).text = (
            f"S <= {stat['max_saturation']}; pixels={stat['largest_component_pixels']}")
        normalized = normalize_mask(mask)
        if normalized is not None:
            contours(svg, normalized, color, (width+36, y+15))
    path = destination / f"{record['id']}.svg"
    with path.open("xb") as stream:
        stream.write(ET.tostring(svg, encoding="utf-8", xml_declaration=True))
    return {"image_sha256": record["sha256"], "path": str(path.resolve()), "sha256": digest(path)}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--figures", required=True)
    args = parser.parse_args()
    output, destination = Path(args.output).resolve(), Path(args.figures).resolve()
    for path in (output, destination):
        if not path.is_relative_to(Path.cwd().resolve()):
            raise ValueError("Audit outputs must stay in the current worktree")
    reserve_outputs(output, destination)
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    if plan.get("script_sha256") != digest(__file__):
        raise ValueError("Audit script changed since plan was declared")
    if plan.get("protocol") != VERSION or not 2 <= len(plan["images"]) <= 8 or len(plan["comparisons"]) > 12:
        raise ValueError("Unknown or unbounded audit plan")
    records = {record["id"]: record for record in plan["images"]}
    if len(records) != len(plan["images"]) or any(not key.isidentifier() for key in records):
        raise ValueError("Invalid or duplicate image ids")
    pixels = {key: load_pixels(record) for key, record in records.items()}
    started = time.perf_counter()
    feature_sets, masks, images = {}, {}, []
    for key, record in records.items():
        rgb, roi = pixels[key], record["roi"]
        feature_sets[key] = {"full": features(rgb)}
        for margin in ROI_MARGINS:
            box = [max(0, roi[0]-margin), max(0, roi[1]-margin),
                   min(rgb.shape[1], roi[2]+margin), min(rgb.shape[0], roi[3]+margin)]
            validate_box(box, (rgb.shape[1], rgb.shape[0]))
            feature_sets[key][str(margin)] = features(rgb, box)
        row = {"id": key, "path": record["path"], "sha256": record["sha256"], "roi": roi,
               "size": [rgb.shape[1], rgb.shape[0]],
               "feature_counts": {scope: len(item["xy"]) for scope, item in feature_sets[key].items()}}
        if record["family"] == "key":
            masks[key], row["threshold_masks"] = threshold_masks(rgb, roi)
        images.append(row)
    comparisons = []
    for pair in plan["comparisons"]:
        ref, cand = pair["reference"], pair["candidate"]
        row = {**pair, **authority(), "registration": {}}
        for scope in ("full", "-8", "0", "8"):
            row["registration"][scope] = match(feature_sets[ref][scope], feature_sets[cand][scope],
                                                records[ref]["roi"], records[cand]["roi"])
        if ref in masks and cand in masks:
            row["mask_comparisons"] = [{"max_saturation": saturation,
                **compare_masks(masks[ref][i], masks[cand][i])} for i, saturation in enumerate(SATURATIONS)]
        comparisons.append(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True)
    figures = [figure(records[row["id"]], pixels[row["id"]], masks[row["id"]],
                      row["threshold_masks"], destination) for row in images if row["id"] in masks]
    report = {"protocol": VERSION, "execution_head": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True).strip(), "plan_sha256": digest(args.plan),
        "script_sha256": digest(__file__), "python": platform.python_version(),
        "packages": {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "scikit-image", "Pillow")},
        "method": {"sift": "default scikit-image SIFT", "full_image_max_edge": 768,
            "roi_margins_pixels": list(ROI_MARGINS), "cross_check": True, "max_ratio": 0.75,
            "transform": "SimilarityTransform; Cartesian pixel coordinates", "ransac_min_samples": 3,
            "ransac_residual_pixels": 2, "ransac_max_trials": 1000, "ransac_rng": 0,
            "saturations": list(SATURATIONS), "minimum_value": MIN_VALUE,
            "mask_component": "largest 8-connected component >=16px; unverified subject",
            "mask_normalization": "PCA angle, uniform scale 112, center in128; compare180 flip",
            "mask_dilation": "5x5 maximum filter; separate from undilated score"},
        "images": images, "comparisons": comparisons, "figures": figures,
        "local_cpu_elapsed_seconds": time.perf_counter()-started,
        "vlm_requests": 0, "generation_requests": 0, "downloads": 0, **authority(),
        "limitations": ["Manual assistant ROI, not gold segmentation or automated object localization.",
            "Background can generate correspondences inside or outside an ROI.",
            "Missing matches do not prove a changed object; matching points do not prove complete shape.",
            "Color/lighting/perspective affect threshold masks and similarity transforms.",
            "Three human-reviewed pairs are not a calibrated accuracy dataset; labels never enter this script."]}
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    (destination / "index.json").write_text(json.dumps({"report_sha256": digest(output), "figures": figures}, indent=2)+"\n")
    print(json.dumps({"output": str(output), "images": len(images), "comparisons": len(comparisons),
                      "seconds": report["local_cpu_elapsed_seconds"], "status": "uncertain", "generation_requests": 0}))


if __name__ == "__main__":
    main()
