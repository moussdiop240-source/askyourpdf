@echo off
title AskYourPDF Launcher
color 0A
cd /d "C:\Users\User\Desktop\askyourpdf"
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo Starting Ollama...
    start "" /B ollama serve >NUL 2>&1
    timeout /t 5 /nobreak >NUL
)
echo Starting AskYourPDF...
call venv\Scripts\activate.bat
python app.py
pause