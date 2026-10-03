import json
import os

import pytest
from openpyxl import Workbook
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

IMAGE_SAVE = {"png": "PNG", "jpg": "JPEG", "webp": "WEBP", "gif": "GIF", "bmp": "BMP", "tiff": "TIFF", "ico": "ICO", "heic": "HEIF"}


@pytest.fixture
def make_image(tmp_path):
    import pillow_heif  # noqa: F401  (registers HEIF saving)
    pillow_heif.register_heif_opener()

    def make(fmt: str, name: str | None = None, alpha: bool = False, size=(64, 48)):
        mode = "RGBA" if alpha and fmt not in ("jpg", "bmp") else "RGB"
        im = Image.new(mode, size, (0, 171, 201, 128) if mode == "RGBA" else (0, 171, 201))
        path = tmp_path / (name or f"sample.{fmt}")
        im.save(path, format=IMAGE_SAVE[fmt])
        return path

    return make


@pytest.fixture
def make_data(tmp_path):
    def make(fmt: str, name: str | None = None):
        path = tmp_path / (name or f"sample.{fmt}")
        if fmt == "csv":
            path.write_text("name,qty,zip\nmango,3,00123\nguava,4.5,+1 242\n", encoding="utf-8")
        elif fmt == "json":
            path.write_text(json.dumps([{"name": "mango", "qty": 3}, {"name": "guava", "tags": ["sweet"]}]), encoding="utf-8")
        else:
            wb = Workbook()
            ws = wb.active
            ws.title = "Fruit"
            ws.append(["name", "qty"])
            ws.append(["mango", 3])
            ws2 = wb.create_sheet("Veg")
            ws2.append(["name", "qty"])
            ws2.append(["okra", 7])
            wb.save(path)
        return path

    return make
