"""Main window: top bar · thumbnail rail · editor stage · bottom control dock."""
from __future__ import annotations

import copy
from io import BytesIO
from typing import Optional

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel,
                               QMessageBox, QProgressBar, QPushButton,
                               QSizePolicy, QSlider, QVBoxLayout, QWidget)

from rt98 import (Clip, EditState, RT98Device, bake_frames, default_encoder, effective_fps,
                  keyboard_present, load_clip, screen_present, settings, timezones)
from rt98.library import Library, LibraryItem
from rt98.slots import SlotStore

from .device_worker import DeviceTask
from .qt_util import pause_icon, play_icon
from .theme import PALETTE
from .widgets.controls import ControlsPanel
from .widgets.cropcanvas import CropCanvas
from .widgets.preview import OutputPreview
from .widgets.slotspanel import ScreensPanel
from .widgets.thumbrail import ThumbRail


def _card(title: str, body: QWidget) -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(12, 10, 12, 12)
    lay.setSpacing(8)
    cap = QLabel(title)
    cap.setObjectName("cardTitle")
    lay.addWidget(cap)
    lay.addWidget(body, 1)
    return frame


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("RT98 Studio")
        self.resize(1200, 780)

        self.library = Library()
        self.slots = SlotStore()
        self._clip: Optional[Clip] = None
        self._item: Optional[LibraryItem] = None
        self._edit = EditState()
        self._idx = 0
        self._target_slot = 0
        self._task: Optional[DeviceTask] = None

        self._build_ui()
        self._load_slot_tiles()

        self._anim = QTimer(self)
        self._anim.timeout.connect(self._tick)
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(2000)
        self._refresh_status()
        self._set_editing_enabled(False)

    # ----- UI -----------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_topbar())

        body = QHBoxLayout()
        body.setContentsMargins(16, 16, 16, 16)
        body.setSpacing(16)

        self.rail = ThumbRail(self.library)
        self.rail.selected.connect(self._on_select)
        body.addWidget(self.rail)

        editor = QVBoxLayout()
        editor.setSpacing(14)

        stage = QHBoxLayout()
        stage.setSpacing(16)
        self.crop = CropCanvas()
        self.crop.cropChanged.connect(self._on_crop)
        self.preview = OutputPreview(scale=2)
        self.screens = ScreensPanel()
        self.screens.selected.connect(self._on_slot_selected)
        self.screens.save_clicked.connect(self._save_to_slot)
        self.screens.clear_clicked.connect(self._clear_slot)
        stage.addWidget(_card("Source · drag to crop", self.crop), 1)
        stage.addWidget(_card("Keyboard preview · 240×136", self.preview), 1)
        stage.addWidget(self.screens)
        editor.addLayout(stage, 1)

        editor.addLayout(self._build_playbar())
        editor.addWidget(self._build_dock())
        body.addLayout(editor, 1)
        root.addLayout(body, 1)

    def _build_topbar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(58)
        h = QHBoxLayout(bar)
        h.setContentsMargins(20, 0, 20, 0)
        h.setSpacing(6)
        self.dot = QLabel("●")
        self.dot.setObjectName("statusDot")
        self.dot.setAlignment(Qt.AlignCenter)
        self.dot.setProperty("state", "off")
        title = QLabel("RT98 Studio")
        title.setObjectName("appTitle")
        h.addWidget(self.dot)
        h.addWidget(title)
        h.addStretch(1)
        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("statusText")
        h.addWidget(self.lbl_status)
        h.addWidget(self._build_tz_combo())
        self.btn_sync = QPushButton("Sync time")
        self.btn_sync.clicked.connect(self._sync_time)
        h.addWidget(self.btn_sync)
        return bar

    def _build_tz_combo(self) -> QComboBox:
        combo = QComboBox()
        self.tz_combo = combo
        zones = timezones.available_zones()
        self._zone_set = set(zones)
        combo.setFixedWidth(200)
        combo.setMaxVisibleItems(20)
        combo.setToolTip("Time zone used by Sync time")
        combo.addItem(timezones.LOCAL)
        combo.addItems(zones)
        saved = settings.get("timezone", timezones.LOCAL)
        idx = combo.findText(saved)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        # connect after setting the saved value so it isn't re-persisted on init
        combo.currentTextChanged.connect(lambda _t: self._persist_tz())
        return combo

    def _persist_tz(self):
        text = self.tz_combo.currentText()
        if text == timezones.LOCAL or text in self._zone_set:
            settings.set("timezone", text)

    def _build_playbar(self):
        h = QHBoxLayout()
        h.setContentsMargins(2, 6, 2, 6)
        h.setSpacing(12)
        self._ico_play = play_icon(PALETTE["text"], 18)
        self._ico_pause = pause_icon(PALETTE["text"], 18)
        self.btn_play = QPushButton()
        self.btn_play.setObjectName("round")
        self.btn_play.setFixedSize(40, 40)
        self.btn_play.setIcon(self._ico_play)
        self.btn_play.setIconSize(QSize(18, 18))
        self.btn_play.clicked.connect(self._toggle_play)
        self.scrub = QSlider(Qt.Horizontal)
        self.scrub.setRange(0, 0)
        self.scrub.valueChanged.connect(self._on_scrub)
        self.lbl_info = QLabel("")
        self.lbl_info.setObjectName("muted")
        h.addWidget(self.btn_play)
        h.addWidget(self.scrub, 1)
        h.addWidget(self.lbl_info)
        return h

    def _build_dock(self) -> QFrame:
        dock = QFrame()
        dock.setObjectName("dock")
        h = QHBoxLayout(dock)
        h.setContentsMargins(18, 14, 18, 14)
        h.setSpacing(16)
        self.controls = ControlsPanel()
        self.controls.changed.connect(self._on_controls)
        self.controls.clear_crop.clicked.connect(self._clear_crop)
        self.controls.reset.clicked.connect(self._reset_edits)
        h.addWidget(self.controls, 1)

        right = QVBoxLayout()
        right.setSpacing(8)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        # Fill the button's column width when shown instead of forcing a wider
        # one (which previously grew the dock and widened the whole window).
        self.progress.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.btn_send = QPushButton("Send to keyboard")
        self.btn_send.setObjectName("primary")
        self.btn_send.clicked.connect(self._send)
        right.addStretch(1)
        right.addWidget(self.progress)
        right.addWidget(self.btn_send)
        h.addLayout(right)
        return dock

    # ----- editing ------------------------------------------------------------
    def _set_editing_enabled(self, on: bool):
        self.controls.set_enabled(on)
        self.btn_play.setEnabled(on)
        self.scrub.setEnabled(on)

    def _on_select(self, item: Optional[LibraryItem]):
        self._anim.stop()
        self._item = item
        if not item:
            self._clip = None
            self.crop.set_clip(None)
            self.preview.set_clip(None)
            self.lbl_info.setText("")
            self._set_editing_enabled(False)
            self._refresh_status()
            return
        try:
            self._clip = load_clip(item.source)
        except Exception as exc:
            QMessageBox.critical(self, "Load failed", str(exc))
            self._clip = None
            return
        self._edit = copy.deepcopy(item.edit)
        self._idx = 0
        self.controls.load(self._edit)
        self.crop.aspect_locked = self.controls.aspect.isChecked()
        self.crop.set_clip(self._clip)
        self.crop.set_crop(self._edit.crop)
        self.preview.set_clip(self._clip)
        self.preview.set_edit(self._edit)
        self.scrub.blockSignals(True)
        self.scrub.setRange(0, max(0, len(self._clip.frames) - 1))
        self.scrub.setValue(0)
        self.scrub.blockSignals(False)
        self._set_editing_enabled(True)
        self._restart_anim()
        self._refresh_status()

    def _on_controls(self):
        self.controls.apply_to(self._edit)
        self.crop.aspect_locked = self.controls.aspect.isChecked()
        self.preview.set_edit(self._edit)
        self._restart_anim()
        self._save_edit()

    def _on_crop(self, rect):
        self._edit.crop = rect
        self.preview.set_edit(self._edit)
        self._save_edit()

    def _clear_crop(self):
        self._edit.crop = None
        self.crop.set_crop(None)
        self.preview.set_edit(self._edit)
        self._save_edit()

    def _reset_edits(self):
        self._edit = EditState()
        self.controls.load(self._edit)
        self.crop.set_crop(None)
        self.preview.set_edit(self._edit)
        self._restart_anim()
        self._save_edit()

    def _save_edit(self):
        if self._item:
            self.library.update_edit(self._item.id, self._edit)

    # ----- animation ----------------------------------------------------------
    def _restart_anim(self):
        if not self._clip:
            self.lbl_info.setText("")
            return
        fps = effective_fps(self._clip, self._edit)
        w, hgt = self._clip.source_size
        self.lbl_info.setText(f"{len(self._clip.frames)} frames · {fps} fps · {w}×{hgt}")
        self._anim.start(max(16, int(1000 / fps)))
        self.btn_play.setIcon(self._ico_pause)

    def _tick(self):
        if not self._clip:
            return
        self._idx = (self._idx + 1) % len(self._clip.frames)
        self.crop.set_frame(self._idx)
        self.preview.set_frame(self._idx)
        self.scrub.blockSignals(True)
        self.scrub.setValue(self._idx)
        self.scrub.blockSignals(False)

    def _toggle_play(self):
        if self._anim.isActive():
            self._anim.stop()
            self.btn_play.setIcon(self._ico_play)
        elif self._clip:
            self._restart_anim()

    def _on_scrub(self, value: int):
        # only fires on user interaction (tick updates are blocked)
        if not self._clip:
            return
        self._anim.stop()
        self.btn_play.setIcon(self._ico_play)
        self._idx = value % len(self._clip.frames)
        self.crop.set_frame(self._idx)
        self.preview.set_frame(self._idx)

    # ----- device -------------------------------------------------------------
    def _set_dot(self, state: str):
        self.dot.setProperty("state", state)
        self.dot.style().unpolish(self.dot)
        self.dot.style().polish(self.dot)

    def _refresh_status(self):
        if self._task is not None:
            return  # never enumerate USB while a transfer is running
        kb = keyboard_present()
        scr = screen_present()
        self._set_dot("on" if kb else "off")
        txt = "USB connected" if kb else "keyboard not found"
        if scr:
            txt += " · screen awake"
        self.lbl_status.setText(txt)
        self._update_action_buttons(kb)

    def _update_action_buttons(self, kb: Optional[bool] = None):
        """Enable Sync/Save/Clear/Send based on device + staged state.

        Save and Clear are local (no device); only Sync and Send need the
        keyboard. Never called while a transfer is running except via the
        post-task refresh (so the keyboard enumerate stays off the wire mid-send).
        """
        if kb is None:
            kb = keyboard_present()
        busy = self._task is not None
        self.btn_sync.setEnabled(kb and not busy)
        self.screens.btn_save.setEnabled(self._clip is not None and not busy)
        self.screens.btn_clear.setEnabled(self.slots.is_set(self._target_slot) and not busy)
        self.btn_send.setEnabled(kb and bool(self.slots.occupied()) and not busy)

    def _set_busy_ui(self, on: bool, label: str = ""):
        self.progress.setVisible(on)
        if on:
            self.progress.setRange(0, 0)
            self._set_dot("busy")
            self.lbl_status.setText("%s…" % (label or "working"))
            for b in (self.btn_sync, self.btn_send,
                      self.screens.btn_save, self.screens.btn_clear):
                b.setEnabled(False)

    def _run_task(self, op, label: str, on_success=None):
        if self._task is not None:
            return
        self._status_timer.stop()
        task = DeviceTask(op, label, self)
        self._task = task
        self._set_busy_ui(True, label)
        task.progress.connect(self._on_progress)
        task.succeeded.connect(lambda res: self._task_done(label, None, res, on_success))
        task.failed.connect(lambda err: self._task_done(label, err))
        task.start()

    def _on_progress(self, done: int, total: int):
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)

    def _task_done(self, label: str, err: Optional[str], result=None, on_success=None):
        self._task = None
        self._set_busy_ui(False)
        if err:
            QMessageBox.critical(self, label + " failed", err)
        else:
            if on_success:
                on_success(result)
            if label.startswith("Sync"):
                msg = "time synced ✓"
            elif label.startswith("Save"):
                msg = "staged ✓"
            elif label.startswith("Clear"):
                msg = "screen cleared ✓"
            else:
                msg = "sent to keyboard ✓"
            self.lbl_status.setText(msg)
        self._update_action_buttons()
        self._status_timer.start(2000)

    def _sync_time(self):
        zone = self.tz_combo.currentText()
        def op(prog):
            with RT98Device() as dev:
                return dev.sync_time(timezones.now_in_zone(zone))
        self._run_task(op, "Sync time")

    def _on_slot_selected(self, index: int):
        self._target_slot = index
        self._update_action_buttons()

    def _load_slot_tiles(self):
        for i in range(SlotStore.COUNT):
            self._refresh_slot_tile(i)

    def _refresh_slot_tile(self, i: int):
        path = self.slots.thumb_path(i)
        pm = QPixmap(path) if path else None
        if pm is not None and pm.isNull():
            pm = None
        self.screens.set_slot(i, pm, self.slots.name(i))

    def _save_to_slot(self):
        """Stage the current clip onto the selected screen (encode + cache; no upload)."""
        if not self._clip:
            return
        target = self._target_slot
        clip = self._clip
        edit = copy.deepcopy(self._edit)
        name = self._item.name if self._item else "Screen %d" % (target + 1)
        item_id = self._item.id if self._item else None
        encoder = default_encoder()

        def op(_prog):
            frames = bake_frames(clip, edit)
            if len(frames) == 1:
                # The screen won't register a single-frame qgif as a cyclable
                # screen (slots 2/3 stay empty), so make a static image animated.
                frames = frames * 2
            qgif = encoder.encode(frames, effective_fps(clip, edit))
            buf = BytesIO()
            frames[0].save(buf, format="PNG")
            return qgif, buf.getvalue()

        def done(result):
            qgif, thumb_png = result
            self.slots.assign(target, qgif, thumb_png, name, item_id)
            self._refresh_slot_tile(target)

        self._run_task(op, "Save to Screen %d" % (target + 1), on_success=done)

    def _clear_slot(self):
        """Drop the selected screen from the staged set (applies on the next send)."""
        i = self._target_slot
        if not self.slots.is_set(i):
            return
        self.slots.clear(i)
        self._refresh_slot_tile(i)
        self._update_action_buttons()
        self.lbl_status.setText("screen %d cleared" % (i + 1))

    def _send(self):
        """Push every staged screen to the keyboard (rewrites all slots at once)."""
        upload = [self.slots.qgif_bytes(i)
                  for i in range(SlotStore.COUNT) if self.slots.is_set(i)]
        upload = [b for b in upload if b]
        if not upload:
            QMessageBox.information(self, "Nothing to send",
                                    "Save at least one screen first.")
            return

        def op(prog):
            with RT98Device() as dev:
                dev.upload_slots(upload, progress=prog)
            return len(upload)

        self._anim.stop()
        self.btn_play.setIcon(self._ico_play)
        self._run_task(op, "Send to keyboard")
