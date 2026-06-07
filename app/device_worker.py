"""Background device operations (slow work runs off the UI thread).

The op is fully responsible for opening the device when it's ready. This matters
for uploads: the qgif must be encoded *before* the screen is woken, because the
screen's USB interface powers back off if it sits idle, which would invalidate
the handle mid-upload.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QThread, Signal


class DeviceTask(QThread):
    """Runs ``op(progress_cb)`` on a worker thread.

    ``progress_cb(done, total)`` forwards to :attr:`progress`. Results/errors
    return on the UI thread via :attr:`succeeded` / :attr:`failed`.
    """

    progress = Signal(int, int)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, op: Callable, label: str = "", parent=None):
        super().__init__(parent)
        self._op = op
        self.label = label

    def run(self) -> None:  # executes on the worker thread
        try:
            result = self._op(lambda d, t: self.progress.emit(int(d), int(t)))
            self.succeeded.emit(result)
        except Exception as exc:  # surface device/encoder errors to the UI
            self.failed.emit(str(exc))
