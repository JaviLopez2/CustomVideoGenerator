import hashlib
import io
from pathlib import Path
import struct
import zlib

import pytest
from PIL import Image, ImageCms, PngImagePlugin
from scripts import prepare_profiled_visual_inputs as helper


def source(tmp_path, mode="RGB", color=(30, 60, 90), **save_args):
    path = tmp_path / "source.png"
    Image.new(mode, (3, 2), color).save(path, **save_args)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size": [3, 2]}


def row(descriptor, name="source"):
    return {"id": name, "source": descriptor}


def plan(*rows):
    return {"protocol": "profiled-visual-input-plan-1", "background_srgb": [255, 255, 255], "images": list(rows)}


def test_rgb_pixels_and_dimensions_are_preserved_without_copying_private_metadata(tmp_path):
    metadata = PngImagePlugin.PngInfo(); metadata.add_text("prompt", "private fixture text")
    descriptor = source(tmp_path, pnginfo=metadata)
    original = Path(descriptor["path"]).read_bytes()
    record, data = helper.render(row(descriptor))
    with Image.open(io.BytesIO(data)) as image:
        assert image.mode == "RGB" and image.size == (3, 2) and not image.info
        assert image.getpixel((1, 1)) == (30, 60, 90)
    assert record["color_policy"] == "untagged_assumed_srgb"
    assert record["rgb_samples_unchanged"] is True
    assert Path(descriptor["path"]).read_bytes() == original
    assert b"private fixture text" not in data


@pytest.mark.parametrize("alpha,expected", [(0, (255, 255, 255)), (128, (255, 127, 127)), (255, (255, 0, 0))])
def test_declared_white_background_uses_alpha_instead_of_discarding_it(tmp_path, alpha, expected):
    descriptor = source(tmp_path, "RGBA", (255, 0, 0, alpha))
    record, data = helper.render(row(descriptor))
    with Image.open(io.BytesIO(data)) as image:
        assert image.getpixel((0, 0)) == expected
    assert record["alpha_extrema"] == [alpha, alpha]
    assert record["background_srgb"] == [255, 255, 255]
    assert record["spatial_resampling"] is False


def test_embedded_rgb_icc_is_converted_and_alpha_is_separate(tmp_path, monkeypatch):
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    descriptor = source(tmp_path, "RGBA", (255, 0, 0, 128), icc_profile=profile)
    called = []; original = ImageCms.profileToProfile
    def trace(image, *args, **kwargs):
        called.append((image.mode, kwargs["renderingIntent"], kwargs["outputMode"]))
        return original(image, *args, **kwargs)
    monkeypatch.setattr(ImageCms, "profileToProfile", trace)
    record, data = helper.render(row(descriptor))
    assert called == [("RGB", ImageCms.Intent.RELATIVE_COLORIMETRIC, "RGB")]
    assert record["color_policy"] == "embedded_icc_to_srgb_relative_colorimetric"
    assert record["source_icc_sha256"] == hashlib.sha256(profile).hexdigest()
    with Image.open(io.BytesIO(data)) as image:
        assert image.getpixel((0, 0)) == (255, 127, 127) and not image.info


@pytest.mark.parametrize("bad", ["hash", "size", "orientation", "profile", "lab_profile", "gamma", "palette", "transparency"])
def test_unsupported_input_fails_before_creating_any_output(tmp_path, bad):
    save_args = {}
    mode, color = "RGB", (30, 60, 90)
    if bad == "orientation":
        exif = Image.Exif(); exif[274] = 6; save_args["exif"] = exif
    if bad == "profile": save_args["icc_profile"] = b"not an ICC profile"
    if bad == "lab_profile": save_args["icc_profile"] = ImageCms.ImageCmsProfile(ImageCms.createProfile("LAB")).tobytes()
    if bad == "palette": mode, color = "P", 1
    if bad == "transparency": save_args["transparency"] = (30, 60, 90)
    if bad == "gamma":
        metadata = PngImagePlugin.PngInfo(); metadata.add(b"gAMA", (45455).to_bytes(4, "big")); save_args["pnginfo"] = metadata
    descriptor = source(tmp_path, mode, color, **save_args)
    if bad == "hash": descriptor["sha256"] = "0" * 64
    if bad == "size": descriptor["size"] = [2, 3]
    destination = tmp_path / "new-artifacts"
    with pytest.raises(ValueError): helper.prepare(plan(row(descriptor)), destination, workspace_root=tmp_path)
    assert not destination.exists()


