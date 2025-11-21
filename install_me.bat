@echo off
REM Installer script for Windows — installs Python deps from requirements.txt
python -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
  echo.
  echo Installation failed. Re-run with an admin prompt if needed.
  pause
  exit /b %errorlevel%
)
echo.
echo Installation completed successfully.
pause
