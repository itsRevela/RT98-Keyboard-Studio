# PyInstaller spec for RT98 Studio - a single self-contained Windows exe.
#
# Build:  pyinstaller --noconfirm rt98studio.spec
#
# Bundles the app, its Python deps, the qgif WASM runner, the icon, the IANA
# tz database, and the hidapi DLL. If packaging/bin/{node.exe,ffmpeg.exe} exist
# (the release workflow downloads them), they are bundled too so GIF encoding
# and video import work with no external installs; otherwise the exe falls back
# to a system Node/ffmpeg on PATH.
import os

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

datas = [
    ("rt98/qgif/qgif.js", "rt98/qgif"),
    ("rt98/qgif/qgif.wasm", "rt98/qgif"),
    ("rt98/qgif/qgif_compress.js", "rt98/qgif"),
    ("app/assets/icon.png", "app/assets"),
    ("app/assets/icon.ico", "app/assets"),
]
binaries = []
hiddenimports = []

# IANA tz database (zoneinfo has no system source on Windows).
tz_datas, tz_bins, tz_hidden = collect_all("tzdata")
datas += tz_datas
binaries += tz_bins
hiddenimports += tz_hidden

# hidapi native library.
binaries += collect_dynamic_libs("hid")

# Bundled CLI runtimes (placed into packaging/bin by the release workflow).
for _tool in ("node.exe", "ffmpeg.exe"):
    _p = os.path.join("packaging", "bin", _tool)
    if os.path.isfile(_p):
        datas.append((_p, "bin"))

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="RT98Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,           # windowed GUI app, no console
    disable_windowed_traceback=False,
    icon="app/assets/icon.ico",
)
