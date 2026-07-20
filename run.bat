@echo off
rem DX Command - live mode (OmniRig + real DX cluster + WSJT-X UDP)
cd /d "%~dp0"
set DXDASH_DEMO=
python -m uvicorn app.main:app --host 127.0.0.1 --port 8073
pause
