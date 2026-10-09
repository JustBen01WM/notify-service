"""Sends emails. "mock" mode just prints the email (no account needed).
"resend" mode really delivers it through resend.com's free tier."""
import httpx
from app import config


class DeliveryError(Exception):
    pass


def send_email(to: str, subject: str, body: str) -> None:
    if config.EMAIL_PROVIDER == "mock":
        print(f"[MOCK EMAIL] to={to} subject={subject!r} body={body!r}", flush=True)
        if "FAIL" in body:  # lets you demo a failure on purpose
            raise DeliveryError("Mock provider simulated a failure")
        return

    if config.EMAIL_PROVIDER == "resend":
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
            json={"from": config.EMAIL_FROM, "to": [to], "subject": subject, "text": body},
            timeout=15,
        )
        if resp.status_code >= 300:
            raise DeliveryError(f"Resend error {resp.status_code}: {resp.text[:200]}")
        return

    raise DeliveryError(f"Unknown EMAIL_PROVIDER: {config.EMAIL_PROVIDER}")


def send_sms(to: str, body: str) -> None:
    # SMS is always mocked in this project (real SMS providers need paid accounts).
    print(f"[MOCK SMS] to={to} body={body!r}", flush=True)
