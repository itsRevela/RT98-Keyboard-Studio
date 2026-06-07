# Changelog

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Manual **Windows release workflow** (`.github/workflows/release.yml`,
  `workflow_dispatch`): builds a single self-contained `RT98Studio.exe` via
  PyInstaller (`rt98studio.spec`) bundling the app, Python deps, qgif WASM, icon,
  tz database, the hidapi DLL, and Node + ffmpeg; GPG-signs the exe (detached
  `.asc` + SHA-256) and the release tag, then publishes a GitHub Release with a
  given title/notes. `rt98/runtime.py` resolves the bundled Node/ffmpeg when
  frozen (falls back to PATH from source). Commits and tags are GPG-signed for
  the "Verified" badge. See `packaging/RELEASING.md`.
- App/window icon (`app/assets/icon.png` + multi-size `icon.ico`), set on the
  window and taskbar; on Windows an explicit AppUserModelID is set so the
  taskbar shows the app icon rather than the generic Python icon (`app/main.py`).
- **Multi-screen support** (the keyboard's 3 FN+Shift screens):
  - `rt98/device.py` `upload_slots()` writes up to 3 qgif slots in one session
    with a multi-slot address table (each slot block-aligned), exactly like the
    official tool; `upload_qgif()` is now a single-slot wrapper over it.
  - `rt98/slots.py` `SlotStore` keeps the staged screens (cached qgif + thumbnail
    + label) under the app-data dir, since the device can't be read back.
  - GUI: a "Screens" panel right of the keyboard preview shows the 3 screens.
    "Save to Screen N" stages the current clip onto the selected screen (encode +
    thumbnail, no device write); "Clear screen" drops one; "Send to keyboard"
    pushes every staged screen at once. (`app/widgets/slotspanel.py`.)
- Backend package `rt98/`:
  - `protocol.py` — RT98 screen wire protocol (device IDs, 0xAA command builders,
    time-set digit encoding, screen-size parsing).
  - `device.py` — HID transport that wakes the screen, syncs the clock, and
    uploads a qgif via the captured flash-download session.
  - `encoder.py` — pluggable qgif encoder; default runs the bundled vendor WASM
    compressor via Node.
  - `imaging.py` — clip decoding and a non-destructive edit pipeline (crop,
    brightness/contrast/saturation/hue, rotate/flip, speed) baked to 240×136.
  - `video.py` — video → GIF via ffmpeg (palettegen/paletteuse, configurable
    fps/size/trim).
  - `library.py` — GIF library stored under the per-user app-data dir.
  - `qgif/` — bundled qgif WASM compressor + Node runner.
- PySide6 app `app/`:
  - Device bar (status, time sync, send-to-keyboard with progress).
  - Library panel (import GIF/image/video, select, remove).
  - Editor: interactive crop canvas, live animated keyboard preview, and
    adjustment/speed/orientation controls.
  - Background device worker so wake/upload don't block the UI.
- `run.py` launcher and OS launchers: `setup.bat`/`run.bat` (Windows) and
  `setup.sh`/`run.sh` (macOS/Linux), plus `.gitattributes` to keep line endings
  correct (LF for `*.sh`, CRLF for `*.bat`). README, requirements.
- `rt98/transport.py` — per-platform "patient write" HID transport selection with
  self-validation + hidapi fallback and a `RT98_HID_BACKEND` override.
- `rt98/winhid.py` — Windows overlapped-I/O HID device (patient writes).

### Added
- **Time-zone selector** for Sync time: a top-bar combo (searchable, all IANA
  zones via `tzdata`, default "Local (system)") whose choice is persisted
  (`rt98/settings.py`) and applied when syncing (`rt98/timezones.py`). Requires
  `tzdata` on Windows.

### Changed
- **UI redesign** ("RT98 Studio"): warm beige theme with soft pastel
  green/pink/blue accents (`app/theme.py`), an editor-focused layout — top status
  bar, left thumbnail rail (`app/widgets/thumbrail.py`), a large Source(crop) +
  live keyboard-preview stage, a frame scrubber, and a bottom control dock
  (sliders reflowed horizontally). Custom-painted canvases use the theme palette.

### Fixed
- GIF upload reliability:
  - Encode the qgif **before** waking the screen (the screen's USB powers off when
    idle, which was invalidating the handle during the slow encode).
  - Stop status polling during a transfer (enumerating the device on Windows
    briefly opens it and collided with the worker's writes → "overlapped I/O").
  - Replace hidapi's hard ~1 s write timeout on Windows with a patient overlapped
    writer (multi-block uploads pause to program flash > 1 s, which previously
    errored and froze the screen).
  - Send the `0xE3` prepare-flash command to the keyboard between `START_DOWNLOAD`
    and `SESSION_INIT` (`rt98/device.py` `_prep_flash`). Without it, a second
    upload while the screen was still awake stalled at `PREP2` and froze the
    screen (30 s write timeout); the official tool sends `0xE3` before every
    download session. Recovered by capturing the official web tool doing repeat
    uploads.
  - Static images now upload as a 2-frame qgif. The screen won't register a
    single-frame qgif as a cyclable screen, so a static image saved to screen 2
    or 3 stayed empty; duplicating the frame makes it animated and registers in
    every slot.
  - The transfer progress bar no longer widens the window when it appears; it
    now fills the action button's column instead of forcing a wider one.
  - "Sync time" (and other transfers) no longer load the first library clip into
    the editor. Disabling the focused button shifted focus to the library list,
    which auto-selected row 0 on focus; the list is now click-focus only.

### Notes
- Animated GIF upload uses the device's proprietary "qgif" format via the vendor
  WASM compressor; a clean-room pure-Python encoder is a planned follow-up
  (the format is a fixed-size base frame + inter-frame delta over 8×8 tiles).
- The screen firmware holds up to 3 GIF/image slots (cycled on-device with
  FN+Shift). The official tool rewrites the full multi-slot table on every
  upload; this app currently writes a single slot (slot 0), overwriting it each
  time. Multi-slot support is a possible future feature.
