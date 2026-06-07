"""Timezone helpers for clock sync.

The screen shows whatever wall-clock time we send, so syncing a given timezone
just means sending *that zone's* current local time. ``LOCAL`` uses the system
clock.
"""
from __future__ import annotations

from datetime import datetime
from typing import List

LOCAL = "Local (system)"


def available_zones() -> List[str]:
    """Sorted IANA zone names (empty if no tz database is present)."""
    try:
        from zoneinfo import available_timezones
        return sorted(available_timezones())
    except Exception:
        return []


def now_in_zone(name: str) -> datetime:
    """Current time as a (naive-fielded) datetime for ``name``.

    Falls back to system local time for ``LOCAL`` / unknown / unavailable zones.
    """
    if not name or name == LOCAL:
        return datetime.now()
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(name))
    except Exception:
        return datetime.now()
