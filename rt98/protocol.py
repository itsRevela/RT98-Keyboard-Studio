"""RT98 screen wire protocol: device identities, report sizes, command builders.

Reverse-engineered from the official RT98 web tool (image.rdmctmzt.com) and a
live HID capture. Two USB devices are involved:

* Keyboard 0x36B0:0x30B9, vendor interface usage page 0xFF60 / usage 0x61
  (32-byte raw-HID reports). Used only to *wake* the screen.
* Screen module 0x1919:0x1919, vendor interface usage page 0x00FF / usage 0x01
  (64-byte reports). All real screen commands go here. It only enumerates after
  the keyboard receives the "open screen mode" command.

Every screen command payload starts with 0xAA followed by a command byte.
"""
from __future__ import annotations

from datetime import datetime

# --- Device identities --------------------------------------------------------
KB_VID, KB_PID = 0x36B0, 0x30B9
KB_USAGE_PAGE, KB_USAGE = 0xFF60, 0x0061
KB_PLEN = 32  # keyboard raw-HID payload size

SCREEN_VID, SCREEN_PID = 0x1919, 0x1919
SCREEN_USAGE_PAGE, SCREEN_USAGE = 0x00FF, 0x0001
SCREEN_PLEN = 64  # screen device payload size

REPORT_ID = 0x00

# --- Screen geometry ----------------------------------------------------------
# Panel is 240x135; frames are encoded at 240x136 because the qgif encoder
# requires width & height divisible by 4 (135 -> 136).
SCREEN_W = 240
SCREEN_H = 136
FLASH_BLOCK = 65536  # flash erase/region block size
DATA_CHUNK = 56      # image data bytes per report

# --- Command bytes (0xAA prefix) ----------------------------------------------
PREFIX = 0xAA
C_PREPARE = 0x10       # begin a query transaction
C_APPLY = 0x11         # commit / refresh
C_GET_SIZE = 0x12      # query screen size
C_SET_TIME = 0x17      # set clock (decimal-digit encoded)
C_END_SESSION = 0x1A   # end download / resume normal
C_START_DOWNLOAD = 0x1B
C_SESSION_INIT = 0x14  # begin a flash download session
C_ADDR_TABLE = 0x15    # screen layout / config writes
C_PREP2 = 0x16
C_GET_CONNECT = 0x1C   # connection status (byte 9: 2=USB)
C_ERASE = 0x18         # erase flash blocks
C_DATA = 0x19          # image data chunk
C_OPEN_MODE = 0xE0     # power on the screen's USB interface (sent to keyboard)
C_GET_MODE = 0xE2      # screen mode (byte 8: 1=open)
C_PREP_FLASH = 0xE3    # prepare/reset screen flash for a download (sent to keyboard;
                       #   byte 5 = 0x01, byte 8 = number of screen slots being written)
FIXED = 0x38           # constant placed at payload[5] for size/time/session cmds


def build_payload(cmd: int, length: int, body: dict[int, int] | None = None) -> bytes:
    """Build a screen payload ``[0xAA, cmd, ...]`` zero-padded to ``length``.

    ``body`` maps wire-payload byte offsets to values.
    """
    payload = bytearray(length)
    payload[0] = PREFIX
    payload[1] = cmd & 0xFF
    for offset, value in (body or {}).items():
        payload[offset] = value & 0xFF
    return bytes(payload)


def time_body(when: datetime) -> dict[int, int]:
    """Decimal-digit encoding of a datetime (one digit per byte).

    Weekday matches JS ``getDay()`` (Sunday=0 .. Saturday=6).
    """
    y = when.year
    weekday = (when.weekday() + 1) % 7
    return {
        5: FIXED,
        8: y // 1000 % 10, 9: y // 100 % 10, 10: y // 10 % 10, 11: y % 10,
        12: when.month // 10 % 10, 13: when.month % 10,
        14: weekday,
        15: when.day // 10 % 10, 16: when.day % 10,
        17: when.hour // 10 % 10, 18: when.hour % 10,
        19: when.minute // 10 % 10, 20: when.minute % 10,
        21: when.second // 10 % 10, 22: when.second % 10,
    }


def parse_screen_size(resp: bytes) -> dict[str, int] | None:
    """Parse a getScreenSize response; non-zero width => screen is responding."""
    if len(resp) < 27:
        return None
    def u16(lo: int, hi: int) -> int:
        return (resp[hi] << 8) | resp[lo]
    rotated = resp[26] in (1, 3)
    return {
        "width": u16(22, 23) if rotated else u16(20, 21),
        "height": u16(20, 21) if rotated else u16(22, 23),
        "image_size": resp[24], "max_screen": resp[25], "rotate": resp[26],
    }
