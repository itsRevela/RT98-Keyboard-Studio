@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [RT98] Virtual environment not found.
  echo [RT98] Run setup.bat first ^(creates .venv and installs dependencies^).
  pause
  exit /b 1
)
echo [RT98] Launching RT98 Keyboard Software...
".venv\Scripts\python.exe" run.py
if errorlevel 1 (
  echo.
  echo [RT98] The app exited with an error ^(see messages above^).
  pause
)
endlocal
