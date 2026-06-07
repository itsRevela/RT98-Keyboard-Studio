"""Patient Windows HID transport (ctypes).

`hidapi`'s `hid_write` waits only ~1 s for a write to complete. The RT98 screen
pauses to program flash during a multi-block GIF upload, so a write can take
longer than that - hidapi then errors and the half-finished session leaves the
screen frozen. The browser-based tool works because WebHID waits indefinitely.

This module opens the device directly and uses overlapped I/O with a generous
write timeout (default 30 s), matching that patient behavior. Same framing as
hidapi: ``write(buf)`` takes ``[report_id] + payload``; ``read`` returns the
payload with the leading report-id byte stripped.

Windows only. On other platforms, callers should fall back to ``hid.device``.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as wt

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
ERROR_IO_PENDING = 997
WAIT_OBJECT_0 = 0x00000000
WRITE_TIMEOUT_MS = 30000  # generous: covers flash-program stalls, not infinite

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)


class _OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_void_p), ("InternalHigh", ctypes.c_void_p),
        ("Offset", wt.DWORD), ("OffsetHigh", wt.DWORD), ("hEvent", wt.HANDLE),
    ]


_CreateFileW = _k32.CreateFileW
_CreateFileW.restype = wt.HANDLE
_CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
_CreateEventW = _k32.CreateEventW
_CreateEventW.restype = wt.HANDLE
_CreateEventW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR]
_WriteFile = _k32.WriteFile
_WriteFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
_ReadFile = _k32.ReadFile
_ReadFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
_GetOverlappedResult = _k32.GetOverlappedResult
_GetOverlappedResult.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(wt.DWORD), wt.BOOL]
_WaitForSingleObject = _k32.WaitForSingleObject
_WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
_WaitForSingleObject.restype = wt.DWORD
_ResetEvent = _k32.ResetEvent
_ResetEvent.argtypes = [wt.HANDLE]
_CancelIo = _k32.CancelIo
_CancelIo.argtypes = [wt.HANDLE]
_CloseHandle = _k32.CloseHandle
_CloseHandle.argtypes = [wt.HANDLE]

_INVALID = wt.HANDLE(-1).value


class WinHidDevice:
    """Minimal overlapped-I/O HID device handle with patient writes."""

    def __init__(self):
        self.h = None
        self._wev = None
        self._rev = None
        self._err = ""

    def open_path(self, path) -> None:
        p = path.decode() if isinstance(path, (bytes, bytearray)) else str(path)
        h = _CreateFileW(p, GENERIC_READ | GENERIC_WRITE,
                         FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING,
                         FILE_FLAG_OVERLAPPED, None)
        if not h or h == _INVALID:
            raise OSError("CreateFile failed for HID path (err %d)" % ctypes.get_last_error())
        self.h = h
        self._wev = _CreateEventW(None, True, False, None)
        self._rev = _CreateEventW(None, True, False, None)

    def error(self) -> str:
        return self._err

    def write(self, data) -> int:
        """Write ``[report_id] + payload``; wait up to WRITE_TIMEOUT_MS. -1 on error."""
        try:
            buf = bytes(data)
            ol = _OVERLAPPED()
            ol.hEvent = self._wev
            _ResetEvent(self._wev)
            written = wt.DWORD(0)
            ok = _WriteFile(self.h, buf, len(buf), ctypes.byref(written), ctypes.byref(ol))
            if not ok:
                err = ctypes.get_last_error()
                if err != ERROR_IO_PENDING:
                    self._err = "WriteFile error %d" % err
                    return -1
                rc = _WaitForSingleObject(self._wev, WRITE_TIMEOUT_MS)
                if rc != WAIT_OBJECT_0:
                    _CancelIo(self.h)
                    _GetOverlappedResult(self.h, ctypes.byref(ol), ctypes.byref(written), True)
                    self._err = "write timed out after %d ms" % WRITE_TIMEOUT_MS
                    return -1
                if not _GetOverlappedResult(self.h, ctypes.byref(ol), ctypes.byref(written), False):
                    self._err = "GetOverlappedResult(write) error %d" % ctypes.get_last_error()
                    return -1
            return int(written.value)
        except Exception as exc:  # pragma: no cover
            self._err = str(exc)
            return -1

    def read(self, size: int, timeout_ms: int = 1000) -> bytes:
        """Read one input report (timeout in ms); returns payload without report id."""
        try:
            buf = ctypes.create_string_buffer(size)
            ol = _OVERLAPPED()
            ol.hEvent = self._rev
            _ResetEvent(self._rev)
            nread = wt.DWORD(0)
            ok = _ReadFile(self.h, buf, size, ctypes.byref(nread), ctypes.byref(ol))
            if not ok:
                err = ctypes.get_last_error()
                if err != ERROR_IO_PENDING:
                    return b""
                rc = _WaitForSingleObject(self._rev, int(timeout_ms))
                if rc != WAIT_OBJECT_0:
                    _CancelIo(self.h)
                    _GetOverlappedResult(self.h, ctypes.byref(ol), ctypes.byref(nread), True)
                    return b""
                if not _GetOverlappedResult(self.h, ctypes.byref(ol), ctypes.byref(nread), False):
                    return b""
            raw = buf.raw[:nread.value]
            return raw[1:] if raw else b""  # strip leading report-id byte (match hidapi)
        except Exception:  # pragma: no cover
            return b""

    def close(self) -> None:
        for handle in (self.h, self._wev, self._rev):
            if handle:
                _CloseHandle(handle)
        self.h = self._wev = self._rev = None
