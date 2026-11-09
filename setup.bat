@echo off
setlocal
cd /d "%~dp0"
py -3.12-64 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.12 64-bit was not found. Install it and run setup.bat again.
  pause
  exit /b 1
)
py -3.12-64 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Setup complete. Run start.bat to open CourtVision.
pause
exit /b 0
:failed
echo Setup did not complete. Check the error above and try again.
pause
exit /b 1
