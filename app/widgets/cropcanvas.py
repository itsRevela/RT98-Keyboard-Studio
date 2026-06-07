"""Interactive crop canvas: shows the source frame with a draggable crop box."""
from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from rt98.imaging import Clip
from ..qt_util import pil_to_qpixmap
from ..theme import PALETTE

ASPECT = 240 / 136
HANDLE = 9  # px hit radius for corner handles


class CropCanvas(QWidget):
    """Displays the (animated) source and lets the user drag a crop rectangle.

    Emits ``cropChanged((l, t, r, b))`` in source-pixel coordinates.
    """

    cropChanged = Signal(object)  # tuple or None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 200)
        self._clip: Optional[Clip] = None
        self._pixmap: Optional[QPixmap] = None
        self._src_w = 0
        self._src_h = 0
        self._crop = None  # type: Optional[list]  # [l,t,r,b] in source px
        self.aspect_locked = True
        self._drag = None  # ("move"|"nw"|"ne"|"sw"|"se"|"new", start info)

    # -- data ------------------------------------------------------------------
    def set_clip(self, clip: Optional[Clip]):
        self._clip = clip
        if clip:
            self._src_w, self._src_h = clip.source_size
            self._crop = None
        else:
            self._pixmap = None
        self.set_frame(0)

    def set_frame(self, idx: int):
        if self._clip and self._clip.frames:
            idx = idx % len(self._clip.frames)
            self._pixmap = pil_to_qpixmap(self._clip.frames[idx])
        self.update()

    def set_crop(self, crop: Optional[Tuple[int, int, int, int]]):
        self._crop = list(crop) if crop else None
        self.update()

    def current_crop(self) -> Optional[Tuple[int, int, int, int]]:
        if not self._crop:
            return None
        l, t, r, b = (int(round(v)) for v in self._crop)
        return (l, t, r, b)

    # -- geometry mapping (source <-> widget) ----------------------------------
    def _fit_rect(self) -> QRectF:
        if not self._src_w:
            return QRectF(0, 0, self.width(), self.height())
        scale = min(self.width() / self._src_w, self.height() / self._src_h)
        w, h = self._src_w * scale, self._src_h * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def _to_widget(self, x: float, y: float) -> QPointF:
        fr = self._fit_rect()
        return QPointF(fr.x() + x / self._src_w * fr.width(),
                       fr.y() + y / self._src_h * fr.height())

    def _to_source(self, px: float, py: float) -> QPointF:
        fr = self._fit_rect()
        if fr.width() <= 0:
            return QPointF(0, 0)
        x = (px - fr.x()) / fr.width() * self._src_w
        y = (py - fr.y()) / fr.height() * self._src_h
        return QPointF(max(0, min(self._src_w, x)), max(0, min(self._src_h, y)))

    # -- painting --------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(PALETTE["canvas"]))
        if not self._pixmap:
            p.setPen(QColor(PALETTE["muted"]))
            p.drawText(self.rect(), Qt.AlignCenter, "Import a GIF, image or video to begin")
            return
        fr = self._fit_rect()
        p.drawPixmap(fr.toRect(), self._pixmap)
        if not self._crop:
            return
        l, t, r, b = self._crop
        tl = self._to_widget(l, t)
        br = self._to_widget(r, b)
        crop_rect = QRectF(tl, br).normalized()
        # dim outside the crop
        p.setBrush(QColor(0, 0, 0, 120))
        p.setPen(Qt.NoPen)
        for region in self._outside(fr, crop_rect):
            p.drawRect(region)
        # crop border + handles
        accent = QColor(PALETTE["blue_hi"])
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(accent, 2))
        p.drawRect(crop_rect)
        p.setBrush(QColor(PALETTE["surface"]))
        p.setPen(QPen(accent, 2))
        for c in (crop_rect.topLeft(), crop_rect.topRight(),
                  crop_rect.bottomLeft(), crop_rect.bottomRight()):
            p.drawEllipse(c, 5, 5)

    @staticmethod
    def _outside(fr: QRectF, crop: QRectF):
        return [
            QRectF(fr.x(), fr.y(), fr.width(), crop.top() - fr.y()),
            QRectF(fr.x(), crop.bottom(), fr.width(), fr.bottom() - crop.bottom()),
            QRectF(fr.x(), crop.top(), crop.left() - fr.x(), crop.height()),
            QRectF(crop.right(), crop.top(), fr.right() - crop.right(), crop.height()),
        ]

    # -- interaction -----------------------------------------------------------
    def _handle_at(self, pos) -> Optional[str]:
        if not self._crop:
            return None
        corners = {"nw": (self._crop[0], self._crop[1]), "ne": (self._crop[2], self._crop[1]),
                   "sw": (self._crop[0], self._crop[3]), "se": (self._crop[2], self._crop[3])}
        for name, (sx, sy) in corners.items():
            wp = self._to_widget(sx, sy)
            if abs(wp.x() - pos.x()) <= HANDLE and abs(wp.y() - pos.y()) <= HANDLE:
                return name
        tl = self._to_widget(self._crop[0], self._crop[1])
        br = self._to_widget(self._crop[2], self._crop[3])
        if QRectF(tl, br).normalized().contains(pos):
            return "move"
        return None

    def mousePressEvent(self, e):
        if not self._pixmap:
            return
        pos = e.position()
        handle = self._handle_at(pos)
        if handle == "move":
            sp = self._to_source(pos.x(), pos.y())
            self._drag = ("move", (sp.x(), sp.y(), list(self._crop)))
        elif handle:
            self._drag = (handle, None)
        else:
            sp = self._to_source(pos.x(), pos.y())
            self._crop = [sp.x(), sp.y(), sp.x(), sp.y()]
            self._drag = ("new", None)
        self.update()

    def mouseMoveEvent(self, e):
        if not self._drag or not self._crop:
            return
        kind, info = self._drag
        sp = self._to_source(e.position().x(), e.position().y())
        if kind == "move":
            ox, oy, orig = info
            dx, dy = sp.x() - ox, sp.y() - oy
            w = orig[2] - orig[0]
            h = orig[3] - orig[1]
            nl = max(0, min(self._src_w - w, orig[0] + dx))
            nt = max(0, min(self._src_h - h, orig[1] + dy))
            self._crop = [nl, nt, nl + w, nt + h]
        else:
            # resize: move the dragged corner. For a brand-new rectangle the
            # press point (crop[0:2]) stays anchored and only the opposite
            # corner follows the cursor.
            if kind == "nw":
                self._crop[0], self._crop[1] = sp.x(), sp.y()
            elif kind == "ne":
                self._crop[2], self._crop[1] = sp.x(), sp.y()
            elif kind == "sw":
                self._crop[0], self._crop[3] = sp.x(), sp.y()
            else:  # "se" or "new"
                self._crop[2], self._crop[3] = sp.x(), sp.y()
            self._normalize_and_lock(kind)
        self.update()
        self._emit()

    def mouseReleaseEvent(self, _):
        if self._drag and self._crop:
            # discard a too-small selection
            if abs(self._crop[2] - self._crop[0]) < 4 or abs(self._crop[3] - self._crop[1]) < 4:
                self._crop = None
                self._emit()
        self._drag = None
        self.update()

    def _normalize_and_lock(self, kind: str):
        l, t, r, b = self._crop
        l, r = sorted((l, r))
        t, b = sorted((t, b))
        if self.aspect_locked and r > l:
            # derive height from width to keep the screen aspect
            w = r - l
            h = w / ASPECT
            if kind in ("nw", "ne"):
                t = b - h
            else:
                b = t + h
        self._crop = [max(0, l), max(0, t), min(self._src_w, r), min(self._src_h, b)]

    def _emit(self):
        self.cropChanged.emit(self.current_crop())
