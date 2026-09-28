@echo off
rem Double-click to start Sector Compass and open it in your browser.
cd /d "%~dp0"
start "" /b cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8765"
py server.py 8765
