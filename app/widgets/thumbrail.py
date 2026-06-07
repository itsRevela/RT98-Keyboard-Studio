"""Library rail: a vertical column of clip thumbnails + import / remove."""
from __future__ import annotations

import os
import tempfile
from typing import Optional

from PIL import Image
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (QDialog, QFileDialog, QFrame, QLabel, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

from rt98.library import Library, LibraryItem
from rt98.video import ffmpeg_available, video_to_gif

from ..qt_util import pil_to_qpixmap
from ..theme import PALETTE
from .library_panel import IMAGE_FILTER, VIDEO_FILTER, VideoImportDialog
from .marquee import MarqueeLabel

THUMB = (108, 62)
_ID_ROLE = 256


def _thumb_pixmap(path: str) -> Optional[QPixmap]:
    try:
        im = Image.open(path)
        im.seek(0)
        frame = im.convert("RGB")
    except Exception:
        return None
    canvas = Image.new("RGB", THUMB, (44, 40, 35))
    sw, sh = frame.size
    scale = min(THUMB[0] / sw, THUMB[1] / sh) if sw and sh else 1.0
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    canvas.paste(frame.resize((nw, nh), Image.LANCZOS), ((THUMB[0] - nw) // 2, (THUMB[1] - nh) // 2))
    return pil_to_qpixmap(canvas)


class RailRow(QWidget):
    """A library entry: centered thumbnail with a scrolling filename below."""

    def __init__(self, name: str, pixmap: Optional[QPixmap]):
        super().__init__()
        self.setObjectName("railRow")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # let the list handle selection
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 6, 4, 8)
        v.setSpacing(6)
        thumb = QLabel()
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setFixedSize(*THUMB)
        thumb.setAttribute(Qt.WA_TransparentForMouseEvents)
        if pixmap is not None:
            thumb.setPixmap(pixmap)
        self.name = MarqueeLabel(name, color=PALETTE["text"], align=Qt.AlignHCenter)
        self.name.setFixedSize(THUMB[0] + 16, 18)
        name_font = QFont(self.name.font())
        name_font.setPixelSize(12)
        self.name.setFont(name_font)
        self.name.setAttribute(Qt.WA_TransparentForMouseEvents)
        v.addWidget(thumb, 0, Qt.AlignHCenter)
        v.addWidget(self.name, 0, Qt.AlignHCenter)
        v.addStretch(1)  # top-pack: any extra row height falls below the name, never over the thumb


class ThumbRail(QFrame):
    selected = Signal(object)   # LibraryItem or None
    changed = Signal()

    def __init__(self, library: Library, parent=None):
        super().__init__(parent)
        self.setObjectName("rail")
        self.setFixedWidth(176)
        self.library = library

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 14, 12, 12)
        v.setSpacing(8)
        title = QLabel("Library")
        title.setObjectName("cardTitle")
        v.addWidget(title)

        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ListMode)
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setSpacing(2)
        # Click-focus only: otherwise, when a focused button (e.g. Sync time) is
        # disabled during a transfer, focus jumps here and an empty list
        # auto-selects row 0, loading that clip into the editor unexpectedly.
        self.list.setFocusPolicy(Qt.ClickFocus)
        self.list.currentRowChanged.connect(lambda _r: self.selected.emit(self.current_item()))
        v.addWidget(self.list, 1)

        self.btn_img = QPushButton("+  GIF / Image")
        self.btn_vid = QPushButton("+  Video")
        self.btn_del = QPushButton("Remove")
        self.btn_del.setObjectName("danger")
        self.btn_del.setEnabled(False)
        for b in (self.btn_img, self.btn_vid, self.btn_del):
            v.addWidget(b)
        self.btn_img.clicked.connect(self._import_image)
        self.btn_vid.clicked.connect(self._import_video)
        self.btn_del.clicked.connect(self._remove)
        self.list.currentRowChanged.connect(lambda r: self.btn_del.setEnabled(r >= 0))
        self.reload()

    def reload(self):
        self.list.blockSignals(True)
        self.list.clear()
        for it in self.library.items:
            row = QListWidgetItem()
            row.setData(_ID_ROLE, it.id)
            # content (6+62+6+18+8 = 100) + the QSS item padding/margin overhead
            # (4px padding + 3px margin per side = 14) so the row widget isn't squished.
            row.setSizeHint(QSize(THUMB[0] + 20, THUMB[1] + 54))  # = 116
            row.setToolTip(it.name)
            self.list.addItem(row)
            self.list.setItemWidget(row, RailRow(it.name, _thumb_pixmap(it.source)))
        self.list.blockSignals(False)

    def current_item(self) -> Optional[LibraryItem]:
        row = self.list.currentItem()
        return self.library.get(row.data(_ID_ROLE)) if row else None

    def select_id(self, item_id: str):
        for i in range(self.list.count()):
            if self.list.item(i).data(_ID_ROLE) == item_id:
                self.list.setCurrentRow(i)
                return

    def _import_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import GIF or image", "", IMAGE_FILTER)
        if not path:
            return
        try:
            item = self.library.add(path)
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        self.reload(); self.select_id(item.id); self.changed.emit()

    def _import_video(self):
        if not ffmpeg_available():
            QMessageBox.warning(self, "ffmpeg not found",
                                "ffmpeg must be installed and on PATH to import video.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Import video", "", VIDEO_FILTER)
        if not path:
            return
        dlg = VideoImportDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        out = os.path.join(tempfile.mkdtemp(prefix="rt98vid_"), "converted.gif")
        try:
            video_to_gif(path, out, dlg.options())
            item = self.library.add(out, name=os.path.splitext(os.path.basename(path))[0])
        except Exception as exc:
            QMessageBox.critical(self, "Conversion failed", str(exc))
            return
        self.reload(); self.select_id(item.id); self.changed.emit()

    def _remove(self):
        item = self.current_item()
        if not item:
            return
        if QMessageBox.question(self, "Remove", f"Remove '{item.name}' from the library?") \
                == QMessageBox.Yes:
            self.library.remove(item.id)
            self.reload(); self.selected.emit(None); self.changed.emit()
