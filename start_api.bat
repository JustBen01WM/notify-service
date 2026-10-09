@echo off
call venv\Scripts\activate.bat
echo Open http://127.0.0.1:8000 in your browser. Press Ctrl+C to stop.
uvicorn app.main:app --reload
pause
