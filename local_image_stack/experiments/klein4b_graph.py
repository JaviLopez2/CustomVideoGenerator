"""Materialize experimental Comfy API graphs offline; never dispatch them."""

import copy
import json
from pathlib import Path, PurePosixPath

from .klein4b import ALIASES, FILENAMES, Reference, _verify_file, build_request


WORKFLOWS = Path(__file__).parent / "workflows"
CLASSES = {
    "UNETLoader", "CLIPLoader", "VAELoader", "CLIPTextEncode", "ConditioningZeroOut",
    "CFGGuider", "RandomNoise", "KSamplerSelect", "Flux2Scheduler",
    "EmptyFlux2LatentImage", "SamplerCustomAdvanced", "VAEDecode", "SaveImage",
    "LoadImage", "ImageScaleToTotalPixels", "VAEEncode", "ReferenceLatent",
}


def validate_graph(graph: dict) -> None:
    """Check isolated assets, link integrity and cycles, without loading any node.

    This does not replace Comfy input validation, file admission or GPU testing.
    """
    if not isinstance(graph, dict) or not graph:
        raise ValueError("Expected a nonempty API graph")
    dependencies = {}
    for key, node in graph.items():
        if not isinstance(node, dict) or node.get("class_type") not in CLASSES:
            raise ValueError(f"Unsupported experimental node: {key}")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            raise ValueError(f"Missing inputs: {key}")
        dependencies[key] = []
        for value in inputs.values():
            if isinstance(value, list):
                if (len(value) != 2 or value[0] not in graph or
                        type(value[1]) is not int or value[1] < 0):
                    raise ValueError(f"Broken API link: {key}")
                dependencies[key].append(value[0])
    for loader, field, component in (
        ("UNETLoader", "unet_name", "diffusion_model"),
        ("CLIPLoader", "clip_name", "text_encoder"),
        ("VAELoader", "vae_name", "vae"),
    ):
        names = [n["inputs"].get(field) for n in graph.values() if n["class_type"] == loader]
        if names != [FILENAMES[component]]:
            raise ValueError(f"Expected exactly the declared 4B {loader}")
    visited, active = set(), set()

    def visit(key):
        if key in active:
            raise ValueError("Cycle in API graph")
        if key in visited:
            return
        active.add(key)
        for source in dependencies[key]:
            visit(source)
        active.remove(key)
        visited.add(key)

    for key in graph:
        visit(key)
    if not any(n["class_type"] == "SaveImage" for n in graph.values()):
        raise ValueError("Missing image output")


def prepare_graph(manifest: dict, prompt: str, seed: int, size: str,
                  references: tuple[Reference, ...] = (), **options) -> dict:
    """Bind a pinned local template to validated intent, retaining no demo slots.

    References must be names already staged in Comfy's input directory. Uploads,
    bridge alias registration and service execution are outside this adapter.
    """
    request = build_request(manifest, prompt, seed, size, references, **options)
    for ref in references:
        name = ref.image.replace("\\", "/")
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or ":" in name:
            raise ValueError("Reference must be a relative Comfy input filename")
    mode = ALIASES[request["payload"]["model"]]
    description = request["workflow"]
    filename = f"flux-klein-4b-{mode}-exp.json"
    expected_path = f"local_image_stack/experiments/workflows/{filename}"
    if description.get("path") != expected_path or description.get("format") != "comfyui_api":
        raise ValueError("Expected the isolated API template binding")
    path = WORKFLOWS / filename
    _verify_file(path, description, mode)
    graph = json.loads(path.read_text(encoding="utf-8"))
    validate_graph(graph)
    payload = request["payload"]
    width, height = map(int, size.split("x"))
    graph["4"]["inputs"]["text"] = payload["prompt"]
    graph["7"]["inputs"]["noise_seed"] = seed
    graph["9"]["inputs"].update(steps=4, width=width, height=height)
    graph["10"]["inputs"].update(width=width, height=height, batch_size=1)
    graph["6"]["inputs"]["cfg"] = 1.0
    if references:
        # Five-node block: image -> scale -> encode -> positive/negative reference.
        block = {str(n): graph.pop(str(n)) for n in range(20, 25)}
        positive, negative = ["4", 0], ["5", 0]
        for index, ref in enumerate(references):
            offset = index * 5
            for key, original in block.items():
                node = copy.deepcopy(original)
                for field, value in node["inputs"].items():
                    if isinstance(value, list) and value[0] in block:
                        node["inputs"][field] = [str(int(value[0]) + offset), value[1]]
                graph[str(int(key) + offset)] = node
            image, pos, neg = str(20 + offset), str(23 + offset), str(24 + offset)
            graph[image]["inputs"]["image"] = ref.image.replace("\\", "/")
            # Roles belong in the ordered prompt. Style Reference would invoke
            # the bridge's legacy style_reference_image field and reorder intent.
            graph[image]["_meta"]["title"] = f"Subject Reference {index + 1}"
            graph[pos]["inputs"]["conditioning"] = positive
            graph[neg]["inputs"]["conditioning"] = negative
            positive, negative = [pos, 0], [neg, 0]
        graph["6"]["inputs"].update(positive=positive, negative=negative)
    validate_graph(graph)
    return {**request, "graph": graph, "dispatch_allowed": False}
