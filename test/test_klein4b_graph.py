"""Real pinned graph contracts, without HTTP, model loading or GPU imports."""

import copy
import json
from pathlib import Path

import pytest

from local_image_stack.experiments.klein4b import Reference
from local_image_stack.experiments.klein4b_graph import prepare_graph, validate_graph


@pytest.fixture
def manifest():
    return json.loads((Path(__file__).parents[1] / "docs/validation/flux-klein-4b-assets.json").read_text())


def test_t2i_binds_seed_dimensions_and_distilled_parameters(manifest):
    result = prepare_graph(manifest, "a physical tile", 123, "768x1376")
    g = result["graph"]
    assert g["4"]["inputs"]["text"] == "a physical tile"
    assert g["7"]["inputs"]["noise_seed"] == 123
    assert g["9"]["inputs"] == {"steps": 4, "width": 768, "height": 1376}
    assert g["10"]["inputs"] == {"width": 768, "height": 1376, "batch_size": 1}
    assert g["6"]["inputs"]["cfg"] == 1.0
    assert not any(n["class_type"] in {"LoadImage", "ReferenceLatent", "FluxKVCache"} for n in g.values())
    assert result["dispatch_allowed"] is False


@pytest.mark.parametrize("count", [1, 2, 3])
def test_edit_chains_exact_ordered_refs_on_both_conditionings(manifest, count):
    refs = tuple(Reference(f"inputs/ref-{i}.png", role) for i, role in enumerate(
        ["identity_reference", "factual_reference", "style_reference"][:count]))
    result = prepare_graph(manifest, "compose the scene", 0, "1024x1024", refs)
    g = result["graph"]
    loads = [n for n in g.values() if n["class_type"] == "LoadImage"]
    assert [n["inputs"]["image"] for n in loads] == [r.image for r in refs]
    assert [n["_meta"]["title"] for n in loads] == [f"Subject Reference {i+1}" for i in range(count)]
    assert sum(n["class_type"] == "ReferenceLatent" for n in g.values()) == count * 2
    for i in range(count):
        offset = i * 5
        assert g[str(23 + offset)]["inputs"]["latent"] == [str(22 + offset), 0]
        assert g[str(24 + offset)]["inputs"]["latent"] == [str(22 + offset), 0]
        assert g[str(23 + offset)]["inputs"]["conditioning"] == (["4", 0] if i == 0 else [str(18 + offset), 0])
        assert g[str(24 + offset)]["inputs"]["conditioning"] == (["5", 0] if i == 0 else [str(19 + offset), 0])
    assert g["6"]["inputs"]["positive"] == [str(23 + (count - 1) * 5), 0]
    assert g["6"]["inputs"]["negative"] == [str(24 + (count - 1) * 5), 0]
    assert "__MPT_REFERENCE_REQUIRED__" not in json.dumps(g)
    assert result["reference_roles"] == [r.role for r in refs]
    assert result["dispatch_allowed"] is False


def test_temporal_graph_preserves_state_contract_and_templates(manifest):
    before = copy.deepcopy(manifest)
    result = prepare_graph(manifest, "a single sheet", 42, "512x512",
                           (Reference("root.png", "continuity_anchor"),),
                           temporal_progression=True, temporal_state="fully developed colors")
    text = result["graph"]["4"]["inputs"]["text"]
    assert "stable root" in text and "MUST advance" in text and "fully developed colors" in text
    assert manifest == before
    again = prepare_graph(manifest, "plain", 1, "512x512")
    assert again["graph"]["4"]["inputs"]["text"] == "plain"


@pytest.mark.parametrize("filename", ["../secret.png", "C:\\image.png", "/image.png", "https://example.org/x.png"])
def test_unstaged_reference_locations_rejected(manifest, filename):
    with pytest.raises(ValueError, match="relative Comfy"):
        prepare_graph(manifest, "scene", 1, "512x512", (Reference(filename, "identity_reference"),))


def test_template_hash_and_binding_enforced(manifest):
    manifest["workflows"]["t2i"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        prepare_graph(manifest, "scene", 1, "512x512")
    manifest["workflows"]["t2i"]["path"] = "local_image_stack/workflows/active.json"
    with pytest.raises(ValueError, match="isolated"):
        prepare_graph(manifest, "scene", 1, "512x512")


@pytest.mark.parametrize("fault", ["broken_link", "cycle", "9b", "kv_cache"])
def test_invalid_graph_is_rejected(manifest, fault):
    graph = prepare_graph(manifest, "scene", 1, "512x512")["graph"]
    if fault == "broken_link":
        graph["6"]["inputs"]["positive"] = ["missing", 0]
    elif fault == "cycle":
        graph["5"]["inputs"]["conditioning"] = ["5", 0]
    elif fault == "9b":
        graph["1"]["inputs"]["unet_name"] = "flux-2-klein-9b-kv-fp8.safetensors"
    else:
        graph["6"]["class_type"] = "FluxKVCache"
    with pytest.raises(ValueError):
        validate_graph(graph)
