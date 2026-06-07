"""Live output preview: shows the edited frame as the screen will display it."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from rt98 import protocol as P
from rt98.imaging import Clip, EditState, render_frame
from ..qt_util import pil_to_qpixmap
from ..theme import PALETTE


class OutputPreview(QWidget):
    """Renders crop+adjustments+fit to 240x136 and shows it scaled up."""

    def __init__(self, scale: int = 2, parent=None):
        super().__init__(parent)
        self.scale = scale
        self.setMinimumSize(P.SCREEN_W * scale, P.SCREEN_H * scale)
        self._clip: Optional[Clip] = None
        self._edit = EditState()
        self._idx = 0
        self._pixmap: Optional[QPixmap] = None

    def set_clip(self, clip: Optional[Clip]):
        self._clip = clip
        self._idx = 0
        self.refresh()

    def set_edit(self, edit: EditState):
        self._edit = edit
        self.refresh()

    def set_frame(self, idx: int):
        if self._clip and self._clip.frames:
            self._idx = idx % len(self._clip.frames)
            self.refresh()

    def refresh(self):
        if self._clip and self._clip.frames:
            src = self._clip.frames[self._idx % len(self._clip.frames)]
            img = render_frame(src, self._edit, (P.SCREEN_W, P.SCREEN_H))
            self._pixmap = pil_to_qpixmap(img)
        else:
            self._pixmap = None
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(PALETTE["canvas"]))
        if not self._pixmap:
            p.setPen(QColor(PALETTE["muted"]))
            p.drawText(self.rect(), Qt.AlignCenter, "Live preview")
            return
        w = P.SCREEN_W * self.scale
        h = P.SCREEN_H * self.scale
        x = (self.width() - w) // 2
        y = (self.height() - h) // 2
        p.drawPixmap(x, y, w, h, self._pixmap)
        p.setPen(QColor(PALETTE["border"]))
        p.drawRect(x, y, w - 1, h - 1)
