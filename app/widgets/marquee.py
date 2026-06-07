"""A label that scrolls its text horizontally when it doesn't fit.

Static (and aligned) when the text fits; gently scrolls left in a loop when it
overflows. Custom-painted so it can live inside list item widgets and slot tiles.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QWidget

_GAP = 28        # px gap between the looping copies
_INTERVAL = 33   # ms per step (~30 fps)


class MarqueeLabel(QWidget):
    def __init__(self, text: str = "", color: Optional[str] = None,
                 align=Qt.AlignLeft, parent=None):
        super().__init__(parent)
        self._text = ""
        self._color = QColor(color) if color else None
        self._align = align
        self._offset = 0
        self._timer = QTimer(self)
        self._timer.setInterval(_INTERVAL)
        self._timer.timeout.connect(self._advance)
        self.setText(text)

    # -- public ---------------------------------------------------------------
    def setText(self, text: str) -> None:
        text = text or ""
        if text == self._text:
            return
        self._text = text
        self._offset = 0
        self.setToolTip(text)
        self._sync()
        self.update()

    def text(self) -> str:
        return self._text

    def setColor(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    # -- internals ------------------------------------------------------------
    def _text_w(self) -> int:
        return self.fontMetrics().horizontalAdvance(self._text)

    def _overflows(self) -> bool:
        return self.width() > 0 and self._text_w() > self.width()

    def _sync(self) -> None:
        if self._overflows() and self.isVisible():
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
            self._offset = 0

    def _advance(self) -> None:
        self._offset += 1
        if self._offset >= self._text_w() + _GAP:
            self._offset = 0
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._sync()
        super().resizeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        self._sync()
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        super().hideEvent(event)

    def sizeHint(self) -> QSize:
        return QSize(0, self.fontMetrics().height())

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setPen(self._color if self._color is not None
                       else self.palette().color(QPalette.WindowText))
        fm = self.fontMetrics()
        y = int((self.height() + fm.ascent() - fm.descent()) / 2)
        if self._timer.isActive():
            tw = self._text_w()
            x = -self._offset
            painter.drawText(x, y, self._text)
            painter.drawText(x + tw + _GAP, y, self._text)  # second copy: seamless loop
        else:
            if self._align & Qt.AlignHCenter:
                x = max(0, int((self.width() - self._text_w()) / 2))
            else:
                x = 0
            painter.drawText(x, y, self._text)
