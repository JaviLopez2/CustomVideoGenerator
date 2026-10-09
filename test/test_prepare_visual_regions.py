"""Pixel/provenance/coverage regressions; no model, network or GPU."""
import hashlib
import json
from pathlib import Path

from PIL import Image, PngImagePlugin
import pytest

from scripts import prepare_visual_regions as regions


def source(tmp_path, mode="RGB", name="source.png", **save_options):
    path = tmp_path / name
    im = Image.new(mode, (5, 4))
    for y in range(4):
        for x in range(5):
            pixel = (10 + x, 20 + y, 30 + x + y)
            im.putpixel((x, y), (*pixel, 100 + x + y) if mode == "RGBA" else pixel)
    im.save(path, **save_options)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size": [5, 4]}


def plan(src, box=None, required_box=None, margin=0):
    row = {"id": "region0", "source": src, "box": box or [1, 1, 4, 3]}
    if required_box is not None:
        row["required_box"] = required_box
    return {"protocol": "visual-region-preparation-plan-1", "margin_pixels": margin, "regions": [row]}


@pytest.mark.parametrize("mode", ["RGB", "RGBA"])
def test_native_pixels_mode_and_source_binding_are_preserved(tmp_path, mode):
    src = source(tmp_path, mode)
    out = tmp_path / "out"
    result = regions.prepare(plan(src), out, workspace_root=tmp_path)
    row = result["regions"][0]
    with Image.open(row["crop"]["path"]) as image:
        assert image.size == (3, 2) and image.mode == mode
        expected = [(11, 21, 32), (12, 21, 33), (13, 21, 34),
                    (11, 22, 33), (12, 22, 34), (13, 22, 35)]
        if mode == "RGBA":
            expected = [(*rgb, a) for rgb, a in zip(expected, [102, 103, 104, 103, 104, 105])]
        assert [image.getpixel((x, y)) for y in range(image.height) for x in range(image.width)] == expected
    assert row["source"] == src and row["pixel_subset_verified"]
    assert row["coverage_relation"] == "not_declared"
    assert row["whole_declared_region_eligible"] is False
    assert row["semantic_coverage_review"] == "pending"
    assert result["admission_allowed"] is False and result["physical_identity_established"] is False
    assert json.loads((out / "manifest.json").read_text(encoding="utf-8")) == result
    assert hashlib.sha256(Path(row["crop"]["path"]).read_bytes()).hexdigest() == row["crop"]["sha256"]


@pytest.mark.parametrize("box,relation,eligible", [
    ([1, 1, 4, 3], "contained", True),
    ([2, 1, 4, 3], "partial", False),
    ([0, 0, 1, 1], "disjoint", False),
])
def test_declared_box_coverage_is_geometry_only(tmp_path, box, relation, eligible):
    result = regions.prepare(plan(source(tmp_path), box, [1, 1, 4, 3]), tmp_path / "out", workspace_root=tmp_path)
    row = result["regions"][0]
    assert row["coverage_relation"] == relation and row["whole_declared_region_eligible"] is eligible
    assert row["semantic_coverage_review"] == "pending" and not result["admission_allowed"]


def test_margin_is_clipped_but_requested_roi_never_silently_clipped(tmp_path):
    result = regions.prepare(plan(source(tmp_path), [0, 0, 2, 2], [0, 0, 2, 2], 1), tmp_path / "out", workspace_root=tmp_path)
    row = result["regions"][0]
    assert row["requested_box"] == [0, 0, 2, 2] and row["effective_box"] == [0, 0, 3, 3]
    assert row["margin_clipped"] and row["crop"]["size"] == [3, 3]


@pytest.mark.parametrize("box", [[0, 0, 0, 2], [-1, 0, 2, 2], [0, 0, 6, 2], [3, 0, 2, 2],
                                [0.0, 0, 2, 2], [False, 0, 2, 2], [0, 0, 2]])
def test_bad_roi_fails_before_any_output(tmp_path, box):
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        regions.prepare(plan(source(tmp_path), box), out, workspace_root=tmp_path)
    assert not out.exists()


