@echo off
call venv\Scripts\activate.bat
echo Worker running. Sent emails will be printed here. Press Ctrl+C to stop.
python -m huey.bin.huey_consumer app.tasks.huey -w 2
pause
