"""Drive the real window offscreen: add files, convert, check the results."""
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from converter.ui.main_window import COL_STATUS, MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def wait_until(app, condition, timeout_s=20):
    import time
    end = time.time() + timeout_s
    while not condition():
        app.processEvents()
        assert time.time() < end, "timed out"
        time.sleep(0.01)


def test_convert_batch_through_window(app, make_image, tmp_path):
    files = [make_image("png", name="a.png"), make_image("heic", name="b.heic"), make_image("jpg", name="c.jpg")]
    (tmp_path / "notes.txt").write_text("not convertible")
    w = MainWindow()
    w.add_files(files + [tmp_path / "notes.txt"])

    assert w.table.rowCount() == 4
    assert w.table.item(3, COL_STATUS).text() == "Not supported"
    targets = [w.target.itemData(i) for i in range(w.target.count())]
    assert "jpg" not in targets and "webp" in targets  # c.jpg can't become a jpg, so jpg isn't a shared target

    w.target.setCurrentIndex(w.target.findData("webp"))
    w.start()
    wait_until(app, lambda: not w.busy)

    assert all(w.table.item(r, COL_STATUS).text().endswith(".webp") for r in range(3))
    assert {p.name for p in Path(tmp_path).glob("*.webp")} == {"a.webp", "b.webp", "c.webp"}
    assert w.progress.value() == 3


def test_mixed_kinds_have_no_shared_target(app, make_image, make_data):
    w = MainWindow()
    w.add_files([make_image("png"), make_data("csv")])
    assert w.target.currentData() is None
    assert not w.convert_btn.isEnabled()


def test_duplicate_files_are_added_once(app, make_image):
    w = MainWindow()
    p = make_image("png")
    w.add_files([p, p])
    w.add_files([p])
    assert w.table.rowCount() == 1
