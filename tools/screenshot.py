"""Render docs/screenshot.png: the window after converting a few sample files.

Run from the project root: python tools/screenshot.py
"""
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from converter.ui.main_window import MainWindow  # noqa: E402

SAMPLES = [("IMG_2041.heic", "HEIF"), ("beach-sunset.png", "PNG"), ("logo.webp", "WEBP"), ("scan_receipt.tiff", "TIFF")]


def main():
    app = QApplication([])
    folder = Path(tempfile.mkdtemp())
    files = []
    for name, fmt in SAMPLES:
        path = folder / name
        Image.new("RGB", (800, 600), (0, 171, 201)).save(path, format=fmt)
        files.append(path)
    (folder / "invoice.pdf.exe").write_bytes(b"MZ\x90\x00")

    window = MainWindow()
    window.resize(900, 560)
    window.add_files(files + [folder / "invoice.pdf.exe"])
    window.target.setCurrentIndex(window.target.findData("jpg"))
    window.start()
    deadline = time.time() + 30
    while window.busy and time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()

    out = Path(__file__).resolve().parent.parent / "docs" / "screenshot.png"
    window.grab().save(str(out))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
