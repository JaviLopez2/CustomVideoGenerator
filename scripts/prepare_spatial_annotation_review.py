"""Validate manual drafts and render local review assets; no identity measurements."""
import argparse
import base64
import hashlib
import html
import io
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

VERSION = "retained-spatial-annotation-draft-1"
FLAGS = {"pixel_truth_verified": False, "admission_allowed": False,
         "physical_identity_established": False, "eligible_for_identity_metrics": False}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value)


def point(value, size):
    if not isinstance(value, list) or len(value) != 2 or any(type(n) is not int for n in value):
        raise ValueError("Coordinates must be integer pixel [x,y]")
    if not (0 <= value[0] < size[0] and 0 <= value[1] < size[1]):
        raise ValueError("Point outside original image")


def intersects(a, b, c, d):
    def orient(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0])
    def on(p, q, r):
        return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
    x, y, z, w = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    if ((x > 0 and y < 0) or (x < 0 and y > 0)) and ((z > 0 and w < 0) or (z < 0 and w > 0)):
        return True
    return any((v == 0 and on(p, q, r)) for v, p, q, r in
               ((x, a, c, b), (y, a, d, b), (z, c, a, d), (w, c, b, d)))


def validate_ring(ring, size):
    if not isinstance(ring, list) or not 3 <= len(ring) <= 512:
        raise ValueError("Polygon needs 3..512 vertices")
    for value in ring:
        point(value, size)
    if len({tuple(value) for value in ring}) != len(ring):
        raise ValueError("Duplicate polygon vertices; closure is implicit")
    edges = list(zip(ring, ring[1:]+ring[:1]))
    area = sum(a[0]*b[1]-b[0]*a[1] for a, b in edges)
    if area == 0:
        raise ValueError("Degenerate polygon")
    for i, (a, b) in enumerate(edges):
        for j in range(i+1, len(edges)):
            if j == i+1 or i == 0 and j == len(edges)-1:
                continue
            if intersects(a, b, *edges[j]):
                raise ValueError("Self-intersecting polygon")


def polygon_mask(ring, size):
    validate_ring(ring, size)
    mask = Image.new("L", tuple(size), 0)
    ImageDraw.Draw(mask).polygon([tuple(value) for value in ring], fill=255)
    return mask


def rasterize(row):
    size = row["size"]
    if not isinstance(size, list) or len(size) != 2 or any(type(n) is not int or not 1 <= n <= 4096 for n in size):
        raise ValueError("Invalid image size")
    if row.get("independent_review_status") != "pending":
        raise ValueError("This protocol accepts assistant drafts pending independent region review only")
    uncertainty = row["boundary_uncertainty_pixels"]
    if type(uncertainty) is not int or not 1 <= uncertainty <= 32:
        raise ValueError("Boundary uncertainty is an estimate in1..32pixels, not exact truth")
    outer = polygon_mask(row["outer"], size)
    union = Image.new("L", tuple(size))
    holes = {}
    if len(row["holes"]) > 16 or len(row["landmarks"]) > 64:
        raise ValueError("Unbounded annotation")
    for item in row["holes"]:
        name = item["id"]
        if not identifier(name) or name == "foreground" or name in holes:
            raise ValueError("Invalid or duplicate hole id")
        hole = polygon_mask(item["polygon"], size)
        if ImageChops.subtract(hole, outer).getbbox():
            raise ValueError("Annotated hole outside outer polygon")
        if ImageChops.multiply(hole, union).getbbox():
            raise ValueError("Annotated holes overlap")
        holes[name] = hole
        union = ImageChops.lighter(hole, union)
    mask = ImageChops.subtract(outer, union)
    names = set()
    for item in row["landmarks"]:
        if item.get("physical_correspondence_established", False) is not False:
            raise ValueError("Draft landmark cannot claim certified physical correspondence")
        name = item["id"]
        if not identifier(name) or name in names:
            raise ValueError("Invalid or duplicate landmark id")
        names.add(name)
        point(item["point"], size)
        uncertainty = item["uncertainty_pixels"]
        if type(uncertainty) is not int or not 1 <= uncertainty <= 32:
            raise ValueError("Invalid landmark uncertainty estimate")
        region = mask if item["region"] == "foreground" else holes.get(item["region"])
        if region is None or not region.getpixel(tuple(item["point"])):
            raise ValueError("Nominal landmark outside declared annotation region")
    return mask, {**FLAGS, "independent_review_status": "pending", "mask_bbox_pixels": list(mask.getbbox()),
                  "annotated_foreground_pixels": mask.histogram()[255], "holes_annotated": len(holes),
                  "landmarks_annotated": len(names), "mask_pixel_sha256": digest(mask.tobytes()),
                  "interpretation": "raster/region consistency only; no semantic mask or part truth verified"}


