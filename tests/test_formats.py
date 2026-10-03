import pytest

from converter.formats import detect
from converter.paths import atomic_write, unique_path


@pytest.mark.parametrize("fmt", ["png", "jpg", "webp", "gif", "bmp", "tiff", "ico", "heic"])
def test_detects_images_by_content(make_image, fmt):
    assert detect(make_image(fmt)) == fmt


def test_detects_disguised_file(make_image):
    # A PNG renamed to .jpg is still a PNG.
    assert detect(make_image("png", name="photo.jpg")) == "png"


@pytest.mark.parametrize("fmt", ["xlsx", "csv", "json"])
def test_detects_data(make_data, fmt):
    assert detect(make_data(fmt)) == fmt


def test_rejects_unknown_and_broken(tmp_path):
    (tmp_path / "notes.txt").write_text("hello")
    (tmp_path / "bad.json").write_text("{not json")
    (tmp_path / "fake.xlsx").write_bytes(b"PK\x03\x04garbage")
    assert detect(tmp_path / "notes.txt") is None
    assert detect(tmp_path / "bad.json") is None
    assert detect(tmp_path / "fake.xlsx") is None
    assert detect(tmp_path / "missing.png") is None


def test_unique_path_never_overwrites(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "a (1).jpg").write_bytes(b"x")
    assert unique_path(tmp_path, "a", ".jpg").name == "a (2).jpg"


def test_atomic_write_cleans_up_on_failure(tmp_path):
    dst = tmp_path / "out.png"
    with pytest.raises(RuntimeError):
        with atomic_write(dst) as tmp:
            tmp.write_bytes(b"half")
            raise RuntimeError("boom")
    assert list(tmp_path.iterdir()) == []
