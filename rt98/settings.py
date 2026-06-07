"""Tiny JSON-backed app settings (stored in the per-user app-data dir)."""
from __future__ import annotations

import json
import os
from typing import Any

from .library import app_data_dir

_PATH = os.path.join(app_data_dir(), "settings.json")


def _load() -> dict:
    if os.path.isfile(_PATH):
        try:
            with open(_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            pass
    return {}


def get(key: str, default: Any = None) -> Any:
    return _load().get(key, default)


def set(key: str, value: Any) -> None:
    data = _load()
    data[key] = value
    tmp = _PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, _PATH)
