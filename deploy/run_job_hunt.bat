@echo off
REM Launcher for Windows Task Scheduler. Runs one full job-hunt pass using the
REM project's venv, with no console window, and appends output to a log file.
cd /d "d:\D\main copy\job search autiomation"
"d:\D\main copy\job search autiomation\venv\Scripts\python.exe" main.py >> "d:\D\main copy\job search autiomation\logs\scheduler_win.log" 2>&1
