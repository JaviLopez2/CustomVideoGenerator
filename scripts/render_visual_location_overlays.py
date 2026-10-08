"""SVG review figures over unchanged retained pixels; no generation or verdict."""
import argparse
import base64
import json
import runpy
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

L = runpy.run_path(str(Path(__file__).with_name("visual_location_observations.py")))
COLORS = ["#00ffff", "#ffe600", "#ff70e0", "#88ff44"]


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    destination = Path(args.output_dir)
    if destination.exists():
        raise ValueError("Preserve existing figures")
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    profile = L["validate_profile"](json.loads(Path(args.profile).read_text(encoding="utf-8")))
    if report.get("inventory_protocol") != L["VERSION"] or report.get("component_profile_sha256") != L["H"]["digest"](args.profile):
        raise ValueError("Profile/report mismatch")
    figures = []
    for row in report["rows"]:
        if row["transport_status"] != "completed":
            continue
        L["validate"](row["inventory"], profile)
        if L["H"]["digest"](row["path"]) != row["sha256"]:
            raise ValueError("Image changed")
        with Image.open(row["path"]) as image:
            width, height = image.size
        figure_height = max(height + 44, 84 + sum(
            36 + 22 * len(c["locations"]) for c in row["inventory"]["components"].values()))
        svg = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "width": str(width + 420),
            "height": str(figure_height), "viewBox": f"0 0 {width + 420} {figure_height}"})
        ET.SubElement(svg, "rect", {"width": "100%", "height": "100%", "fill": "#171b22"})
        ET.SubElement(svg, "text", {"x": "12", "y": "26", "fill": "white", "font-size": "15"}).text = (
            "Regiones del modelo: sin verificar; no aprueban identidad ni escenas")
        ET.SubElement(svg, "image", {"x": "0", "y": "44", "width": str(width), "height": str(height),
            "href": "data:image/png;base64," + base64.b64encode(Path(row["path"]).read_bytes()).decode()})
        legend_y = 72
        for i, (name, component) in enumerate(row["inventory"]["components"].items()):
            color = COLORS[i % len(COLORS)]
            ET.SubElement(svg, "text", {"x": str(width + 16), "y": str(legend_y), "fill": color,
                "font-size": "14"}).text = f"{name}: {component['state']}"
            legend_y += 24
            for j, location in enumerate(component["locations"]):
                left, top, right, bottom = location["box"]
                ET.SubElement(svg, "rect", {"x": str(left * width / 1000), "y": str(44 + top * height / 1000),
                    "width": str((right - left) * width / 1000), "height": str((bottom - top) * height / 1000),
                    "fill": "none", "stroke": color, "stroke-width": "2"})
                ET.SubElement(svg, "text", {"x": str(left * width / 1000 + 3),
                    "y": str(44 + top * height / 1000 + 14), "fill": color, "font-size": "12"}).text = f"{i + 1}.{j + 1}"
                ET.SubElement(svg, "text", {"x": str(width + 16), "y": str(legend_y), "fill": "#d5dce8",
                    "font-size": "12"}).text = f"{i + 1}.{j + 1} box={location['box']}"
                legend_y += 22
            legend_y += 12
        figures.append((row["sha256"], ET.tostring(svg, encoding="utf-8", xml_declaration=True)))
    destination.mkdir(parents=True)
    index = {"report_sha256": L["H"]["digest"](args.report), "profile_sha256": L["H"]["digest"](args.profile),
             "script_sha256": L["H"]["digest"](__file__), "generation_requests": 0, "pixel_truth_verified": False, "figures": []}
    for sha, data in figures:
        path = destination / f"{sha[:16]}.svg"
        with path.open("xb") as stream:
            stream.write(data)
        index["figures"].append({"image_sha256": sha, "path": str(path.resolve()), "svg_sha256": L["H"]["digest"](path)})
    (destination / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(index))


if __name__ == "__main__":
    main()
