#!/usr/bin/env bash
# RT98 Studio - launch the app from the project's virtual environment (macOS/Linux).
cd "$(dirname "$0")"
if [ ! -e ".venv/bin/python" ]; then
  echo "[RT98] Virtual environment not found. Run ./setup.sh first."
  exit 1
fi
echo "[RT98] Launching RT98 Studio..."
exec .venv/bin/python run.py
