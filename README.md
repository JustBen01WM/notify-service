# Notification Service

A backend service that accepts notification requests (email or SMS), puts them in a background queue, delivers them with a worker, logs the result, and shows everything live in the browser.

**Stack:** Python, FastAPI, SQLAlchemy + Alembic, Huey (queue; Redis in production), WebSockets, pytest, GitHub Actions.

```
Browser / API client --> FastAPI --> database (status: queued)
                            |                    ^
                            +--> queue --> Worker (sends, then status: sent/failed)
                                                 |
Live page <-- WebSocket <-- watches the database +
```

## Run it on Windows (about 15 minutes)

1. **Install Python 3.12** from https://www.python.org/downloads/ . On the first installer screen, tick **"Add python.exe to PATH"**, then click Install.
2. **Install VS Code** (optional, for viewing the code) from https://code.visualstudio.com/
3. Unzip this folder somewhere simple, e.g. `C:\notify-service`.
4. Double-click **`setup.bat`**. It installs everything and creates the database. Wait for "Setup finished".
5. Double-click **`start_api.bat`** and leave the window open.
6. Double-click **`start_worker.bat`** and leave that window open too.
7. Open **http://127.0.0.1:8000** in your browser. Add a user, send a notification, and watch it appear live and turn from `queued` to `sent`.
8. Type the word **FAIL** in a message to see a failed delivery being logged.

API docs (auto-generated): http://127.0.0.1:8000/docs

Run the automated tests by double-clicking **`run_tests.bat`** (10 tests).

## Real emails (optional)

By default emails are "mocked": printed in the worker window instead of sent. To send real ones, make a free account at https://resend.com, create an API key, then set these before starting the worker: `EMAIL_PROVIDER=resend` and `RESEND_API_KEY=your_key`. (On the free tier you can only send to your own email address until you verify a domain.)

## Put it on GitHub (this is your proof of work)

1. Create a free account at https://github.com and a new empty repository named `notify-service`.
2. Install Git from https://git-scm.com/download/win
3. In the project folder, open PowerShell and run:
   ```
   git init
   git add .
   git commit -m "Initial notification service"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/notify-service.git
   git push -u origin main
   ```
4. Open the **Actions** tab on GitHub. Your tests run automatically on every push, and you get a green tick. Make small commits as you learn and change things; the history shows your work over time.

## Deploy online (Render)

The included `render.yaml` describes the website, the worker, a Postgres database and Redis.

1. Sign up at https://render.com and connect your GitHub.
2. **New > Blueprint**, choose your repository, and apply.
3. After it builds, your live link looks like `https://notify-api-xxxx.onrender.com`.

Cost notes (check Render's current pricing page, since it changes): the website, Postgres and Redis can use free plans, but background workers generally need a paid plan, and free databases expire after a while. If you don't want to pay, a common workaround is to deploy only the website and show the worker running locally, or use a platform with trial credit such as Railway. Both are fine for a portfolio as long as the GitHub repo and tests are visible.

## Project layout

| Path | What it does |
|---|---|
| `app/main.py` | API endpoints and the WebSocket |
| `app/models.py` | The 3 database tables |
| `app/rate_limit.py` | Limits notifications per user |
| `app/queue.py`, `app/tasks.py` | The queue and the worker's job |
| `app/email_service.py` | Mock and Resend email sending |
| `app/static/index.html` | The live web page |
| `alembic/` | Database migrations (change history) |
| `tests/` | Automated tests |
| `.github/workflows/tests.yml` | Runs tests on every push |

Read **HOW_IT_WORKS.md** before you present this to anyone.
