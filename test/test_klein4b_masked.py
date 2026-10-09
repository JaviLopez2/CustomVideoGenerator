"""Mask direction, conservation and actual graph boundaries, without inference."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from local_image_stack.experiments.klein4b import Reference
from local_image_stack.experiments.klein4b_graph import prepare_graph
from local_image_stack.experiments.klein4b_masked import (
    check_masked_pixels, inspect_mask, prepare_masked_graph, validate_live_links,
)


@pytest.fixture
def manifest():
    return json.loads((Path(__file__).parents[1] / "docs/validation/flux-klein-4b-assets.json").read_text())


def test_masked_graph_keeps_existing_conditioning_and_changes_only_target_path(manifest):
    before = copy.deepcopy(manifest)
    base = prepare_graph(manifest, "local cut", 42, "512x512", (Reference("source.png", "identity_reference"),))
    result = prepare_masked_graph(manifest, "local cut", 42, "source.png", "mask.png")
    graph = result["graph"]
    assert result["dispatch_allowed"] is False and result["runtime_validated"] is False
    assert "payload" not in result
    assert result["protocol"] == "klein4b-masked-preparation-1"
    assert set(graph) == set(base["graph"]) | {"30", "31"}
    for key in set(base["graph"]) - {"10", "13"}:
        assert graph[key] == base["graph"][key]
    assert graph["10"]["class_type"] == "VAEEncodeForInpaint"
    assert graph["10"]["inputs"] == {"pixels": ["20", 0], "vae": ["3", 0], "mask": ["30", 0], "grow_mask_by": 0}
    assert graph["30"]["inputs"] == {"image": "mask.png", "channel": "red"}
    assert graph["31"]["inputs"] == {"destination": ["20", 0], "source": ["12", 0], "mask": ["30", 0], "x": 0, "y": 0, "resize_source": False}
    assert graph["13"]["inputs"]["images"] == ["31", 0]
    assert graph["13"]["inputs"]["filename_prefix"] == "MPT_MASKED_CONTROL_KLEIN4B"
    assert manifest == before
    assert prepare_graph(manifest, "local cut", 42, "512x512", (Reference("source.png", "identity_reference"),)) == base


@pytest.mark.parametrize("name", ["../mask.png", "C:\\mask.png", "/mask.png", "https://host/mask.png", "", "mask.jpg", "folder/../../mask.png", "source.png"])
def test_invalid_or_colliding_mask_filename_is_rejected(manifest, name):
    with pytest.raises(ValueError):
        prepare_masked_graph(manifest, "cut", 42, "source.png", name)


@pytest.mark.parametrize("seed", [-1, True])
def test_existing_seed_contract_is_preserved(manifest, seed):
    with pytest.raises(ValueError):
        prepare_masked_graph(manifest, "cut", seed, "source.png", "mask.png")


@pytest.mark.parametrize("fault", ["typed_link", "bad_slot", "missing_input", "unknown_input", "missing_node_class", "cycle"])
def test_live_type_contract_rejects_broken_links_and_cycles(fault):
    graph = {"a": {"class_type": "Mask", "inputs": {}}, "b": {"class_type": "Consumer", "inputs": {"mask": ["a", 0]}}}
    contracts = {"Mask": {"required": {}, "optional": {}, "output": ["MASK"]}, "Consumer": {"required": {"mask": "MASK"}, "optional": {}, "output": ["MASK"]}}
    if fault == "typed_link": contracts["Mask"]["output"] = ["IMAGE"]
    elif fault == "bad_slot": graph["b"]["inputs"]["mask"][1] = True
    elif fault == "missing_input": graph["b"]["inputs"] = {}
    elif fault == "unknown_input": graph["b"]["inputs"]["extra"] = 1
    elif fault == "missing_node_class": del contracts["Mask"]
    else:
        graph["a"]["inputs"]["mask"] = ["b", 0]
        contracts["Mask"]["required"]["mask"] = "MASK"
    with pytest.raises(ValueError): validate_live_links(graph, contracts)


def test_live_contract_reports_structural_success_without_file_or_gpu_admission():
    graph = {"a": {"class_type": "Mask", "inputs": {}}, "b": {"class_type": "Consumer", "inputs": {"mask": ["a", 0]}}}
    contracts = {"Mask": {"required": {}, "optional": {}, "output": ["MASK"]}, "Consumer": {"required": {"mask": "MASK"}, "optional": {}, "output": ["IMAGE"]}}
    result = validate_live_links(graph, contracts)
    assert result == {"nodes_checked": 2, "typed_links_checked": 1, "input_file_admission_checked": False, "gpu_execution_validated": False}


@pytest.mark.parametrize("fault", ["empty", "full", "soft", "alpha", "wrong_size"])
def test_nonbinary_or_invalid_mask_is_rejected(tmp_path, fault):
    image = Image.new("L", (512, 512), 0)
    image.putpixel((338, 354), 255)
    if fault == "empty": image = Image.new("L", image.size, 0)
    elif fault == "full": image = Image.new("L", image.size, 255)
    elif fault == "soft": image.putpixel((338, 354), 128)
    elif fault == "alpha": image = image.convert("RGBA")
    else: image = image.resize((256, 256))
    path = tmp_path / "mask.png"; image.save(path)
    with pytest.raises(ValueError): inspect_mask(path)


def test_binary_mask_reports_editable_white_pixels_without_truth_claim(tmp_path):
    mask = Image.new("L", (512, 512), 0)
    for x in [337, 338, 339]: mask.putpixel((x, 354), 255)
    path = tmp_path / "mask.png"; mask.save(path)
    result = inspect_mask(path)
    assert result["white_pixels"] == 3 and result["bounds_exclusive"] == [337, 354, 340, 355]
    assert result["white_means_edit"] is True and result["pixel_truth_verified"] is False


def test_conservation_oracle_distinguishes_inside_change_outside_drift_and_no_change(tmp_path):
    original = np.zeros((512, 512, 3), dtype=np.uint8)
    changed = original.copy(); changed[354, 338] = [255, 12, 5]
    mask = np.zeros((512, 512), dtype=np.uint8); mask[354, 338] = 255
    source, candidate, mask_path = [tmp_path / n for n in ["source.png", "candidate.png", "mask.png"]]
    Image.fromarray(original).save(source); Image.fromarray(changed).save(candidate); Image.fromarray(mask).save(mask_path)
    first = check_masked_pixels(source, candidate, mask_path)
    assert first["outside_changed_pixels"] == 0 and first["inside_changed_pixels"] == 1
    assert first["outside_pixels_preserved"] is True and first["structural_negative_validated"] is False
    changed[0, 0] = 1; Image.fromarray(changed).save(candidate)
    assert check_masked_pixels(source, candidate, mask_path)["outside_changed_pixels"] == 1
    assert check_masked_pixels(source, source, mask_path)["inside_changed_pixels"] == 0


def test_conservation_oracle_rejects_misaligned_or_alpha_candidate(tmp_path):
    source, candidate, mask = [tmp_path / n for n in ["source.png", "candidate.png", "mask.png"]]
    Image.new("RGB", (512, 512)).save(source)
    image = Image.new("L", (512, 512)); image.putpixel((1, 1), 255); image.save(mask)
    for im in [Image.new("RGB", (256, 256)), Image.new("RGBA", (512, 512))]:
        im.save(candidate)
        with pytest.raises(ValueError): check_masked_pixels(source, candidate, mask)
