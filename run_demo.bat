@echo off
rem DX Command - DEMO mode: simulated rig, simulated cluster + WSJT-X, offline.
rem Nothing to hook up - just open http://localhost:8073
cd /d "%~dp0"
set DXDASH_DEMO=1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8073
pause
