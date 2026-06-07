"""GIF library: imported source clips + their non-destructive edit settings.

Stored under the per-user app-data dir (e.g. %APPDATA%/RT98KeyboardSoftware),
so binaries stay out of the repo. Each entry keeps a copy of the source file and
an :class:`~rt98.imaging.EditState`.
"""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from .imaging import EditState


def app_data_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
    path = os.path.join(base, "RT98KeyboardSoftware")
    os.makedirs(path, exist_ok=True)
    return path


@dataclass
class LibraryItem:
    id: str
    name: str
    source: str               # absolute path to the stored source file
    edit: EditState = field(default_factory=EditState)
    added: float = 0.0

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "source": self.source,
                "edit": self.edit.to_dict(), "added": self.added}

    @classmethod
    def from_dict(cls, d: dict) -> "LibraryItem":
        return cls(id=d["id"], name=d["name"], source=d["source"],
                   edit=EditState.from_dict(d.get("edit", {})), added=d.get("added", 0.0))


class Library:
    """A simple JSON-indexed library of imported clips."""

    def __init__(self, root: Optional[str] = None):
        self.root = root or os.path.join(app_data_dir(), "library")
        self.sources_dir = os.path.join(self.root, "sources")
        os.makedirs(self.sources_dir, exist_ok=True)
        self.index_path = os.path.join(self.root, "index.json")
        self.items: List[LibraryItem] = []
        self.load()

    def load(self) -> None:
        self.items = []
        if os.path.isfile(self.index_path):
            try:
                with open(self.index_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                self.items = [LibraryItem.from_dict(d) for d in data.get("items", [])]
            except (OSError, ValueError, KeyError):
                self.items = []

    def save(self) -> None:
        tmp = self.index_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"items": [it.to_dict() for it in self.items]}, fh, indent=2)
        os.replace(tmp, self.index_path)

    def add(self, source_path: str, name: Optional[str] = None) -> LibraryItem:
        item_id = uuid.uuid4().hex[:12]
        ext = os.path.splitext(source_path)[1] or ".gif"
        stored = os.path.join(self.sources_dir, item_id + ext)
        shutil.copyfile(source_path, stored)
        item = LibraryItem(
            id=item_id,
            name=name or os.path.splitext(os.path.basename(source_path))[0],
            source=stored, edit=EditState(), added=time.time(),
        )
        self.items.append(item)
        self.save()
        return item

    def update_edit(self, item_id: str, edit: EditState) -> None:
        for it in self.items:
            if it.id == item_id:
                it.edit = edit
                self.save()
                return

    def rename(self, item_id: str, name: str) -> None:
        for it in self.items:
            if it.id == item_id:
                it.name = name
                self.save()
                return

    def remove(self, item_id: str) -> None:
        for it in list(self.items):
            if it.id == item_id:
                try:
                    os.remove(it.source)
                except OSError:
                    pass
                self.items.remove(it)
                self.save()
                return

    def get(self, item_id: str) -> Optional[LibraryItem]:
        return next((it for it in self.items if it.id == item_id), None)
