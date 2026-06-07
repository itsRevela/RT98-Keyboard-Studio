"""RT98 HID device transport: discovery, screen wake, time sync, qgif upload."""
from __future__ import annotations

import time
from datetime import datetime
from typing import Callable, Optional

try:
    import hid
except ImportError as exc:  # pragma: no cover
    raise ImportError("hidapi is required: pip install hidapi") from exc

from . import protocol as P


class DeviceError(RuntimeError):
    """Raised for device communication / state problems."""


def _find_path(vid: int, pid: int, usage_page: int, usage: int) -> Optional[bytes]:
    for info in hid.enumerate(vid, pid):
        if info.get("usage_page") == usage_page and info.get("usage") == usage:
            return info["path"]
    return None


def keyboard_present() -> bool:
    """True if the RT98 keyboard's control interface is connected."""
    return _find_path(P.KB_VID, P.KB_PID, P.KB_USAGE_PAGE, P.KB_USAGE) is not None


def screen_present() -> bool:
    """True if the screen module's USB device is currently enumerated."""
    return _find_path(P.SCREEN_VID, P.SCREEN_PID, P.SCREEN_USAGE_PAGE, P.SCREEN_USAGE) is not None


class RT98Device:
    """Talks to the RT98 screen module (waking it via the keyboard if needed).

    Use as a context manager:

        with RT98Device() as dev:
            dev.sync_time()
    """

    def __init__(self, wake_timeout: float = 15.0):
        self.wake_timeout = wake_timeout
        self._screen = None  # type: Optional[hid.device]

    # -- lifecycle -------------------------------------------------------------
    def __enter__(self) -> "RT98Device":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> None:
        from . import transport
        path = self._ensure_screen_path()
        dev = transport.open_hid(path, P.SCREEN_VID, P.SCREEN_PID)
        self._screen = dev
        # A "patient" transport (Windows overlapped writer, Linux hidraw) avoids
        # hidapi's ~1s write timeout that freezes the screen mid-upload. Since we
        # can only hardware-test Windows, validate the transport actually talks to
        # the screen and transparently fall back to stock hidapi if it doesn't.
        if getattr(dev, "patient", False) and not self._screen_responds():
            try:
                dev.close()
            except Exception:
                pass
            self._screen = transport.open_hidapi(path)

    def _screen_responds(self) -> bool:
        try:
            size = self.screen_size()
            return bool(size and size.get("width", 0) > 0)
        except Exception:
            return False

    def close(self) -> None:
        if self._screen is not None:
            try:
                self._screen.close()
            finally:
                self._screen = None

    def _ensure_screen_path(self) -> bytes:
        """Return the screen device path, waking it via the keyboard if needed."""
        path = _find_path(P.SCREEN_VID, P.SCREEN_PID, P.SCREEN_USAGE_PAGE, P.SCREEN_USAGE)
        if path:
            return path
        kb_path = _find_path(P.KB_VID, P.KB_PID, P.KB_USAGE_PAGE, P.KB_USAGE)
        if not kb_path:
            raise DeviceError(
                "RT98 keyboard not found (VID 0x%04X). Plug it in via USB." % P.KB_VID
            )
        kb = hid.device()
        kb.open_path(kb_path)
        try:
            kb.write(bytes([P.REPORT_ID]) + P.build_payload(P.C_GET_MODE, P.KB_PLEN))
            waited = 0.0
            while waited < self.wake_timeout:
                kb.write(bytes([P.REPORT_ID]) + P.build_payload(P.C_OPEN_MODE, P.KB_PLEN))
                time.sleep(0.4)
                waited += 0.4
                path = _find_path(P.SCREEN_VID, P.SCREEN_PID, P.SCREEN_USAGE_PAGE, P.SCREEN_USAGE)
                if path:
                    return path
        finally:
            kb.close()
        raise DeviceError(
            "Screen module did not enumerate (VID 0x%04X). It may be detached or "
            "asleep; a full keyboard power-cycle usually fixes it." % P.SCREEN_VID
        )

    # -- low-level I/O ---------------------------------------------------------
    def _dev(self):
        if self._screen is None:
            raise DeviceError("device is not open")
        return self._screen

    # Transient Windows overlapped-I/O hiccups that are safe to retry. Data
    # chunks carry their own flash address, so re-issuing one is idempotent.
    _TRANSIENT = ("0x000003E5", "overlapped", "pending", "i/o operation")

    def _raw_write(self, buf: bytes, attempts: int = 6) -> None:
        dev = self._dev()
        for i in range(attempts):
            if dev.write(buf) >= 0:
                return
            err = (dev.error() or "").lower()
            if any(tok in err for tok in self._TRANSIENT) and i < attempts - 1:
                time.sleep(0.003 * (i + 1))
                continue
            raise DeviceError("HID write failed: %s" % (dev.error() or "unknown"))

    def _write(self, payload: bytes, read: bool = True, timeout: int = 1000) -> bytes:
        dev = self._dev()
        self._raw_write(bytes([P.REPORT_ID]) + payload)
        if read:
            data = dev.read(P.SCREEN_PLEN + 1, timeout)
            return bytes(data) if data else b""
        return b""

    def _cmd(self, cmd: int, body: dict | None = None) -> bytes:
        return self._write(P.build_payload(cmd, P.SCREEN_PLEN, body))

    def _prep_flash(self, slots: int = 1) -> None:
        """Tell the keyboard to prepare/reset the screen flash for a download.

        The official tool sends this (0xAA 0xE3) to the keyboard's control
        interface between START_DOWNLOAD and SESSION_INIT. Without it, a second
        download started while the screen is already awake stalls at PREP2 and
        the first data write hangs (the screen never drained the write). ``slots``
        is the number of screen slots in the upcoming address table.
        """
        kb_path = _find_path(P.KB_VID, P.KB_PID, P.KB_USAGE_PAGE, P.KB_USAGE)
        if not kb_path:
            raise DeviceError(
                "RT98 keyboard not found (VID 0x%04X) for flash prepare." % P.KB_VID
            )
        kb = hid.device()
        kb.open_path(kb_path)
        try:
            kb.write(bytes([P.REPORT_ID]) + P.build_payload(
                P.C_PREP_FLASH, P.KB_PLEN, {5: 0x01, 8: slots}))
        finally:
            kb.close()

    # -- queries ---------------------------------------------------------------
    def screen_size(self) -> Optional[dict]:
        self._cmd(P.C_PREPARE)
        resp = self._cmd(P.C_GET_SIZE, {5: P.FIXED})
        self._cmd(P.C_APPLY)
        return P.parse_screen_size(resp)

    def connect_status(self) -> Optional[int]:
        resp = self._cmd(P.C_GET_CONNECT)
        return resp[9] if len(resp) > 9 else None

    def is_alive(self) -> bool:
        size = self.screen_size()
        return bool(size and size["width"] > 0)

    # -- actions ---------------------------------------------------------------
    def sync_time(self, when: Optional[datetime] = None) -> datetime:
        when = when or datetime.now()
        self._cmd(P.C_PREPARE)
        self._cmd(P.C_SET_TIME, P.time_body(when))
        self._cmd(P.C_APPLY)
        return when

    def upload_qgif(
        self,
        data: bytes,
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Upload one qgif as the screen's only slot (ERASES + writes flash)."""
        self.upload_slots([data], progress=progress)

    def upload_slots(
        self,
        slots: list[bytes],
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Upload up to 3 qgif blobs as the screen's slot list (ERASES + rewrites).

        Mirrors the official tool: a single flash-download session whose address
        table describes every slot, erasing and rewriting the whole region.
        ``slots`` is the ordered list of qgif blobs (slot 0 first); empty/falsy
        entries are skipped. Each slot is laid out on a 64 KB block boundary, so
        slot ``i`` starts at the cumulative block count of the slots before it.
        """
        slots = [s for s in slots if s]
        if not slots:
            raise DeviceError("no slots to upload")
        if len(slots) > 3:
            raise DeviceError("the screen holds at most 3 slots")

        sizes = [len(s) for s in slots]
        blocks = [(sz + P.FLASH_BLOCK - 1) // P.FLASH_BLOCK for sz in sizes]
        offsets: list[int] = []
        acc = 0
        for b in blocks:
            offsets.append(acc)
            acc += b
        total_blocks = acc
        count = len(slots)

        self._cmd(P.C_START_DOWNLOAD, {5: P.FIXED})
        self._prep_flash(count)  # 0xE3 to the keyboard: reset flash so repeat uploads don't stall
        self._cmd(P.C_SESSION_INIT, {5: P.FIXED})

        table = {5: P.FIXED, 8: 0, 9: count, 10: total_blocks}
        for i, (off_blocks, sz) in enumerate(zip(offsets, sizes)):
            b = 11 + 5 * i  # per-slot entry: [blockOffset, 0, size(3 bytes LE)]
            table[b] = off_blocks
            table[b + 1] = 0
            table[b + 2] = sz & 0xFF
            table[b + 3] = (sz >> 8) & 0xFF
            table[b + 4] = (sz >> 16) & 0xFF
        self._cmd(P.C_ADDR_TABLE, table)
        self._cmd(P.C_ADDR_TABLE, {2: 0x38, 5: 0x38})
        self._cmd(P.C_ADDR_TABLE, {2: 0x70, 5: 0x10})
        self._cmd(P.C_PREP2, {5: P.FIXED})
        self._cmd(P.C_ERASE, {5: 0x01, 8: total_blocks})
        time.sleep(0.5 * total_blocks + 0.6)  # flash erase ~500ms/block

        grand_total = sum(sizes)
        done = 0
        n = 0
        for data, off_blocks in zip(slots, offsets):
            base = off_blocks * P.FLASH_BLOCK
            size = len(data)
            off = 0
            while off < size:
                chunk = data[off:off + P.DATA_CHUNK]
                addr = base + off
                body = {2: addr & 0xFF, 3: (addr >> 8) & 0xFF,
                        4: (addr >> 16) & 0xFF, 5: len(chunk)}
                payload = bytearray(P.build_payload(P.C_DATA, P.SCREEN_PLEN, body))
                payload[8:8 + len(chunk)] = chunk
                self._write(bytes(payload))
                off += len(chunk)
                done += len(chunk)
                n += 1
                if n % 16 == 0:
                    time.sleep(0.001)  # brief yield, like the official tool's batching
                if progress:
                    progress(done, grand_total)

        self._cmd(P.C_END_SESSION)
        self.sync_time()
        self._cmd(P.C_APPLY)
