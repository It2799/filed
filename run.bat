@echo off
REM Double-click this to get today's important announcements.
cd /d "%~dp0"
python run.py %*
echo.
pause
