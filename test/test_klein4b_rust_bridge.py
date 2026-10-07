"""Exercise the compiled Rust bridge without submitting any Comfy prompt."""

import copy
import json
import os
import subprocess
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from local_image_stack.experiments.klein4b import Reference
from local_image_stack.experiments.klein4b_graph import prepare_graph


@pytest.fixture
def manifest():
    return json.loads((Path(__file__).parents[1] / "docs/validation/flux-klein-4b-assets.json").read_text())


@pytest.fixture
def binary():
    configured = os.environ.get("MPT_KLEIN_BRIDGE_BIN")
    if not configured:
        pytest.skip("Build the experimental bridge and set MPT_KLEIN_BRIDGE_BIN")
    path = Path(configured)
    assert path.is_file(), "Configured experimental Rust binary is missing"
    return path


def native_request(prepared):
    return {**prepared["payload"], "reference_roles": prepared["reference_roles"]}


def run_bridge(binary, tmp_path, payload):
    path = tmp_path / "request.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return subprocess.run([str(binary), "--dry-run", str(path)], capture_output=True, text=True, timeout=15)


@pytest.mark.parametrize("count", [0, 1, 2, 3])
def test_native_rust_payload_equals_offline_python_graph(manifest, binary, tmp_path, count):
    refs = tuple(Reference(f"ref-{i}.png", role) for i, role in enumerate(
        ["identity_reference", "factual_reference", "style_reference"][:count]))
    prepared = prepare_graph(manifest, "compose a single scene", 42, "768x1376", refs)
    result = run_bridge(binary, tmp_path, native_request(prepared))
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert value["dispatch_allowed"] is False
    assert value["comfy_request"]["prompt"] == prepared["graph"]
    assert value["comfy_request"]["client_id"] == "klein4b-preview"


def test_native_temporal_root_keeps_requested_state(manifest, binary, tmp_path):
    prepared = prepare_graph(manifest, "a physical sheet", 0, "512x512",
        (Reference("root.png", "continuity_anchor"),), temporal_progression=True,
        temporal_state="fully developed visible colors")
    result = run_bridge(binary, tmp_path, native_request(prepared))
    assert result.returncode == 0, result.stderr
    graph = json.loads(result.stdout)["comfy_request"]["prompt"]
    assert graph == prepared["graph"]
    assert "MUST advance" in graph["4"]["inputs"]["text"]


def test_native_raw_roles_and_temporal_intent_match_canonical_builder(manifest, binary, tmp_path):
    prepared = prepare_graph(manifest, "a physical sheet", 0, "512x512",
        (Reference("root.png", "continuity_anchor"),), temporal_progression=True,
        temporal_state="fully developed visible colors")
    payload = native_request(prepared)
    payload.update(prompt="a physical sheet", temporal_progression=True, temporal_state="fully developed visible colors")
    result = run_bridge(binary, tmp_path, payload)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["comfy_request"]["prompt"] == prepared["graph"]


def test_preview_http_lists_only_experimental_aliases_and_blocks_dispatch(manifest, binary):
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", 8091)) != 0, "Preview port occupied; preserve existing service"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen([str(binary), "--serve-preview"], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, creationflags=flags)
    try:
        deadline = time.monotonic() + 10
        while True:
            assert process.poll() is None, "Preview process exited before serving"
            try:
                health = json.load(urllib.request.urlopen("http://127.0.0.1:8091/health", timeout=1))
                break
            except urllib.error.URLError:
                assert time.monotonic() < deadline, "Preview startup timeout"
                time.sleep(0.05)
        assert health["gpu_enabled"] is False
        models = json.load(urllib.request.urlopen("http://127.0.0.1:8091/v1/models", timeout=2))
        assert {item["id"] for item in models["data"]} == {"flux-klein-4b-t2i-exp", "flux-klein-4b-edit-exp"}
        prepared = prepare_graph(manifest, "a physical tile", 1, "512x512")
        body = json.dumps(native_request(prepared)).encode()
        preview = urllib.request.Request("http://127.0.0.1:8091/experimental/preview", data=body,
                                         headers={"Content-Type": "application/json"})
        result = json.load(urllib.request.urlopen(preview, timeout=2))
        assert result["dispatch_allowed"] is False
        assert result["comfy_request"]["prompt"] == prepared["graph"]
        blocked = urllib.request.Request("http://127.0.0.1:8091/v1/images/generations", data=body,
                                         headers={"Content-Type": "application/json"})
        with pytest.raises(urllib.error.HTTPError) as failure:
            urllib.request.urlopen(blocked, timeout=2)
        assert failure.value.code == 403
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.mark.parametrize("mutation", ["legacy_alias", "slot_gap", "four_refs", "duplicate", "missing_roles",
                                     "unknown_role", "steps", "guidance", "batch", "seed", "size", "absolute",
                                     "t2i_roles", "temporal_without_root", "temporal_contradiction"])
def test_native_invalid_contracts_fail_before_dispatch(manifest, binary, tmp_path, mutation):
    prepared = prepare_graph(manifest, "single scene", 1, "512x512",
                             (Reference("root.png", "identity_reference"),))
    p = copy.deepcopy(native_request(prepared))
    if mutation == "legacy_alias": p["model"] = "flux-klein-precision"
    elif mutation == "slot_gap": p["reference_image_3"] = "other.png"
    elif mutation == "four_refs": p["reference_image_4"] = "other.png"
    elif mutation == "duplicate": p["reference_image_2"] = "root.png"
    elif mutation == "missing_roles": p.pop("reference_roles")
    elif mutation == "unknown_role": p["reference_roles"] = ["unknown"]
    elif mutation == "steps": p["steps"] = 20
    elif mutation == "guidance": p["guidance"] = 5
    elif mutation == "batch": p["n"] = 2
    elif mutation == "seed": p["seed"] = -1
    elif mutation == "size": p["size"] = "768x1377"
    elif mutation == "absolute": p["reference_image"] = "C:\\private.png"
    elif mutation == "t2i_roles":
        p["model"] = "flux-klein-4b-t2i-exp"
        p.pop("reference_image")
    elif mutation == "temporal_without_root":
        p.update(temporal_progression=True, temporal_state="new state")
    elif mutation == "temporal_contradiction":
        p.update(temporal_progression=True, temporal_state="new state",
                 reference_roles=["continuity_anchor"], prompt="keep all visible content unchanged")
    result = run_bridge(binary, tmp_path, p)
    assert result.returncode != 0
    assert not result.stdout.strip()
