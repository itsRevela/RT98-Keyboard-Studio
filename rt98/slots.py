"""Screen-slot store: the up-to-3 screens the keyboard cycles with FN+Shift.

The device's flash download rewrites every slot at once (the official tool sends
an address table listing all screens and re-sends them all), and the stored
image data can't be read back. So this app keeps its own copy of each saved
screen - the encoded qgif plus a thumbnail and a label - under the per-user
app-data dir, and pushes the whole set on every save.
"""
from __future__ import annotations

import json
import os
from typing import List, Optional

from .library import app_data_dir

COUNT = 3  # the firmware's GIF_PIC_MAX


class SlotStore:
    """Persistent set of up to :data:`COUNT` screen slots.

    Each occupied slot has a cached ``slot{i}.qgif`` (the bytes to upload) and a
    ``slot{i}.png`` thumbnail, plus a small metadata record (name, source id).
    """

    COUNT = COUNT

    def __init__(self, root: Optional[str] = None):
        self.root = root or os.path.join(app_data_dir(), "slots")
        os.makedirs(self.root, exist_ok=True)
        self.index_path = os.path.join(self.root, "index.json")
        self._meta: List[Optional[dict]] = [None] * COUNT
        self.load()

    # -- paths -----------------------------------------------------------------
    def qgif_path(self, i: int) -> str:
        return os.path.join(self.root, "slot%d.qgif" % i)

    def thumb_path(self, i: int) -> Optional[str]:
        p = os.path.join(self.root, "slot%d.png" % i)
        return p if (self.is_set(i) and os.path.isfile(p)) else None

    # -- persistence -----------------------------------------------------------
    def load(self) -> None:
        self._meta = [None] * COUNT
        if not os.path.isfile(self.index_path):
            return
        try:
            with open(self.index_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            saved = data.get("slots", [])
            for i in range(COUNT):
                m = saved[i] if i < len(saved) else None
                # only honor a slot whose cached qgif still exists
                if m and os.path.isfile(self.qgif_path(i)):
                    self._meta[i] = m
        except (OSError, ValueError, KeyError):
            self._meta = [None] * COUNT

    def save(self) -> None:
        tmp = self.index_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"slots": self._meta}, fh, indent=2)
        os.replace(tmp, self.index_path)

    # -- queries ---------------------------------------------------------------
    def is_set(self, i: int) -> bool:
        return 0 <= i < COUNT and self._meta[i] is not None

    def name(self, i: int) -> str:
        return (self._meta[i] or {}).get("name", "") if self.is_set(i) else ""

    def item_id(self, i: int) -> Optional[str]:
        return (self._meta[i] or {}).get("item_id") if self.is_set(i) else None

    def qgif_bytes(self, i: int) -> Optional[bytes]:
        if not self.is_set(i):
            return None
        try:
            with open(self.qgif_path(i), "rb") as fh:
                return fh.read()
        except OSError:
            return None

    def occupied(self) -> List[int]:
        return [i for i in range(COUNT) if self.is_set(i)]

    # -- mutations -------------------------------------------------------------
    def assign(self, i: int, qgif: bytes, thumb_png: bytes,
               name: str, item_id: Optional[str] = None) -> None:
        if not (0 <= i < COUNT):
            raise IndexError("slot index out of range: %d" % i)
        with open(self.qgif_path(i), "wb") as fh:
            fh.write(qgif)
        with open(os.path.join(self.root, "slot%d.png" % i), "wb") as fh:
            fh.write(thumb_png)
        self._meta[i] = {"name": name, "item_id": item_id}
        self.save()

    def clear(self, i: int) -> None:
        for p in (self.qgif_path(i), os.path.join(self.root, "slot%d.png" % i)):
            try:
                os.remove(p)
            except OSError:
                pass
        if 0 <= i < COUNT:
            self._meta[i] = None
        self.save()
