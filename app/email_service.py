"""Sends emails.

Test mode: the email is only printed in the worker log (nothing is delivered).
Live mode: the email is delivered for real through Resend (resend.com).

The mode and the API key live in `settings.json` (edited from the Settings screen).
They are read every time an email is sent, so changes apply immediately."""
import json
import os
from pathlib import Path

import httpx

from app import config

RESEND_URL = os.getenv("RESEND_API_URL", "https://api.resend.com/emails")


class DeliveryError(Exception):
    pass


def _settings_path() -> Path:
    return Path(os.getenv("SETTINGS_FILE", Path(__file__).resolve().parent.parent / "settings.json"))


def load_settings() -> dict:
    try:
        data = json.loads(_settings_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        data = {}
    return {
        "use_real": bool(data.get("use_real", False)) or config.EMAIL_PROVIDER == "resend",
        "api_key": data.get("api_key") or config.RESEND_API_KEY,
        "from_email": data.get("from_email") or config.EMAIL_FROM,
    }


def save_settings(**updates) -> dict:
    path = _settings_path()
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        current = {}
    current.update({k: v for k, v in updates.items() if v is not None})
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(current, indent=2), encoding="utf-8")
    try:
        tmp.chmod(0o600)  # keep the key private where the system supports it
    except OSError:
        pass
    tmp.replace(path)
    return load_settings()


def is_live(settings: dict | None = None) -> bool:
    s = settings or load_settings()
    return bool(s["use_real"] and s["api_key"])


def _explain(status: int, text: str) -> str:
    low = text.lower()
    if status in (401, 403) and "own email" in low:
        return ("Resend's free test address can only email the address you signed up with. "
                "To email anyone else, verify a domain in Resend and use an address on it as the From address.")
    if status in (401, 403) and ("api key" in low or status == 401):
        return "Resend rejected the API key. Check that you pasted the whole key."
    if status == 403 and "domain" in low:
        return "Resend says the From address is not allowed. Use onboarding@resend.dev or an address on your verified domain."
    if status == 422:
        return f"Resend rejected the email details: {text[:160]}"
    if status == 429:
        return "Resend's sending limit was reached. Try again later."
    return f"Resend error {status}: {text[:160]}"


def send_email(to: str, subject: str, body: str) -> None:
    settings = load_settings()

    if not is_live(settings):
        print(f"[MOCK EMAIL] to={to} subject={subject!r} body={body!r}", flush=True)
        if "FAIL" in body:  # lets you demo a failure on purpose
            raise DeliveryError("Mock provider simulated a failure")
        return

    sender = settings["from_email"]
    if "<" not in sender:
        sender = f"WM Notifier <{sender}>"
    try:
        resp = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings['api_key']}"},
            json={"from": sender, "to": [to], "subject": subject, "text": body},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise DeliveryError(f"Could not reach Resend. Check your internet connection. ({exc.__class__.__name__})")
    if resp.status_code >= 300:
        raise DeliveryError(_explain(resp.status_code, resp.text))


def send_sms(to: str, body: str) -> None:
    # SMS is always simulated in this project (real SMS providers need paid accounts).
    print(f"[MOCK SMS] to={to} body={body!r}", flush=True)
