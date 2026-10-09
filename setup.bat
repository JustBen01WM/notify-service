@echo off
echo === Creating virtual environment and installing packages (takes a minute) ===
py -3.12 -m venv venv || goto :error
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || goto :error
echo === Creating the database tables ===
alembic upgrade head || goto :error
echo.
echo Setup finished. Next: double-click start_api.bat, then start_worker.bat
pause
exit /b 0
:error
echo Something went wrong. Copy the message above and send it to Claude.
pause
exit /b 1
