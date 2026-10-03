"""Start File Type Converter. Files passed on the command line (e.g. via "Open with") are preloaded."""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from converter.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("File Type Converter")
    window = MainWindow()
    window.add_files([Path(a) for a in sys.argv[1:]])
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
