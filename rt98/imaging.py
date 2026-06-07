"""Frame decoding and the non-destructive edit pipeline.

Edits are described by an :class:`EditState` and applied on the fly so the UI can
preview them live; frames are only baked to the screen's 240x136 target at
upload time.
"""
from __future__ import annotations

import dataclasses
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageEnhance, ImageSequence

from . import protocol as P

Rect = Tuple[int, int, int, int]  # (left, top, right, bottom) in source pixels


@dataclasses.dataclass
class EditState:
    """Non-destructive edit parameters for a clip."""
    crop: Optional[Rect] = None          # source-pixel crop box, None = whole frame
    brightness: float = 1.0              # 1.0 = unchanged
    contrast: float = 1.0
    saturation: float = 1.0
    hue: int = 0                         # degrees, -180..180
    rotate: int = 0                      # 0 / 90 / 180 / 270
    flip_h: bool = False
    flip_v: bool = False
    speed: float = 1.0                   # playback speed multiplier (>1 = faster)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EditState":
        f = {k: d[k] for k in (fld.name for fld in dataclasses.fields(cls)) if k in d}
        if f.get("crop") is not None:
            f["crop"] = tuple(f["crop"])
        return cls(**f)


@dataclasses.dataclass
class Clip:
    """A decoded source: frames (RGBA, source size) + per-frame durations (ms)."""
    frames: List[Image.Image]
    durations: List[int]
    source_size: Tuple[int, int]

    @property
    def is_animated(self) -> bool:
        return len(self.frames) > 1

    @property
    def avg_duration_ms(self) -> float:
        return (sum(self.durations) / len(self.durations)) if self.durations else 100.0


def load_clip(path: str) -> Clip:
    """Decode a GIF/image (or any Pillow-readable animation) into a Clip."""
    im = Image.open(path)
    frames: List[Image.Image] = []
    durations: List[int] = []
    for frame in ImageSequence.Iterator(im):
        durations.append(int(frame.info.get("duration", 100) or 100))
        frames.append(frame.convert("RGBA"))
    if not frames:
        raise ValueError("no frames decoded from %s" % path)
    return Clip(frames=frames, durations=durations, source_size=frames[0].size)


def _apply_adjustments(img: Image.Image, edit: EditState) -> Image.Image:
    out = img
    if edit.brightness != 1.0:
        out = ImageEnhance.Brightness(out).enhance(edit.brightness)
    if edit.contrast != 1.0:
        out = ImageEnhance.Contrast(out).enhance(edit.contrast)
    if edit.saturation != 1.0:
        out = ImageEnhance.Color(out).enhance(edit.saturation)
    if edit.hue % 360 != 0:
        out = _shift_hue(out, edit.hue)
    return out


def _shift_hue(img: Image.Image, degrees: int) -> Image.Image:
    """Rotate hue by ``degrees`` (preserves alpha)."""
    rgba = img.convert("RGBA")
    arr = np.asarray(rgba)
    rgb = arr[..., :3].astype("uint8")
    hsv = np.asarray(Image.fromarray(rgb, "RGB").convert("HSV")).astype("int16")
    hsv[..., 0] = (hsv[..., 0] + int(degrees * 255 / 360)) % 256
    shifted = np.asarray(Image.fromarray(hsv.astype("uint8"), "HSV").convert("RGB"))
    out = np.dstack([shifted, arr[..., 3:4]])
    return Image.fromarray(out, "RGBA")


def _orient(img: Image.Image, edit: EditState) -> Image.Image:
    out = img
    if edit.flip_h:
        out = out.transpose(Image.FLIP_LEFT_RIGHT)
    if edit.flip_v:
        out = out.transpose(Image.FLIP_TOP_BOTTOM)
    if edit.rotate % 360:
        out = out.rotate(-(edit.rotate % 360), expand=True)
    return out


def fit_contain(img: Image.Image, w: int, h: int, bg=(0, 0, 0)) -> Image.Image:
    """Scale to fit within w x h (preserving aspect), centered on a bg canvas."""
    src = img.convert("RGBA")
    sw, sh = src.size
    scale = min(w / sw, h / sh) if sw and sh else 1.0
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    resized = src.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (w, h), bg)
    canvas.paste(resized, ((w - nw) // 2, (h - nh) // 2), resized)
    return canvas


def render_frame(src: Image.Image, edit: EditState, size: Tuple[int, int]) -> Image.Image:
    """Apply crop -> orient -> adjustments -> contain-fit to ``size`` (RGB)."""
    img = src
    if edit.crop:
        img = img.crop(edit.crop)
    img = _orient(img, edit)
    img = _apply_adjustments(img, edit)
    return fit_contain(img, size[0], size[1])


def bake_frames(clip: Clip, edit: EditState) -> List[Image.Image]:
    """Render every frame to the screen's 240x136 RGB target."""
    size = (P.SCREEN_W, P.SCREEN_H)
    return [render_frame(f, edit, size) for f in clip.frames]


def effective_fps(clip: Clip, edit: EditState) -> int:
    """Playback fps after applying the speed multiplier (clamped 2..120)."""
    avg = clip.avg_duration_ms
    base = (1000.0 / avg) if avg > 0 else 10.0
    return max(2, min(120, round(base * max(0.05, edit.speed))))
