"""HID transport selection - a patient writer per platform.

The screen's multi-block GIF upload needs writes that wait as long as the device
takes to program flash. Whether the stock hidapi write is "patient" depends on
the platform/backend:

* Windows  : hidapi waits only ~1 s  -> use :class:`~rt98.winhid.WinHidDevice`
             (overlapped ``WriteFile``, ~30 s).  [tested]
* macOS    : hidapi uses ``IOHIDDeviceSetReport`` (synchronous) -> already patient
             -> hidapi fallback.
* Linux    : hidraw backend uses a blocking ``write()`` (patient). To be robust
             regardless of how hidapi was built, when the device path is a
             ``/dev/hidraw*`` node we talk to it directly with blocking I/O
             (:class:`HidrawDevice`); otherwise hidapi fallback.

A custom transport is *self-validated* by the caller (a screen-size query): if it
misbehaves it is transparently replaced by hidapi. Set ``RT98_HID_BACKEND`` to
``hidapi`` / ``win`` / ``hidraw`` to force a choice.

Every transport exposes the hidapi-compatible surface used by ``device.py``:
``write(buf) -> int`` (``buf`` = ``[report_id] + payload``; -1 on error),
``read(size, timeout_ms) -> bytes`` (payload, report-id stripped), ``error() ->
str``, ``close()``.
"""
from __future__ import annotations

import os
import sys


def _pref() -> str:
    return os.environ.get("RT98_HID_BACKEND", "auto").lower()


def open_hidapi(path):
    import hid
    dev = hid.device()
    dev.open_path(path)
    dev.patient = False  # marker: stock hidapi, no self-validation needed
    return dev


def open_hid(path, vid: int, pid: int):
    """Open the best available transport for ``path``. May be self-validated."""
    pref = _pref()
    if pref == "hidapi":
        return open_hidapi(path)

    if sys.platform == "win32" and pref in ("auto", "win"):
        from .winhid import WinHidDevice
        dev = WinHidDevice()
        dev.open_path(path)
        dev.patient = True
        return dev

    if sys.platform.startswith("linux") and pref in ("auto", "hidraw"):
        node = _hidraw_node(path)
        if node is not None:
            try:
                dev = HidrawDevice()
                dev.open_path(node)
                dev.patient = True
                return dev
            except OSError:
                pass  # fall through to hidapi

    return open_hidapi(path)


def _hidraw_node(path):
    """Return a usable ``/dev/hidraw*`` node for the path, or None.

    On the hidraw backend hidapi already hands us the node directly; that's the
    case we can use confidently. (libusb-backend paths can't be mapped to a
    single hidraw interface reliably, so we defer to hidapi there.)
    """
    p = path.decode("utf-8", "ignore") if isinstance(path, (bytes, bytearray)) else str(path)
    if p.startswith("/dev/hidraw") and os.path.exists(p):
        return p
    return None


class HidrawDevice:
    """Blocking (patient) Linux hidraw transport via ``os`` syscalls."""

    def __init__(self):
        self.fd = -1
        self._err = ""

    def open_path(self, path) -> None:
        p = path.decode("utf-8", "ignore") if isinstance(path, (bytes, bytearray)) else str(path)
        self.fd = os.open(p, os.O_RDWR)

    def write(self, data) -> int:
        try:
            return os.write(self.fd, bytes(data))  # blocking == patient
        except OSError as exc:
            self._err = str(exc)
            return -1

    def read(self, size: int, timeout_ms: int = 1000) -> bytes:
        import select
        try:
            r, _, _ = select.select([self.fd], [], [], max(0.0, timeout_ms / 1000.0))
            if not r:
                return b""
            # hidraw returns the report with no leading id byte for unnumbered reports.
            return os.read(self.fd, size)
        except OSError as exc:
            self._err = str(exc)
            return b""

    def error(self) -> str:
        return self._err

    def close(self) -> None:
        if self.fd >= 0:
            try:
                os.close(self.fd)
            finally:
                self.fd = -1
