# How WM Notifier works (read this so you can explain it)

## The story in one paragraph
Apps often need to send emails or texts: "welcome", "your order shipped". Sending is slow and can fail, so a good system never makes the user wait for it. This project accepts the request, saves a record, immediately says "got it", and lets a separate worker do the slow sending. The web page updates live when the worker finishes.

## Following one notification
1. You POST to `/api/v1/notify` (from the web page or `/docs`).
2. The API checks the data is valid (`schemas.py`) and that the user exists.
3. The **rate limiter** checks the user hasn't sent too many in the last minute (default 10). If so, it replies `429 Too Many Requests`.
4. The API saves a row in `notification_logs` with status **queued** and puts the row's id on the **queue**. It replies `202 Accepted` right away.
5. The **worker** (separate program) takes the id off the queue, sends the email (mock or Resend), and updates the row to **sent**, or **failed** with the error message. Failed jobs are retried twice.
6. The **WebSocket** (`/ws`) checks the database every second and pushes any new or changed row to the browser, so the page updates without refreshing.

## How the desktop app starts
The desktop icon runs `launcher.py`. It prepares the database, starts the web server and the worker in the background (no black windows), opens the app in its own Edge/Chrome window, and stops everything when you close that window. The screens are one web page (`app/static/index.html`) that talks to the API, so the "app" is a web interface inside a window. Say it that way if asked: it is how many desktop apps are built.

## Key terms in plain English
- **API**: the front door other programs use to talk to your service.
- **Queue**: a waiting line of jobs. The API adds jobs; the worker removes and does them.
- **Worker**: a second program that only processes jobs, so slow work never blocks the API.
- **Migration** (Alembic): a saved, versioned change to the database structure, like Git for your tables.
- **Rate limiting**: protecting the system from one user flooding it.
- **WebSocket**: a connection that stays open so the server can push updates to the browser.
- **Mock / Test mode**: a fake stand-in (prints instead of really emailing) so you can test without accounts or cost.
- **API key**: a secret password that lets your app use another company's service (here, Resend). Keep it private.
- **CI (GitHub Actions)**: a robot that runs your tests on every push.

## Honest design notes (good to mention)
- Locally the queue is a SQLite file so it runs on Windows with no extra installs. In production it switches to Redis by setting `REDIS_URL`. Same code.
- The rate limiter counts recent database rows rather than memory, so it still works with several servers.
- The live page polls the database each second. With more time I'd use Redis pub/sub for instant push.
- Email has two modes. Test mode only prints the email. Live mode delivers it through Resend. The mode and API key are stored in `settings.json`, read each time an email is sent, so changes apply instantly. The key is never sent back to the browser and the file is excluded from Git.
- Resend's free test address can only email the account owner, so emailing other people needs a verified domain.
- SMS is mocked only. Real SMS needs a paid provider.
- There is no login system. A real product would authenticate callers (e.g. API keys) before allowing `/notify`.

## Questions you may be asked, with short answers
1. **Why a queue instead of sending directly?** Sending is slow and can fail. A queue lets the API respond instantly, survive provider outages, and retry.
2. **What happens if the email fails?** The row becomes `failed` with the error stored, and the worker retries twice before giving up.
3. **Why return 202 and not 200?** 202 means "accepted for processing, not finished yet", which is exactly what happens.
4. **How does rate limiting work?** It counts a user's notifications in the last 60 seconds in the database and returns 429 past the limit.
5. **Why migrations?** They track every change to the database so it can be rebuilt identically anywhere, including production.
6. **How does the page update live?** The browser keeps a WebSocket open; the server pushes each changed notification.
7. **How do you test it?** Tests call the API, run the task, and check the database says `sent` or `failed`. They run automatically on GitHub for every push.
8. **How would you scale it?** Run more workers (more consumers on the same queue), use Redis, and add an index on the logs table (already done).
9. **What would you improve next?** Authentication, Redis pub/sub for live updates, a dashboard, and real SMS.

10. **How do you keep the API key safe?** It's stored in a local file excluded from Git, it is never returned by the API (only the last 4 characters are shown), and it is read at send time so it can be changed without restarting.

## Describing it honestly
Something like: "I built WM Notifier, a notification app, during my internship, with AI assistance while learning Python. It uses FastAPI, a background queue, database migrations, WebSockets and automated tests, deployed with CI." Be ready to open the code and walk through one request end to end.