def test_second_bad_source_does_not_leave_a_partial_batch(tmp_path):
    descriptor = source(tmp_path)
    bad = {**descriptor, "sha256": "0" * 64}
    destination = tmp_path / "new-artifacts"
    with pytest.raises(ValueError): helper.prepare(plan(row(descriptor, "good"), row(bad, "bad")), destination, workspace_root=tmp_path)
    assert not destination.exists()


@pytest.mark.parametrize("color_type,channels", [(2, 3), (6, 4)])
def test_rgb_and_rgba_sixteen_bit_png_are_rejected_without_silent_precision_loss(tmp_path, color_type, channels):
    def chunk(name, value):
        return struct.pack(">I", len(value)) + name + value + struct.pack(">I", zlib.crc32(name + value))
    header = struct.pack(">IIBBBBB", 2, 1, 16, color_type, 0, 0, 0)
    first = [0x1234, 0x5678, 0x9ABC, 0xFFFF][:channels]
    second = [0x1235, 0x5678, 0x9ABC, 0xFFFF][:channels]
    scanline = b"\x00" + struct.pack(">" + "H" * (channels * 2), *(first + second))
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(scanline)) + chunk(b"IEND", b"")
    path = tmp_path / "rgb16.png"; path.write_bytes(data)
    with Image.open(path) as decoded:
        assert decoded.mode in {"RGB", "RGBA"}  # Mode alone hides lost low bits.
        assert decoded.getpixel((0, 0)) == decoded.getpixel((1, 0))
    descriptor = {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "size": [2, 1]}
    destination = tmp_path / "new-artifacts"
    with pytest.raises(ValueError): helper.prepare(plan(row(descriptor)), destination, workspace_root=tmp_path)
    assert not destination.exists() and path.read_bytes() == data


def test_fresh_batch_and_native_region_helper_can_reconstruct_prepared_png(tmp_path):
    from scripts import prepare_visual_regions as regions
    descriptor = source(tmp_path, "RGBA", (255, 0, 0, 128))
    destination = tmp_path / "prepared"
    manifest = helper.prepare(plan(row(descriptor)), destination, workspace_root=tmp_path)
    assert manifest["admission_allowed"] is False and manifest["model_requests"] == 0
    prepared = manifest["images"][0]["prepared"]
    _, cropped = regions.render({"id": "full", "source": {k: prepared[k] for k in ["path", "sha256", "size"]}, "box": [0, 0, 3, 2]}, 0)
    assert cropped == Path(prepared["path"]).read_bytes()
    assert helper.render(row(descriptor))[1] == Path(prepared["path"]).read_bytes()
    with pytest.raises(FileExistsError): helper.prepare(plan(row(descriptor)), destination, workspace_root=tmp_path)


@pytest.mark.parametrize("bad", ["outside", "root", "duplicate", "background", "empty", "extra"])
def test_invalid_destination_or_policy_is_rejected(tmp_path, bad):
    descriptor = source(tmp_path); value = plan(row(descriptor)); destination = tmp_path / "new"
    if bad == "outside": destination = tmp_path.parent / "outside-profile-fixture"
    if bad == "root": destination = tmp_path
    if bad == "duplicate": value["images"].append(row(descriptor))
    if bad == "background": value["background_srgb"] = [0, 0, 0]
    if bad == "empty": value["images"] = []
    if bad == "extra": value["unknown_policy"] = True
    with pytest.raises(ValueError): helper.prepare(value, destination, workspace_root=tmp_path)
