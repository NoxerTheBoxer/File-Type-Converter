"""Which conversions are possible, and running one."""
from dataclasses import dataclass
from pathlib import Path

from . import data, images
from .formats import FORMATS
from .paths import atomic_write, unique_path


@dataclass
class Options:
    quality: int = 90             # JPEG/WebP quality, 1-100
    keep_metadata: bool = False   # keep photo info (date, camera, GPS location)
    out_dir: Path | None = None   # None = next to the original


def targets_for(fmt: str) -> list[str]:
    kind = FORMATS[fmt].kind
    if kind == "image":
        return [t for t in images.TARGETS if t != fmt]
    return data.TARGETS[fmt]


def common_targets(formats: list[str]) -> list[str]:
    """Targets every given format can convert to, in a stable order."""
    if not formats:
        return []
    shared = set(targets_for(formats[0]))
    for fmt in formats[1:]:
        shared &= set(targets_for(fmt))
    return [t for t in targets_for(formats[0]) if t in shared]


def convert(src: Path, fmt: str, target: str, options: Options | None = None) -> list[Path]:
    """Convert `src` (already detected as `fmt`) to `target`. Returns the file(s) created."""
    options = options or Options()
    if target not in targets_for(fmt):
        raise ValueError(f"Can't convert {FORMATS[fmt].label} to {FORMATS[target].label}")
    folder = options.out_dir or src.parent
    folder.mkdir(parents=True, exist_ok=True)

    if FORMATS[fmt].kind == "image":
        dst = unique_path(folder, src.stem, FORMATS[target].ext)
        with atomic_write(dst) as tmp:
            images.convert(src, tmp, target, options.quality, options.keep_metadata)
        return [dst]
    return data.write(data.read(src, fmt), folder, src.stem, target)
