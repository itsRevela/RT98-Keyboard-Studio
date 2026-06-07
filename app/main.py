"""Entry point for the RT98 Keyboard Software GUI."""
from __future__ import annotations

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .theme import stylesheet

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def app_icon() -> QIcon:
    """The window/taskbar icon (.ico on Windows for crisp small sizes, else PNG)."""
    ico = os.path.join(ASSETS, "icon.ico")
    png = os.path.join(ASSETS, "icon.png")
    path = ico if (sys.platform == "win32" and os.path.isfile(ico)) else png
    return QIcon(path) if os.path.isfile(path) else QIcon()


def _set_windows_app_id() -> None:
    """Give the process an explicit AppUserModelID so Windows shows our window
    icon in the taskbar instead of the generic Python icon."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RT98.Studio")
    except Exception:
        pass


def main() -> int:
    _set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName("RT98 Studio")
    icon = app_icon()
    app.setWindowIcon(icon)
    app.setStyleSheet(stylesheet())
    win = MainWindow()
    win.setWindowIcon(icon)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
