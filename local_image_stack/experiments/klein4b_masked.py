"""Offline preparation only; no dispatch, model imports or active template edits."""
from pathlib import PurePosixPath

import numpy as np
from PIL import Image

from .klein4b import Reference
from .klein4b_graph import prepare_graph


def prepare_masked_graph(manifest, prompt, seed, source_image, mask_image):
    mask = mask_image.replace("\\", "/")
    path = PurePosixPath(mask)
    if (not mask or path.is_absolute() or ".." in path.parts or ":" in mask
            or path.suffix.lower() != ".png" or mask == source_image.replace("\\", "/")):
        raise ValueError("Mask requires a distinct relative Comfy PNG filename")
    base = prepare_graph(manifest, prompt, seed, "512x512", (Reference(source_image, "identity_reference"),))
    graph = base["graph"]
    graph["10"] = {"class_type": "VAEEncodeForInpaint", "inputs": {
        "pixels": ["20", 0], "vae": ["3", 0], "mask": ["30", 0], "grow_mask_by": 0}}
    graph["30"] = {"class_type": "LoadImageMask", "inputs": {"image": mask, "channel": "red"}}
    graph["31"] = {"class_type": "ImageCompositeMasked", "inputs": {
        "destination": ["20", 0], "source": ["12", 0], "mask": ["30", 0],
        "x": 0, "y": 0, "resize_source": False}}
    graph["13"]["inputs"].update(images=["31", 0], filename_prefix="MPT_MASKED_CONTROL_KLEIN4B")
    # No legacy bridge payload: submitting it would silently run an unmasked edit.
    return {"protocol": "klein4b-masked-preparation-1", "graph": graph,
            "dispatch_allowed": False, "runtime_validated": False}


def validate_live_links(graph, node_contracts):
    if not isinstance(graph, dict) or not graph:
        raise ValueError("Expected graph")
    dependencies, links = {}, 0
    widgets = {"INT": (int,), "FLOAT": (int, float), "BOOLEAN": (bool,), "STRING": (str,), "COMBO": (str,)}
    for key, node in graph.items():
        contract = node_contracts.get(node.get("class_type"))
        if contract is None:
            raise ValueError("Node class not in live contracts")
        inputs = node.get("inputs", {})
        required, optional = contract["required"], contract["optional"]
        if not set(required) <= set(inputs) or set(inputs) - (set(required) | set(optional)):
            raise ValueError("Missing or unknown node input")
        dependencies[key] = []
        for name, value in inputs.items():
            expected = (required | optional)[name]
            if isinstance(value, list):
                if (len(value) != 2 or value[0] not in graph or type(value[1]) is not int or value[1] < 0):
                    raise ValueError("Broken output link")
                outputs = node_contracts[graph[value[0]]["class_type"]]["output"]
                if value[1] >= len(outputs) or outputs[value[1]] != expected:
                    raise ValueError("Output slot/type mismatch")
                dependencies[key].append(value[0]); links += 1
            elif expected not in widgets or type(value) not in widgets[expected]:
                raise ValueError("Literal input type mismatch")
    done, active = set(), set()

    def visit(key):
        if key in active:
            raise ValueError("Graph cycle")
        if key in done:
            return
        active.add(key)
        for parent in dependencies[key]:
            visit(parent)
        active.remove(key); done.add(key)

    for key in graph:
        visit(key)
    return {"nodes_checked": len(graph), "typed_links_checked": links,
            "input_file_admission_checked": False, "gpu_execution_validated": False}


def inspect_mask(path):
    with Image.open(path) as image:
        if image.format != "PNG" or image.mode != "L" or image.size != (512, 512):
            raise ValueError("Mask must be a 512x512 grayscale PNG")
        values = set(np.unique(np.array(image)))
        if values != {0, 255}:
            raise ValueError("Mask must contain black and white only")
        return {"size": [512, 512], "mode": "L", "white_pixels": image.histogram()[255],
                "bounds_exclusive": list(image.getbbox()), "white_means_edit": True,
                "pixel_truth_verified": False}


def check_masked_pixels(reference, candidate, mask):
    inspect_mask(mask)
    arrays = []
    for path in [reference, candidate]:
        with Image.open(path) as image:
            if image.format != "PNG" or image.mode != "RGB" or image.size != (512, 512):
                raise ValueError("Source/candidate require aligned 512x512 RGB PNGs")
            arrays.append(np.array(image))
    with Image.open(mask) as image:
        editable = np.array(image) == 255
    changed = np.any(arrays[0] != arrays[1], axis=-1)
    outside = int(np.count_nonzero(changed & ~editable))
    return {"outside_changed_pixels": outside, "inside_changed_pixels": int(np.count_nonzero(changed & editable)),
            "outside_pixels_preserved": outside == 0, "structural_negative_validated": False,
            "human_review_required": True, "admission_allowed": False}
