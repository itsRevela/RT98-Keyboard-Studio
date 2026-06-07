"""Pluggable qgif encoder.

The RT98 screen's animated format ("qgif") is a proprietary tile/delta codec.
We don't reimplement it; we run the vendor's WebAssembly compressor (bundled in
``rt98/qgif/``) under Node. The :class:`QgifEncoder` interface lets a future
clean-room pure-Python encoder be dropped in without touching the rest of the app.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Protocol, Sequence

from PIL import Image

from .runtime import CREATE_NO_WINDOW, meipass, tool_available, tool_command

# Bundled (PyInstaller) puts the qgif data under <bundle>/rt98/qgif; from source
# it sits next to this module.
_MEI = meipass()
QGIF_DIR = (os.path.join(_MEI, "rt98", "qgif") if _MEI
            else os.path.join(os.path.dirname(os.path.abspath(__file__)), "qgif"))
QGIF_RUNNER = os.path.join(QGIF_DIR, "qgif_compress.js")
QGIF_MAGIC = b"QGIF"


class EncoderError(RuntimeError):
    pass


class QgifEncoder(Protocol):
    """Encodes a sequence of target-sized RGB frames + fps into qgif bytes."""

    def encode(self, frames: Sequence[Image.Image], fps: int) -> bytes: ...


class WasmQgifEncoder:
    """Runs the bundled vendor qgif WASM compressor via Node."""

    def __init__(self, node: str | None = None):
        self.node = node or tool_command("node")

    @staticmethod
    def available() -> tuple[bool, str]:
        if not os.path.isfile(QGIF_RUNNER):
            return False, "qgif runner missing: %s" % QGIF_RUNNER
        if not tool_available("node"):
            return False, "Node.js not found (required to run the qgif compressor)"
        return True, "ok"

    def encode(self, frames: Sequence[Image.Image], fps: int) -> bytes:
        if not frames:
            raise EncoderError("no frames to encode")
        ok, why = self.available()
        if not ok:
            raise EncoderError(why)

        work = tempfile.mkdtemp(prefix="rt98qgif_")
        out_path = os.path.join(work, "out.qgif")
        try:
            for i, frame in enumerate(frames):
                frame.convert("RGB").save(os.path.join(work, "input_%d.png" % i))
            res = subprocess.run(
                [self.node, QGIF_RUNNER, work, str(max(1, int(fps))), out_path],
                capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
            )
            if res.returncode != 0 or not os.path.isfile(out_path):
                raise EncoderError("qgif compression failed: %s" % (res.stderr.strip() or "unknown"))
            with open(out_path, "rb") as fh:
                data = fh.read()
            if data[:4] != QGIF_MAGIC:
                raise EncoderError("encoder output is not a valid qgif (bad magic)")
            return data
        finally:
            shutil.rmtree(work, ignore_errors=True)


def default_encoder() -> QgifEncoder:
    return WasmQgifEncoder()
