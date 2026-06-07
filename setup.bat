@echo off
setlocal
cd /d "%~dp0"
echo [RT98] Creating virtual environment (.venv)...
python -m venv .venv
if errorlevel 1 (
  echo [RT98] Failed to create venv. Is Python 3.9+ on PATH?
  pause
  exit /b 1
)
echo [RT98] Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
echo [RT98] Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [RT98] Dependency install failed.
  pause
  exit /b 1
)
echo.
echo [RT98] Setup complete. Launch the app with run.bat
echo [RT98] (Node.js is also required for GIF upload; ffmpeg for video import.)
pause
endlocal
