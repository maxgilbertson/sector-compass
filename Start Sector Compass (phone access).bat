@echo off
rem Starts Sector Compass so phones and tablets on the same Wi-Fi can open it.
rem The window prints the address to type into your phone's browser.
rem If Windows asks whether to allow Python on networks, allow Private networks only.
cd /d "%~dp0"
start "" /b cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8765"
py server.py 8765 --lan
pause
