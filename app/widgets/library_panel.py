"""Library panel: import GIF/image/video, list saved clips, select/remove."""
from __future__ import annotations

import os
import tempfile
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QGroupBox, QHBoxLayout, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from rt98.library import Library, LibraryItem
from rt98.video import VideoOptions, ffmpeg_available, video_to_gif

IMAGE_FILTER = "Images & GIFs (*.gif *.png *.jpg *.jpeg *.bmp *.webp);;All files (*)"
VIDEO_FILTER = "Video (*.mp4 *.mov *.mkv *.avi *.webm *.gif);;All files (*)"


class VideoImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video -> GIF options")
        form = QFormLayout(self)
        self.fps = QSpinBox(); self.fps.setRange(2, 50); self.fps.setValue(15)
        self.width = QSpinBox(); self.width.setRange(0, 1920); self.width.setValue(240)
        self.width.setSpecialValueText("source")
        self.start = QDoubleSpinBox(); self.start.setRange(0, 100000); self.start.setSuffix(" s")
        self.duration = QDoubleSpinBox(); self.duration.setRange(0, 100000); self.duration.setSuffix(" s")
        self.duration.setSpecialValueText("to end")
        form.addRow("FPS", self.fps)
        form.addRow("Width (px)", self.width)
        form.addRow("Start", self.start)
        form.addRow("Duration", self.duration)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        form.addRow(bb)

    def options(self) -> VideoOptions:
        return VideoOptions(
            fps=self.fps.value(),
            width=self.width.value() or None,
            start=self.start.value(),
            duration=self.duration.value() or None,
        )


class LibraryPanel(QWidget):
    selected = Signal(object)   # LibraryItem or None
    changed = Signal()

    def __init__(self, library: Library, parent=None):
        super().__init__(parent)
        self.library = library
        root = QVBoxLayout(self)
        box = QGroupBox("GIF library")
        bv = QVBoxLayout(box)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._on_row)
        bv.addWidget(self.list)

        btns = QHBoxLayout()
        self.btn_img = QPushButton("Import GIF / image")
        self.btn_vid = QPushButton("Import video")
        self.btn_del = QPushButton("Remove")
        btns.addWidget(self.btn_img); btns.addWidget(self.btn_vid); btns.addWidget(self.btn_del)
        bv.addLayout(btns)
        root.addWidget(box)

        self.btn_img.clicked.connect(self._import_image)
        self.btn_vid.clicked.connect(self._import_video)
        self.btn_del.clicked.connect(self._remove)
        self.reload()

    def reload(self):
        self.list.blockSignals(True)
        self.list.clear()
        for it in self.library.items:
            row = QListWidgetItem(it.name)
            row.setData(256, it.id)
            self.list.addItem(row)
        self.list.blockSignals(False)

    def current_item(self) -> Optional[LibraryItem]:
        row = self.list.currentItem()
        return self.library.get(row.data(256)) if row else None

    def select_id(self, item_id: str):
        for i in range(self.list.count()):
            if self.list.item(i).data(256) == item_id:
                self.list.setCurrentRow(i)
                return

    def _on_row(self, _row: int):
        self.selected.emit(self.current_item())

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
            name = os.path.splitext(os.path.basename(path))[0]
            item = self.library.add(out, name=name)
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
