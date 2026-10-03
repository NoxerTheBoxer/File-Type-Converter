"""Image conversion with Pillow (plus pillow-heif for iPhone HEIC photos)."""
from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

TARGETS = ["png", "jpg", "webp", "gif", "bmp", "tiff", "ico"]
PIL_FORMAT = {"png": "PNG", "jpg": "JPEG", "webp": "WEBP", "gif": "GIF", "bmp": "BMP", "tiff": "TIFF", "ico": "ICO"}
NO_ALPHA = {"jpg", "bmp"}               # transparency gets flattened onto white
KEEPS_EXIF = {"jpg", "webp", "png", "tiff"}
LOSSY = {"jpg", "webp"}                 # formats where the quality setting applies


def convert(src: Path, dst: Path, target: str, quality: int = 90, keep_metadata: bool = False) -> None:
    with Image.open(src) as original:
        im = ImageOps.exif_transpose(original)  # bake in phone rotation so the picture isn't sideways
        exif = im.getexif().tobytes() if keep_metadata and target in KEEPS_EXIF else None

        im = _flatten(im) if target in NO_ALPHA else _web_safe_mode(im)

        options = {"format": PIL_FORMAT[target]}
        if target in LOSSY:
            options["quality"] = quality
        if target in ("jpg", "png"):
            options["optimize"] = True
        if exif:
            options["exif"] = exif
        im.save(dst, **options)


def _has_alpha(im: Image.Image) -> bool:
    return im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)


def _flatten(im: Image.Image) -> Image.Image:
    if not _has_alpha(im):
        return im if im.mode in ("RGB", "L") else im.convert("RGB")
    rgba = im.convert("RGBA")
    background = Image.new("RGB", rgba.size, (255, 255, 255))
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def _web_safe_mode(im: Image.Image) -> Image.Image:
    """Convert unusual modes (CMYK, 16-bit, etc.) to something every target format can store."""
    if im.mode in ("1", "L", "LA", "P", "RGB", "RGBA"):
        return im
    return im.convert("RGBA" if _has_alpha(im) else "RGB")
