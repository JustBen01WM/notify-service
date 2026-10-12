"""WM Notifier launcher.

Double-clicking the desktop icon runs this file. It:
  1. prepares the database,
  2. starts the web server and the background worker (no black windows),
  3. opens the app in its own window,
  4. shuts everything down when you close that window.
"""
import ctypes
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
PORT = int(os.getenv("WM_PORT", "8000"))
URL = f"http://127.0.0.1:{PORT}"
LOGS = BASE / "logs"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows only; 0 elsewhere


def message(text: str) -> None:
    """Show a pop-up on Windows (there is no console to print to)."""
    try:
        ctypes.windll.user32.MessageBoxW(0, text, "WM Notifier", 0x10)
    except Exception:
        print(text)


def python_exe() -> str:
    """Use python.exe (not pythonw.exe) for the background programs."""
    exe = Path(sys.executable)
    candidate = exe.with_name("python.exe")
    return str(candidate) if candidate.exists() else str(exe)


def is_up() -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/health", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def find_browser() -> str | None:
    override = os.getenv("WM_BROWSER")  # used for testing
    if override:
        return override
    roots = [os.environ.get(k) for k in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA")]
    for root in filter(None, roots):
        for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
            path = Path(root) / rel
            if path.exists():
                return str(path)
    return shutil.which("msedge") or shutil.which("chrome") or shutil.which("google-chrome")


def start(args: list[str], logfile: str) -> subprocess.Popen:
    log = open(LOGS / logfile, "ab")
    return subprocess.Popen(args, cwd=BASE, stdout=log, stderr=log, creationflags=NO_WINDOW)


def main() -> int:
    os.chdir(BASE)
    LOGS.mkdir(exist_ok=True)
    py = python_exe()
    children: list[subprocess.Popen] = []

    if not is_up():
        with open(LOGS / "migrate.log", "ab") as log:
            result = subprocess.run([py, "-m", "alembic", "upgrade", "head"], cwd=BASE,
                                    stdout=log, stderr=log, creationflags=NO_WINDOW)
        if result.returncode != 0:
            message("WM Notifier could not prepare its database.\n\nSee logs\\migrate.log in the project folder.")
            return 1
        children.append(start([py, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)], "api.log"))
        children.append(start([py, "-m", "huey.bin.huey_consumer", "app.tasks.huey", "-w", "2"], "worker.log"))
        for _ in range(60):  # wait up to ~30 seconds for the server
            if is_up():
                break
            time.sleep(0.5)
        else:
            for c in children:
                c.terminate()
            message("WM Notifier did not start.\n\nSee logs\\api.log in the project folder.")
            return 1

    browser = find_browser()
    try:
        if browser:
            profile = BASE / ".app_profile"
            window = subprocess.Popen([browser, f"--app={URL}", f"--user-data-dir={profile}",
                                       "--window-size=1280,820", "--no-first-run", "--no-default-browser-check"])
            window.wait()  # returns when you close the app window
        else:
            import webbrowser
            webbrowser.open(URL)
            message("WM Notifier is running in your browser.\n\nClick OK to stop it.")
    finally:
        for c in children:
            c.terminate()
        for c in children:
            try:
                c.wait(timeout=10)
            except subprocess.TimeoutExpired:
                c.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