def validate_document(document):
    if document.get("protocol") != VERSION or document.get("annotation_source") != "assistant_manual_draft":
        raise ValueError("Unknown annotation provenance or protocol")
    if document.get("independent_review_status") != "pending":
        raise ValueError("Draft document must remain pending independent region review")
    if any(document.get(name, False) is not False for name in FLAGS):
        raise ValueError("Manual draft cannot claim physical truth or metric eligibility")
    if not 1 <= len(document["rows"]) <= 16:
        raise ValueError("Unbounded annotation rows")
    names, hashes = set(), set()
    for row in document["rows"]:
        if not identifier(row["id"]) or row["id"] in names:
            raise ValueError("Invalid or duplicate image id")
        if not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) or row["sha256"] in hashes:
            raise ValueError("Invalid or duplicate image hash")
        names.add(row["id"]); hashes.add(row["sha256"])
        rasterize(row)


def load_source(row):
    data = Path(row["path"]).read_bytes()
    if len(data) > 16*1024*1024 or digest(data) != row["sha256"]:
        raise ValueError("Original image hash/size mismatch")
    with Image.open(io.BytesIO(data)) as image:
        if image.format != "PNG" or list(image.size) != row["size"]:
            raise ValueError("Declared image size/format mismatch")
    return data


def preserve_outputs(report, directory):
    if Path(report).exists() or Path(directory).exists():
        raise ValueError("Preserve existing review artifacts")


def svg_for(row, source):
    width, height = row["size"]
    svg = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "viewBox": f"0 0 {width} {height}",
        "width": str(width), "height": str(height), "data-full": f"0 0 {width} {height}",
        "data-roi": " ".join(str(n) for n in row["review_viewbox"]), "role": "img"})
    ET.SubElement(svg, "title").text = "Assistant manual draft; pending independent region review"
    ET.SubElement(svg, "image", {"width": str(width), "height": str(height),
        "href": "data:image/png;base64,"+base64.b64encode(source).decode()})
    def polygon(ring, color, css):
        ET.SubElement(svg, "polygon", {"points": " ".join(f"{x},{y}" for x, y in ring), "fill": "none",
            "stroke": color, "stroke-width": "1.5", "class": css})
    polygon(row["outer"], "#00ffff", "outer")
    for item in row["holes"]:
        polygon(item["polygon"], "#ff70e0", "hole")
    for i, item in enumerate(row["landmarks"], 1):
        x, y = item["point"]
        ET.SubElement(svg, "circle", {"cx": str(x), "cy": str(y), "r": str(item["uncertainty_pixels"]),
            "fill": "none", "stroke": "#ffe600", "stroke-width": "1", "class": "landmark"})
        ET.SubElement(svg, "circle", {"cx": str(x), "cy": str(y), "r": "1.5", "fill": "#ffe600", "class": "landmark"})
        ET.SubElement(svg, "text", {"x": str(x+5), "y": str(y-5), "fill": "#ffe600",
            "stroke": "#171b22", "stroke-width": "0.5", "font-size": "10", "class": "landmark"}).text = str(i)
    return svg


