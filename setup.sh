#!/usr/bin/env bash
# RT98 Studio - create a virtual environment and install dependencies (macOS/Linux).
set -e
cd "$(dirname "$0")"

PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
command -v "$PY" >/dev/null 2>&1 || { echo "[RT98] Python 3.9+ not found (tried python3, python)."; exit 1; }

echo "[RT98] Creating virtual environment (.venv)..."
"$PY" -m venv .venv

echo "[RT98] Upgrading pip..."
.venv/bin/python -m pip install --upgrade pip

echo "[RT98] Installing dependencies..."
.venv/bin/python -m pip install -r requirements.txt

echo
echo "[RT98] Setup complete. Launch the app with ./run.sh"
echo "[RT98] Note: Node.js is also required for GIF upload; ffmpeg for video import."
