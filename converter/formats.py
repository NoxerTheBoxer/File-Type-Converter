"""Known formats, and detection of what a file really is (by its contents, not just its name)."""
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Format:
    id: str
    label: str
    ext: str
    kind: str  # "image" or "data"


FORMATS = {
    f.id: f
    for f in [
        Format("png", "PNG", ".png", "image"),
        Format("jpg", "JPEG", ".jpg", "image"),
        Format("webp", "WebP", ".webp", "image"),
        Format("gif", "GIF", ".gif", "image"),
        Format("bmp", "BMP", ".bmp", "image"),
        Format("tiff", "TIFF", ".tiff", "image"),
        Format("ico", "Icon", ".ico", "image"),
        Format("heic", "HEIC (iPhone photo)", ".heic", "image"),
        Format("xlsx", "Excel workbook", ".xlsx", "data"),
        Format("csv", "CSV", ".csv", "data"),
        Format("json", "JSON", ".json", "data"),
    ]
}

EXTENSIONS = {f.ext: f.id for f in FORMATS.values()} | {
    ".jpeg": "jpg", ".jpe": "jpg", ".jfif": "jpg", ".tif": "tiff", ".heif": "heic", ".hif": "heic",
}

HEIF_BRANDS = {b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx", b"mif1", b"msf1"}


def format_from_extension(path: Path) -> str | None:
    return EXTENSIONS.get(path.suffix.lower())


def detect(path: Path) -> str | None:
    """Return the format id of a file based on its contents, or None if unsupported."""
    try:
        with open(path, "rb") as f:
            head = f.read(32)
    except OSError:
        return None

    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head.startswith(b"BM") and _is_bmp_header(head):
        return "bmp"
    if head.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff"
    if head.startswith(b"\x00\x00\x01\x00"):
        return "ico"
    if head[4:8] == b"ftyp" and head[8:12] in HEIF_BRANDS:
        return "heic"
    if head.startswith(b"PK\x03\x04"):
        return "xlsx" if _is_xlsx(path) else None

    # Text formats have no signature: trust the extension, but check the contents fit.
    ext_format = format_from_extension(path)
    if ext_format == "json" and _is_json(path):
        return "json"
    if ext_format == "csv" and _is_text(head):
        return "csv"
    return None


def _is_bmp_header(head: bytes) -> bool:
    """'BM' alone is too weak (a CSV can start with 'BMW,'): also check reserved bytes and header size."""
    return head[6:10] == b"\x00\x00\x00\x00" and int.from_bytes(head[14:18], "little") in (12, 40, 52, 56, 64, 108, 124)


def _is_xlsx(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as z:
            return "xl/workbook.xml" in z.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


def _is_json(path: Path) -> bool:
    try:
        with open(path, encoding="utf-8-sig") as f:
            json.load(f)
        return True
    except (ValueError, OSError):
        return False


def _is_text(head: bytes) -> bool:
    return b"\x00" not in head