def review_board(rows, figures):
    cards = []
    for row, svg in zip(rows, figures):
        svg.set("viewBox", svg.get("data-roi"))
        legend = "".join(f"<li>{html.escape(item['id'])}: {item['point']} ±{item['uncertainty_pixels']}px</li>"
                         for i, item in enumerate(row["landmarks"], 1))
        cards.append(f"<article><h2>{html.escape(row['display_label'])}</h2>"
            f"<p>{html.escape(row['id'])} · {row['sha256'][:16]} · borde ±{row['boundary_uncertainty_pixels']}px (estimación)</p>"
            "<button onclick=\"const s=this.nextElementSibling;s.setAttribute('viewBox',s.getAttribute('viewBox')===s.dataset.full?s.dataset.roi:s.dataset.full)\">Objeto / contexto completo</button>"
            +ET.tostring(svg, encoding="unicode")+f"<ol>{legend}</ol></article>")
    return """<!doctype html><html lang="es"><meta charset="utf-8"><title>MPT: borradores espaciales</title>
<style>body{background:#171b22;color:#eee;font:16px system-ui;margin:24px;max-width:1400px}h1{font-size:26px}header{max-width:1000px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:20px}article{background:#242b35;padding:16px;border-radius:8px}h2{font-size:20px}svg{width:100%;height:440px;display:block;background:#101318;margin-top:8px}li{font-size:13px}button{padding:8px;margin:4px;background:#dae7ef;border:0;border-radius:4px;cursor:pointer}.hide-outer .outer,.hide-holes .hole,.hide-points .landmark{display:none}</style>
<header><h1>Contornos y puntos: borrador del asistente</h1>
<p>Sin revisión independiente de regiones. No son anotaciones gold ni aprueban identidad. La evaluación A/B/C anterior permanece separada.</p>
<p>Cian: contorno exterior. Rosa: hueco de fondo. Amarillo: puntos y margen de dibujo estimado; no intervalo estadístico. La boca interior de la taza permanece dentro de la apariencia del objeto.</p>
<p>Revisar que el borde cubra el objeto visible completo, excluya sombras y que huecos/puntos caigan en su sitio. Los nombres no certifican correspondencia física entre perspectivas.</p>
<button onclick="document.body.classList.toggle('hide-outer')">Contornos</button><button onclick="document.body.classList.toggle('hide-holes')">Huecos</button><button onclick="document.body.classList.toggle('hide-points')">Puntos</button>
<p>Solo inspección local; estos botones no guardan una aprobación ni envían datos.</p></header><main>"""+"".join(cards)+"</main></html>"


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    report, destination = Path(args.report).resolve(), Path(args.output_dir).resolve()
    for path in (report, destination):
        if not path.is_relative_to(Path.cwd().resolve()):
            raise ValueError("Outputs must stay inside current worktree")
    preserve_outputs(report, destination)
    data = Path(args.annotations).read_bytes()
    if len(data) > 1024*1024:
        raise ValueError("Unbounded annotation file")
    document = json.loads(data)
    validate_document(document)
    sources = [load_source(row) for row in document["rows"]]
    destination.mkdir(parents=True)
    results, figures = [], []
    for row, source in zip(document["rows"], sources):
        mask, stats = rasterize(row)
        mask_path = destination / f"{row['id']}-mask.png"
        mask.save(mask_path)
        svg = svg_for(row, source)
        svg_path = destination / f"{row['id']}.svg"
        svg_path.write_bytes(ET.tostring(svg, encoding="utf-8", xml_declaration=True))
        figures.append(svg)
        results.append({"id": row["id"], "image_sha256": row["sha256"], **stats,
            "mask_path": str(mask_path), "mask_png_sha256": digest(mask_path.read_bytes()),
            "svg_path": str(svg_path), "svg_sha256": digest(svg_path.read_bytes())})
    board = destination / "review.html"
    board.write_text(review_board(document["rows"], figures), encoding="utf-8")
    result = {"protocol": VERSION, "execution_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "annotation_sha256": digest(data), "script_sha256": digest(Path(__file__).read_bytes()),
        "annotation_source": "assistant_manual_draft", "independent_review_status": "pending", **FLAGS,
        "rows": results, "board_path": str(board), "board_sha256": digest(board.read_bytes()),
        "generation_requests": 0, "vlm_requests": 0, "identity_comparisons": 0,
        "scope": "raster and provenance validation; source images untouched; no promotion or decision"}
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"report": str(report), "board": str(board), "rows": len(results),
                      "review_status": "pending", "identity_comparisons": 0}))


if __name__ == "__main__":
    main()
