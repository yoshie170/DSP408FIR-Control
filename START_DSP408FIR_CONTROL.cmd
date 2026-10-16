@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Python environment missing. Create .venv and install requirements first.
    pause
    exit /b 1
)
start "DSP408FIR Control" ".venv\Scripts\pythonw.exe" "%~dp0main.py" --connection-dialog
