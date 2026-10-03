"""Choosing output names and writing files so a failed conversion never leaves a half-written file."""
import os
from contextlib import contextmanager
from pathlib import Path


def unique_path(folder: Path, stem: str, ext: str) -> Path:
    """`folder/stem.ext`, or `stem (1).ext`, `stem (2).ext`... if that name is taken."""
    candidate = folder / f"{stem}{ext}"
    n = 1
    while candidate.exists():
        candidate = folder / f"{stem} ({n}){ext}"
        n += 1
    return candidate


@contextmanager
def atomic_write(dst: Path):
    """Yield a temporary path next to `dst`; move it into place only if the block succeeds."""
    tmp = dst.with_name(f".{dst.name}.part")
    try:
        yield tmp
        os.replace(tmp, dst)
    finally:
        tmp.unlink(missing_ok=True)
