"""Runs conversions off the UI thread so the window never freezes."""
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from .. import registry


class ConvertWorker(QObject):
    progress = Signal(int, str, str)   # row, state ("working" | "done" | "error" | "skipped"), message
    finished = Signal(int, int)        # converted, failed

    def __init__(self, jobs: list[tuple[int, Path, str]], target: str, options: registry.Options):
        super().__init__()
        self.jobs = jobs
        self.target = target
        self.options = options
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    @Slot()
    def run(self) -> None:
        ok = failed = 0
        for row, path, fmt in self.jobs:
            if self._cancel.is_set():
                self.progress.emit(row, "skipped", "Cancelled")
                continue
            self.progress.emit(row, "working", "Converting…")
            try:
                outputs = registry.convert(path, fmt, self.target, self.options)
            except Exception as e:  # one bad file shouldn't stop the batch
                failed += 1
                self.progress.emit(row, "error", _friendly(e))
            else:
                ok += 1
                self.progress.emit(row, "done", ", ".join(p.name for p in outputs))
        self.finished.emit(ok, failed)


def _friendly(e: Exception) -> str:
    if isinstance(e, PermissionError):
        return "Couldn't write the file. Is it open in another program, or is the folder read-only?"
    if isinstance(e, MemoryError):
        return "File too large to convert"
    return str(e) or type(e).__name__
