from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from stopmotion.app import StopMotionWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Стоп-моушен студия")
    app.setFont(QFont("Segoe UI", 10))
    window = StopMotionWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
