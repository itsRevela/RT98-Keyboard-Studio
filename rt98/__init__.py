"""RT98 keyboard backend: device transport, qgif encoding, and the edit pipeline.

GUI-agnostic - the PySide6 app in ``app/`` builds on this.
"""
from .device import RT98Device, DeviceError, keyboard_present, screen_present
from .encoder import WasmQgifEncoder, EncoderError, default_encoder
from .imaging import Clip, EditState, load_clip, bake_frames, render_frame, effective_fps

__all__ = [
    "RT98Device", "DeviceError", "keyboard_present", "screen_present",
    "WasmQgifEncoder", "EncoderError", "default_encoder",
    "Clip", "EditState", "load_clip", "bake_frames", "render_frame", "effective_fps",
]

__version__ = "0.1.0"
