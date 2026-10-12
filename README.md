# WM Notifier (Wingman)

A backend service that accepts notification requests (email or SMS), puts them in a background queue, delivers them with a worker, logs the result, and shows everything live in the browser.

**Stack:** Python, FastAPI, SQLAlchemy + Alembic, Huey (queue; Redis in production), WebSockets, pytest, GitHub Actions.

```
Browser / API client --> FastAPI --> database (status: queued)
                            |                    ^
                            +--> queue --> Worker (sends, then status: sent/failed)
                                                 |
Live page <-- WebSocket <-- watches the database +
```

## Run it on Windows (about 15 minutes, one time)

1. **Install Python 3.12** from https://www.python.org/downloads/windows/ (pick the newest 3.12 that has a Windows installer, e.g. 3.12.10). Tick **"Add python.exe to PATH"** on the first screen. Newer versions such as 3.14 will not work with the packages used here.
2. Unzip this folder somewhere simple, e.g. `C:\WM-Notifier`.
3. Double-click **`setup.bat`**. It installs everything, creates the database and puts a **WM Notifier** icon on your Desktop. Wait for "Setup finished".
4. From now on, **double-click the WM Notifier icon**. The app opens in its own window. Closing the window stops everything.

First time only: if Windows shows a firewall prompt, click **Allow**. If the icon does nothing, look in the `logs` folder inside the project for `api.log`.

### Using the app
- **Overview**: live totals and the latest activity.
- **Send**: pick a person, channel and message (or a template). A preview shows how it will look.
- **History**: search and filter everything; retry failed notifications.
- **People**: add the people you can notify (a phone number is needed for SMS).
- **Templates**: save messages with blanks like `Hello {name}`.

Developer tools (optional): `start_api.bat` and `start_worker.bat` run the two parts in visible windows, `run_tests.bat` runs the 21 tests, and http://127.0.0.1:8000/docs shows the API.

## Real emails

By default the app is in **Test mode**: emails are simulated (a line is written to the worker log, nothing is delivered). To send real ones, open **Settings** in the app and follow the steps there:

1. Create a free account at https://resend.com, using the email address you want to receive test emails at.
2. In Resend, create an **API key** (it starts with `re_` and is shown once).
3. In WM Notifier: **Settings**, paste the key, choose **Live**, click **Save settings**.
4. Under **Send a test email**, type your Resend account email and click the button.

**Limits to know about**
- Until you verify a domain in Resend, you can only send from `onboarding@resend.dev` and only to the email you signed up with. Anything else is refused.
- To email other people you need a domain you own, verified in Resend (add the DNS records Resend gives you), and a From address on it, e.g. `hello@yourdomain.com`.
- Free plans have daily and monthly sending limits. Check Resend's current pricing page.
- SMS is always simulated; real SMS needs a paid provider.
- A notification marked **Sent** in Live mode means Resend accepted it. Delivery to the inbox is Resend's job after that.

Your key is saved in `settings.json` in the project folder. It is excluded from GitHub uploads. Never share or upload it.

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
| `app/static/index.html` | The app screens (Overview, Send, History, People, Templates) |
| `launcher.py` | Starts everything and opens the app window |
| `assets/` | Logo and icon |
| `alembic/` | Database migrations (change history) |
| `tests/` | Automated tests |
| `.github/workflows/tests.yml` | Runs tests on every push |

Rename note: the project was first called Notification Service; WM Notifier is the same project.

Read **HOW_IT_WORKS.md** before you present this to anyone.