@pytest.mark.parametrize("margin", [-1, True, 1.0, 4097])
def test_bad_margin_is_not_implicitly_converted(tmp_path, margin):
    with pytest.raises(ValueError):
        regions.prepare(plan(source(tmp_path), margin=margin), tmp_path / "out", workspace_root=tmp_path)


@pytest.mark.parametrize("change", ["hash", "dimensions", "bool_dimensions", "unsupported_format"])
def test_invalid_source_is_not_admitted(tmp_path, change):
    src = source(tmp_path, name="source.jpg" if change == "unsupported_format" else "source.png")
    if change == "hash":
        src["sha256"] = "a" * 64
    elif change == "dimensions":
        src["size"] = [6, 4]
    elif change == "bool_dimensions":
        src["size"] = [True, 4]
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        regions.prepare(plan(src), out, workspace_root=tmp_path)
    assert not out.exists()


def test_text_metadata_is_not_copied_to_crop(tmp_path):
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private_marker", "not-for-derived-image")
    result = regions.prepare(plan(source(tmp_path, pnginfo=metadata)), tmp_path / "out", workspace_root=tmp_path)
    with Image.open(result["regions"][0]["crop"]["path"]) as image:
        assert "private_marker" not in image.info


def test_mutating_input_cannot_rewrite_returned_source_provenance(tmp_path):
    src = source(tmp_path)
    out = tmp_path / "out"
    result = regions.prepare(plan(src), out, workspace_root=tmp_path)
    src["size"][0] = 999
    assert result["regions"][0]["source"]["size"] == [5, 4]
    assert json.loads((out / "manifest.json").read_text(encoding="utf-8")) == result


def test_unsupported_color_profile_cannot_be_silently_dropped(tmp_path):
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        regions.prepare(plan(source(tmp_path, icc_profile=b"profile-for-test")), out, workspace_root=tmp_path)
    assert not out.exists()


def test_rgb_transparency_cannot_be_silently_dropped(tmp_path):
    src = source(tmp_path, transparency=(11, 21, 32))
    with Image.open(src["path"]) as image:
        assert image.mode == "RGB"
        assert image.convert("RGBA").getpixel((1, 1)) == (11, 21, 32, 0)
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        regions.prepare(plan(src), out, workspace_root=tmp_path)
    assert not out.exists()


def test_batch_preflight_failure_leaves_zero_partial_files(tmp_path):
    src = source(tmp_path)
    spec = plan(src)
    spec["regions"].append({"id": "bad", "source": {**src, "sha256": "b" * 64}, "box": [1, 1, 3, 3]})
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        regions.prepare(spec, out, workspace_root=tmp_path)
    assert not out.exists()


def test_existing_outputs_are_never_overwritten(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    marker = out / "keep.txt"
    marker.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError):
        regions.prepare(plan(source(tmp_path)), out, workspace_root=tmp_path)
    assert marker.read_text(encoding="utf-8") == "existing" and list(out.iterdir()) == [marker]


def test_output_scope_cannot_escape_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    out = tmp_path / "outside"
    with pytest.raises(ValueError):
        regions.prepare(plan(source(workspace)), out, workspace_root=workspace)
    assert not out.exists()


@pytest.mark.parametrize("change", ["duplicate_ids", "unknown_fields", "bad_required_box", "too_many"])
def test_ambiguous_plan_is_rejected(tmp_path, change):
    spec = plan(source(tmp_path))
    if change == "duplicate_ids":
        spec["regions"].append(dict(spec["regions"][0]))
    elif change == "unknown_fields":
        spec["regions"][0]["unexpected"] = True
    elif change == "bad_required_box":
        spec["regions"][0]["required_box"] = [0, 0, 9, 9]
    else:
        spec["regions"] = [{**spec["regions"][0], "id": str(i)} for i in range(17)]
    with pytest.raises(ValueError):
        regions.prepare(spec, tmp_path / "out", workspace_root=tmp_path)
