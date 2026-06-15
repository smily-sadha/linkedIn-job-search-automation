@echo off
REM Launcher for Windows Task Scheduler. Starts the web dashboard (FastAPI/uvicorn)
REM on http://127.0.0.1:8000 with no console window. Its built-in scheduler also
REM auto-fetches jobs every 3 hours while this server is running.
cd /d "d:\D\main copy\job search autiomation"
"d:\D\main copy\job search autiomation\venv\Scripts\python.exe" -m webapp >> "d:\D\main copy\job search autiomation\logs\dashboard_win.log" 2>&1
