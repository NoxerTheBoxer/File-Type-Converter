"""Main window: drop files in, pick a format, convert."""
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QSlider, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from .. import __version__, images, registry
from ..formats import FORMATS, detect, format_from_extension
from .worker import ConvertWorker

COL_FILE, COL_TYPE, COL_STATUS = range(3)
STATE_COLORS = {"done": "#1a8f3c", "error": "#c62828", "skipped": "#8a8f98", "working": "#00788d"}

# Explicit colors everywhere: Windows dark mode otherwise draws white text on these light backgrounds.
STYLE = """
QMainWindow, QWidget { background: #f7fafb; color: #1f2a30; }
QLabel, QCheckBox { background: transparent; }
QToolTip { background: white; color: #1f2a30; border: 1px solid #c5cdd3; }
QTableWidget { background: white; color: #1f2a30; border: 2px dashed #00abc9; border-radius: 10px;
               gridline-color: #e3e8eb; selection-background-color: #d8f3f8; selection-color: #1f2a30; }
QHeaderView::section { background: #eef3f5; color: #1f2a30; padding: 5px; border: none;
                       border-bottom: 1px solid #d5dde2; font-weight: 600; }
QComboBox { background: white; color: #1f2a30; border: 1px solid #c5cdd3; border-radius: 6px; padding: 4px 8px; }
QComboBox QAbstractItemView { background: white; color: #1f2a30; selection-background-color: #d8f3f8;
                              selection-color: #1f2a30; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #8a959c; border-radius: 3px; background: white; }
QCheckBox::indicator:checked { background: #00abc9; border-color: #00abc9; }
QSlider::groove:horizontal { height: 4px; background: #d5dde2; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #00abc9; border-radius: 2px; }
QSlider::handle:horizontal { background: #ffc72c; border: 1px solid #c99a12; width: 14px; margin: -6px 0; border-radius: 7px; }
QStatusBar { color: #1f2a30; }
QPushButton { padding: 6px 14px; border-radius: 6px; border: 1px solid #c5cdd3; background: white; color: #1f2a30; }
QPushButton:disabled { color: #9aa5ac; }
QPushButton:hover { border-color: #00abc9; }
QPushButton#primary { background: #00abc9; color: white; border: none; font-weight: 600; }
QPushButton#primary:hover { background: #0096b0; }
QPushButton#primary:disabled { background: #a9dde7; }
QProgressBar { border: 1px solid #c5cdd3; border-radius: 6px; text-align: center; height: 18px; }
QProgressBar::chunk { background: #ffc72c; border-radius: 5px; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"File Type Converter {__version__}")
        self.setMinimumSize(780, 520)
        self.setAcceptDrops(True)
        self.setStyleSheet(STYLE)

        self.files: list[tuple[Path, str | None]] = []   # (path, detected format or None)
        self.thread: QThread | None = None
        self.worker: ConvertWorker | None = None
        self.out_dir: Path | None = None
        self.last_output_dir: Path | None = None

        self._build()
        self._refresh()

    # ---------- layout ----------

    def _build(self):
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["File", "Type", "Status"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_FILE, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_TYPE, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.hint = QLabel("Drop files here, or click <b>Add files…</b>")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet("color: #5f6b73; font-size: 15px;")

        add_btn = QPushButton("Add files…", clicked=self.choose_files)
        self.remove_btn = QPushButton("Remove selected", clicked=self.remove_selected)
        self.clear_btn = QPushButton("Clear", clicked=self.clear)
        file_row = _row(add_btn, self.remove_btn, self.clear_btn, stretch=True)

        self.target = QComboBox(currentIndexChanged=self._refresh_options)
        self.quality = QSlider(Qt.Horizontal, minimum=10, maximum=100, value=90)
        self.quality.setFixedWidth(140)
        self.quality_label = QLabel()
        self.quality.valueChanged.connect(lambda v: self.quality_label.setText(f"Quality {v}"))
        self.quality.valueChanged.emit(self.quality.value())
        self.keep_meta = QCheckBox("Keep photo info (date, camera, location)")
        self.keep_meta.setToolTip("Off by default so photos you share don't reveal where they were taken.")
        options_row = _row(QLabel("Convert to:"), self.target, self.quality_label, self.quality, self.keep_meta, stretch=True)

        self.output = QComboBox()
        self.output.addItems(["Next to the original", "Choose folder…"])
        self.output.activated.connect(self._output_changed)
        self.open_btn = QPushButton("Open output folder", clicked=self.open_output)
        self.convert_btn = QPushButton("Convert", clicked=self.start, objectName="primary")
        self.cancel_btn = QPushButton("Cancel", clicked=self.cancel)
        action_row = _row(QLabel("Save to:"), self.output, stretch=True)
        action_row.addWidget(self.open_btn)
        action_row.addWidget(self.cancel_btn)
        action_row.addWidget(self.convert_btn)

        self.progress = QProgressBar()

        layout = QVBoxLayout()
        layout.addWidget(self.hint)
        layout.addWidget(self.table, 1)
        for part in (file_row, options_row, action_row):
            layout.addLayout(part)
        layout.addWidget(self.progress)
        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

    # ---------- files ----------

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and not self.busy:
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_files([Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()])

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose files to convert")
        self.add_files([Path(p) for p in paths])

    def add_files(self, paths: list[Path]):
        known = {p for p, _ in self.files}
        for path in _expand(paths):
            if path in known:
                continue
            known.add(path)
            fmt = detect(path)
            self.files.append((path, fmt))
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, COL_FILE, QTableWidgetItem(path.name))
            self.table.item(row, COL_FILE).setToolTip(str(path))
            self.table.setItem(row, COL_TYPE, QTableWidgetItem(_type_label(path, fmt)))
            self._set_status(row, "skipped" if fmt is None else "", "Not supported" if fmt is None else "Ready")
        self._refresh()

    def remove_selected(self):
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)
            del self.files[row]
        self._refresh()

    def clear(self):
        self.table.setRowCount(0)
        self.files.clear()
        self._refresh()

    # ---------- options ----------

    def _refresh(self):
        supported = [fmt for _, fmt in self.files if fmt]
        current = self.target.currentData()
        self.target.blockSignals(True)
        self.target.clear()
        for t in registry.common_targets(supported):
            self.target.addItem(FORMATS[t].label, t)
        if current and self.target.findData(current) >= 0:
            self.target.setCurrentIndex(self.target.findData(current))
        self.target.blockSignals(False)

        self.hint.setVisible(not self.files)
        if supported and not self.target.count():
            self.target.addItem("No shared format: convert images and spreadsheets separately", None)
        self._refresh_options()

    def _refresh_options(self):
        t = self.target.currentData()
        is_image = bool(t) and FORMATS[t].kind == "image"
        self.quality.setVisible(t in images.LOSSY)
        self.quality_label.setVisible(t in images.LOSSY)
        self.keep_meta.setVisible(is_image and t in images.KEEPS_EXIF)
        busy = self.busy
        self.convert_btn.setEnabled(bool(t) and not busy)
        self.cancel_btn.setVisible(busy)
        for w in (self.target, self.output, self.remove_btn, self.clear_btn):
            w.setEnabled(not busy)
        self.open_btn.setEnabled(self.last_output_dir is not None)

    def _output_changed(self, index: int):
        if index == 1:
            folder = QFileDialog.getExistingDirectory(self, "Save converted files to")
            if folder:
                self.out_dir = Path(folder)
                self.output.setItemText(1, f"{self.out_dir}  (change…)")
            elif self.out_dir is None:
                self.output.setCurrentIndex(0)
        else:
            self.out_dir = None

    # ---------- converting ----------

    @property
    def busy(self) -> bool:
        return self.thread is not None

    def start(self):
        target = self.target.currentData()
        jobs = [(row, path, fmt) for row, (path, fmt) in enumerate(self.files) if fmt]
        if not target or not jobs:
            return
        options = registry.Options(self.quality.value(), self.keep_meta.isChecked(), self.out_dir)
        self.last_output_dir = self.out_dir or jobs[0][1].parent

        self.progress.setRange(0, len(jobs))
        self.progress.setValue(0)
        self.thread = QThread(self)
        self.worker = ConvertWorker(jobs, target, options)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._on_thread_done)
        self.thread.start()
        self._refresh_options()

    def cancel(self):
        if self.worker:
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)

    def _on_progress(self, row: int, state: str, message: str):
        self._set_status(row, state, message)
        if state != "working":
            self.progress.setValue(self.progress.value() + 1)

    def _on_finished(self, ok: int, failed: int):
        text = f"Converted {ok} file{'s' * (ok != 1)}" + (f", {failed} failed" if failed else "")
        self.statusBar().showMessage(text, 10000)

    def _on_thread_done(self):
        self.thread.deleteLater()
        self.thread = self.worker = None
        self.cancel_btn.setEnabled(True)
        self._refresh_options()

    def open_output(self):
        if self.last_output_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output_dir)))

    def closeEvent(self, event):
        if self.busy:
            if QMessageBox.question(self, "Still converting", "Cancel the conversion and quit?") != QMessageBox.Yes:
                event.ignore()
                return
            self.worker.cancel()
            self.thread.quit()
            self.thread.wait()
        event.accept()

    def _set_status(self, row: int, state: str, message: str):
        item = QTableWidgetItem(message)
        item.setToolTip(message)
        if state in STATE_COLORS:
            item.setForeground(QColor(STATE_COLORS[state]))
        self.table.setItem(row, COL_STATUS, item)


def _row(*widgets, stretch=False) -> QHBoxLayout:
    row = QHBoxLayout()
    for w in widgets:
        row.addWidget(w)
    if stretch:
        row.addStretch(1)
    return row


def _expand(paths: list[Path]) -> list[Path]:
    """Dropped folders contribute the files directly inside them."""
    out = []
    for p in paths:
        if p.is_dir():
            out.extend(sorted(c for c in p.iterdir() if c.is_file()))
        elif p.is_file():
            out.append(p)
    return out


def _type_label(path: Path, fmt: str | None) -> str:
    if fmt is None:
        return "Unknown"
    label = FORMATS[fmt].label
    claimed = format_from_extension(path)
    return f"{label} (named as {path.suffix})" if claimed and claimed != fmt else label
