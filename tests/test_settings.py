import httpx
import pytest

from app import email_service


def test_default_mode_is_test(client):
    s = client.get("/api/v1/settings").json()
    assert s["mode"] == "test" and s["api_key_set"] is False


def test_cannot_go_live_without_a_key(client):
    r = client.put("/api/v1/settings", json={"use_real": True})
    assert r.status_code == 422


def test_saving_key_switches_to_live_and_hides_the_key(client):
    r = client.put("/api/v1/settings", json={"api_key": "re_secretvalue1234", "from_email": "hi@mydomain.com", "use_real": True})
    body = r.json()
    assert body["mode"] == "live" and body["from_email"] == "hi@mydomain.com"
    assert body["api_key_hint"] == "re_…1234"
    assert "secretvalue" not in r.text
    assert "secretvalue" not in client.get("/api/v1/settings").text


def test_live_mode_calls_resend_with_the_right_data(client, user, monkeypatch):
    client.put("/api/v1/settings", json={"api_key": "re_abc", "from_email": "onboarding@resend.dev", "use_real": True})
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json)
        return httpx.Response(200, json={"id": "x"})

    monkeypatch.setattr(email_service.httpx, "post", fake_post)
    r = client.post("/api/v1/notify", json={"user_id": user["id"], "type": "email", "subject": "Hi", "content": "Real one"})
    assert client.get(f"/api/v1/notifications/{r.json()['notification_id']}").json()["status"] == "sent"
    assert seen["headers"]["Authorization"] == "Bearer re_abc"
    assert seen["json"]["to"] == ["ada@example.com"]
    assert seen["json"]["from"] == "WM Notifier <onboarding@resend.dev>"
    assert seen["json"]["subject"] == "Hi" and seen["json"]["text"] == "Real one"


def test_resend_rejection_is_explained_in_plain_english(client, monkeypatch):
    client.put("/api/v1/settings", json={"api_key": "re_abc", "use_real": True})
    msg = "You can only send testing emails to your own email address (me@x.com)."
    monkeypatch.setattr(email_service.httpx, "post", lambda *a, **k: httpx.Response(403, text=msg))
    r = client.post("/api/v1/settings/test", json={"to": "someone@else.com"})
    assert r.status_code == 502
    assert "verify a domain" in r.json()["detail"]


def test_test_email_in_test_mode_succeeds_without_sending(client):
    r = client.post("/api/v1/settings/test", json={"to": "me@example.com"})
    assert r.status_code == 200 and r.json()["mode"] == "test"
