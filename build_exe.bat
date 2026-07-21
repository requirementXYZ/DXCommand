@echo off
rem Build a one-file Windows executable (no Python needed on the target PC).
rem Requires: pip install pyinstaller
cd /d "%~dp0"
pyinstaller --noconfirm --onefile --name DXCommand ^
  --add-data "static;static" ^
  --add-data "app/bundled;app/bundled" ^
  run_app.py
echo.
echo Done. The executable is dist\DXCommand.exe
echo Ship it together with nothing else - config.json and data\ are created
echo next to the exe on first run.
pause
