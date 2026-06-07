"""Right-hand panel: the 3 keyboard screens, a save target, and push controls.

Tiles pick the save target (the editor stays driven by the library). Saving
stages the current clip to the selected screen and pushes all screens to the
keyboard; clearing drops a screen and re-pushes the rest.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from ..theme import PALETTE
from .marquee import MarqueeLabel

THUMB_W, THUMB_H = 128, 73  # ~240x136 aspect, sized to sit centered in the tile


class SlotTile(QFrame):
    """A clickable screen slot showing its thumbnail (or 'Empty')."""

    clicked = Signal(int)

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.setObjectName("slotTile")
        self.setProperty("selected", False)
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)
        self.thumb = QLabel()
        self.thumb.setObjectName("slotThumb")
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setFixedSize(THUMB_W, THUMB_H)
        self.cap = MarqueeLabel("Screen %d" % (index + 1),
                                color=PALETTE["muted"], align=Qt.AlignHCenter)
        self.cap.setObjectName("slotCap")
        self.cap.setFixedSize(THUMB_W, 16)
        cap_font = QFont(self.cap.font())
        cap_font.setPixelSize(11)
        self.cap.setFont(cap_font)
        lay.addWidget(self.thumb, 0, Qt.AlignHCenter)
        lay.addWidget(self.cap, 0, Qt.AlignHCenter)
        self.set_content(None, "")

    def mousePressEvent(self, _event) -> None:  # noqa: N802 (Qt signature)
        self.clicked.emit(self.index)

    def set_content(self, pixmap: Optional[QPixmap], name: str) -> None:
        if pixmap is not None and not pixmap.isNull():
            self.thumb.setPixmap(pixmap.scaled(
                THUMB_W, THUMB_H, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.thumb.setProperty("empty", False)
            self.cap.setText("Screen %d · %s" % (self.index + 1, name) if name
                             else "Screen %d" % (self.index + 1))
        else:
            self.thumb.clear()
            self.thumb.setText("Empty")
            self.thumb.setProperty("empty", True)
            self.cap.setText("Screen %d" % (self.index + 1))
        self.thumb.style().unpolish(self.thumb)
        self.thumb.style().polish(self.thumb)

    def set_selected(self, on: bool) -> None:
        self.setProperty("selected", on)
        self.style().unpolish(self)
        self.style().polish(self)


class ScreensPanel(QFrame):
    """Card holding the 3 screen tiles plus Save / Clear and a progress bar."""

    selected = Signal(int)
    save_clicked = Signal()
    clear_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.setFixedWidth(186)
        self._selected = 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)
        title = QLabel("Screens")
        title.setObjectName("cardTitle")
        lay.addWidget(title)

        self.tiles = []
        for i in range(3):
            tile = SlotTile(i)
            tile.clicked.connect(self._on_tile)
            self.tiles.append(tile)
            lay.addWidget(tile)
        lay.addStretch(1)

        self.btn_save = QPushButton("Save to Screen 1")
        self.btn_save.setObjectName("primary")
        self.btn_save.clicked.connect(self.save_clicked)
        lay.addWidget(self.btn_save)

        self.btn_clear = QPushButton("Clear screen")
        self.btn_clear.setObjectName("ghost")
        self.btn_clear.clicked.connect(self.clear_clicked)
        lay.addWidget(self.btn_clear)

        self._refresh_selection()

    def _on_tile(self, index: int) -> None:
        self._selected = index
        self._refresh_selection()
        self.selected.emit(index)

    def _refresh_selection(self) -> None:
        for i, tile in enumerate(self.tiles):
            tile.set_selected(i == self._selected)
        self.btn_save.setText("Save to Screen %d" % (self._selected + 1))

    def selected_index(self) -> int:
        return self._selected

    def set_slot(self, index: int, pixmap: Optional[QPixmap], name: str) -> None:
        self.tiles[index].set_content(pixmap, name)
