"""Video -> GIF conversion via ffmpeg (must be on PATH).

Uses ffmpeg's palettegen/paletteuse for good-quality GIFs. The result is a
normal .gif that the rest of the app loads through :func:`rt98.imaging.load_clip`.
"""
from __future__ import annotations

import dataclasses
import os
import subprocess
from typing import Optional

from .runtime import CREATE_NO_WINDOW, tool_available, tool_command


class VideoError(RuntimeError):
    pass


def ffmpeg_available() -> bool:
    return tool_available("ffmpeg")


@dataclasses.dataclass
class VideoOptions:
    fps: int = 15
    start: float = 0.0                 # seconds into the source
    duration: Optional[float] = None   # seconds to take (None = to end)
    width: Optional[int] = None        # scale to this width (keep aspect); None = source
    loop: bool = True


def video_to_gif(src: str, out_gif: str, opts: Optional[VideoOptions] = None) -> str:
    """Convert ``src`` video to ``out_gif``. Returns the output path."""
    if not ffmpeg_available():
        raise VideoError("ffmpeg not found")
    if not os.path.isfile(src):
        raise VideoError("video not found: %s" % src)
    opts = opts or VideoOptions()

    scale = ("scale=%d:-1:flags=lanczos," % opts.width) if opts.width else ""
    vf = (
        "fps=%d,%ssplit[s0][s1];[s0]palettegen=stats_mode=diff[p];"
        "[s1][p]paletteuse=dither=bayer:bayer_scale=3" % (max(1, opts.fps), scale)
    )
    cmd = [tool_command("ffmpeg"), "-y"]
    if opts.start > 0:
        cmd += ["-ss", str(opts.start)]
    if opts.duration:
        cmd += ["-t", str(opts.duration)]
    cmd += ["-i", src, "-vf", vf, "-loop", "0" if opts.loop else "-1", out_gif]

    res = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    if res.returncode != 0 or not os.path.isfile(out_gif):
        tail = "\n".join((res.stderr or "").strip().splitlines()[-4:])
        raise VideoError("ffmpeg failed:\n%s" % tail)
    return out_gif
