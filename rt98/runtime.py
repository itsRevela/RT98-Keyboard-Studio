"""Locating bundled resources and CLI tools, PyInstaller-aware.

When packaged with PyInstaller, data files live under ``sys._MEIPASS`` and any
bundled CLI tools (node, ffmpeg) are placed in ``<bundle>/bin``. When running
from source these helpers fall back to the project layout / the system PATH.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

# Suppress the console window when launching console exes (node/ffmpeg) from a
# windowed (no-console) build. 0 / no-op on non-Windows.
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def meipass() -> str | None:
    """The PyInstaller extraction dir when frozen, else ``None``."""
    return getattr(sys, "_MEIPASS", None)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundled_tool(name: str) -> str | None:
    """Path to a CLI tool bundled under ``<bundle>/bin``, if present."""
    base = meipass()
    if not base:
        return None
    exe = name + (".exe" if sys.platform == "win32" else "")
    path = os.path.join(base, "bin", exe)
    return path if os.path.isfile(path) else None


def tool_command(name: str) -> str:
    """How to invoke ``name``: the bundled binary if present, else the bare name
    (resolved on PATH)."""
    return bundled_tool(name) or name


def tool_available(name: str) -> bool:
    """True if ``name`` is bundled or found on PATH."""
    return bundled_tool(name) is not None or shutil.which(name) is not None
