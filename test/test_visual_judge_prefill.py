"""Offline checks for independent controls and input provenance."""
import json
import runpy
from pathlib import Path

import pytest
from PIL import Image

D = runpy.run_path(str(Path(__file__).parents[1] / "scripts/diagnose_visual_judge_prefill.py"))


def fixture_inputs(tmp_path):
    path = tmp_path / "full.png"
    crop = tmp_path / "crop.png"
    Image.new("RGB", (16, 16), "red").save(path)
    Image.new("RGB", (8, 8), "red").save(crop)
    sha = D["H"]["digest"](path)
    dataset = {"cases": [{"id": cid, "artifact": str(path), "sha256": sha,
                          "expected_verdict": "PRIVATE_LABEL", "review_reason": "PRIVATE_REVIEW"}
                         for cid in ["valid_cloth_edit", "mpt_t2i_text_contract_768"]]}
    regions = {c["id"]: [{"path": str(crop), "sha256": D["H"]["digest"](crop),
                         "source_sha256": sha, "query": "watch hands"}] for c in dataset["cases"]}
    return dataset, regions


def test_controls_isolate_image_count_and_preserve_blinding(tmp_path):
    dataset, regions = fixture_inputs(tmp_path)
    plan = D["probe_plan"](dataset, regions)
    assert [len(p["images"]) for p in plan] == [0, 1, 1, 2, 1, 1]
    requests = [D["payload"](p) for p in plan]
    serialized = json.dumps(requests)
    for secret in ["PRIVATE_LABEL", "PRIVATE_REVIEW", "expected_count", "tolerance"]:
        assert secret not in serialized
    assert requests[1]["messages"][0]["content"][0] == requests[2]["messages"][0]["content"][0]
    assert all(r["response_format"] == requests[0]["response_format"] for r in requests)


def test_region_parent_is_verified(tmp_path):
    dataset, regions = fixture_inputs(tmp_path)
    regions["valid_cloth_edit"][0]["source_sha256"] = "unrelated"
    with pytest.raises(ValueError):
        D["probe_plan"](dataset, regions)


def test_image_change_is_rejected_before_request(tmp_path):
    dataset, regions = fixture_inputs(tmp_path)
    probe = D["probe_plan"](dataset, regions)[1]
    Path(probe["images"][0]["path"]).write_bytes(b"changed")
    with pytest.raises(ValueError):
        D["payload"](probe)
