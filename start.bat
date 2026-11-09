@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The project environment is missing. Run setup.bat first.
  pause
  exit /b 1
)
echo Starting CourtVision at http://127.0.0.1:5050
".venv\Scripts\python.exe" app.py
pause
