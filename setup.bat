@echo off
echo === Creating virtual environment and installing packages (takes a minute) ===
py -3.12 -m venv venv || python -m venv venv || goto :error
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || goto :error
echo === Creating the database tables ===
alembic upgrade head || goto :error
echo === Creating the WM Notifier desktop shortcut ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"
echo.
echo Setup finished. Open "WM Notifier" from your Desktop.
pause
exit /b 0
:error
echo Something went wrong. Copy the message above and send it to Claude.
pause
exit /b 1
