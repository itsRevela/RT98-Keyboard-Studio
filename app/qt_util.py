"""Small Qt helpers (PIL <-> Qt, painted glyph icons)."""
from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap, QPolygonF


def pil_to_qimage(img: Image.Image) -> QImage:
    rgba = img.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimg = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format_RGBA8888)
    return qimg.copy()  # detach from the temporary bytes buffer


def pil_to_qpixmap(img: Image.Image) -> QPixmap:
    return QPixmap.fromImage(pil_to_qimage(img))


def _icon_canvas(size: int):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    return pm, p


def play_icon(color: str, size: int = 18) -> QIcon:
    """A solid right-pointing triangle, painted (font-independent)."""
    pm, p = _icon_canvas(size)
    p.setBrush(QColor(color))
    s = size
    p.drawPolygon(QPolygonF([QPointF(s * 0.34, s * 0.24),
                             QPointF(s * 0.34, s * 0.76),
                             QPointF(s * 0.78, s * 0.50)]))
    p.end()
    return QIcon(pm)


def pause_icon(color: str, size: int = 18) -> QIcon:
    """Two solid bars matching the play triangle's weight."""
    pm, p = _icon_canvas(size)
    p.setBrush(QColor(color))
    s = size
    bw, gap, top, h = s * 0.16, s * 0.18, s * 0.24, s * 0.52
    p.drawRoundedRect(QRectF(s * 0.5 - gap / 2 - bw, top, bw, h), 1.0, 1.0)
    p.drawRoundedRect(QRectF(s * 0.5 + gap / 2, top, bw, h), 1.0, 1.0)
    p.end()
    return QIcon(pm)
