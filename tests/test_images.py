import pytest
from PIL import Image

from converter import registry
from converter.formats import detect
from converter.images import TARGETS

SOURCES = ["png", "jpg", "webp", "gif", "bmp", "tiff", "ico", "heic"]


@pytest.mark.parametrize("src_fmt", SOURCES)
@pytest.mark.parametrize("target", TARGETS)
def test_every_image_conversion(make_image, src_fmt, target):
    if src_fmt == target:
        pytest.skip("same format")
    src = make_image(src_fmt, alpha=True)
    before = src.read_bytes()
    [out] = registry.convert(src, src_fmt, target)
    assert out.suffix == f".{target}"
    assert detect(out) == target
    with Image.open(out) as im:
        im.load()
    assert src.read_bytes() == before, "original must never change"


def test_transparency_flattens_to_white_for_jpg(make_image):
    src = make_image("png", alpha=True)
    [out] = registry.convert(src, "png", "jpg")
    with Image.open(out) as im:
        assert im.mode == "RGB"
        r, g, b = im.getpixel((5, 5))
        assert r > 100  # half-transparent aqua over white, not over black


def test_quality_changes_size(make_image, tmp_path):
    src = make_image("png", size=(400, 300))
    Image.effect_noise((400, 300), 60).convert("RGB").save(src)
    low = registry.convert(src, "png", "jpg", registry.Options(quality=20))[0].stat().st_size
    high = registry.convert(src, "png", "jpg", registry.Options(quality=95))[0].stat().st_size
    assert low < high


def test_metadata_stripped_unless_kept(make_image):
    src = make_image("jpg")
    with Image.open(src) as im:
        exif = im.getexif()
        exif[0x010F] = "TestCam"  # camera make
        im.save(src, exif=exif.tobytes())
    [stripped] = registry.convert(src, "jpg", "webp")
    [kept] = registry.convert(src, "jpg", "png", registry.Options(keep_metadata=True))
    with Image.open(stripped) as im:
        assert 0x010F not in im.getexif()
    with Image.open(kept) as im:
        assert im.getexif().get(0x010F) == "TestCam"


def test_output_folder_and_no_overwrite(make_image, tmp_path):
    src = make_image("png")
    out_dir = tmp_path / "converted"
    first = registry.convert(src, "png", "jpg", registry.Options(out_dir=out_dir))[0]
    second = registry.convert(src, "png", "jpg", registry.Options(out_dir=out_dir))[0]
    assert first.parent == out_dir and first.name == "sample.jpg"
    assert second.name == "sample (1).jpg"


def test_corrupt_image_raises_and_leaves_nothing(tmp_path):
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    with pytest.raises(Exception):
        registry.convert(bad, "png", "jpg")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["broken.png"]
