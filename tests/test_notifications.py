from app import email_service


def notify(client, user_id, **extra):
    body = {"user_id": user_id, "type": "email", "content": "Hello!", **extra}
    return client.post("/api/v1/notify", json=body)


def test_notification_is_accepted_and_logged_as_sent(client, user):
    r = notify(client, user["id"])
    assert r.status_code == 202
    log = client.get(f"/api/v1/notifications/{r.json()['notification_id']}").json()
    assert log["status"] == "sent"  # queued -> worker ran -> sent
    assert log["error"] is None


def test_email_provider_is_called_with_right_data(client, user, monkeypatch):
    calls = []
    monkeypatch.setattr(email_service, "send_email", lambda to, subject, body: calls.append((to, subject, body)))
    notify(client, user["id"], subject="Welcome", content="Hi Ada")
    assert calls == [("ada@example.com", "Welcome", "Hi Ada")]


def test_failed_delivery_is_logged_as_failed(user):
    # In test mode the queue runs the task inside the request, so its error bubbles up.
    # (In real use the worker process absorbs it.) We only care that the database says "failed".
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app, raise_server_exceptions=False)
    notify(c, user["id"], content="please FAIL now")
    log = c.get("/api/v1/notifications").json()[0]
    assert log["status"] == "failed"
    assert "simulated a failure" in log["error"]


def test_sms_goes_through_sms_sender(client, user, monkeypatch):
    calls = []
    monkeypatch.setattr(email_service, "send_sms", lambda to, body: calls.append((to, body)))
    r = notify(client, user["id"], type="sms", content="Your code is 123")
    assert calls == [("+2348000000000", "Your code is 123")]
    assert client.get(f"/api/v1/notifications/{r.json()['notification_id']}").json()["status"] == "sent"


def test_unknown_user_returns_404(client):
    assert notify(client, 999).status_code == 404


def test_invalid_payload_is_rejected(client, user):
    r = client.post("/api/v1/notify", json={"user_id": user["id"], "type": "pigeon", "content": "x"})
    assert r.status_code == 422
    assert notify(client, user["id"], content="").status_code == 422


def test_rate_limit_blocks_after_max_requests(client, user):
    codes = [notify(client, user["id"]).status_code for _ in range(7)]
    assert codes[:5] == [202] * 5
    assert codes[5:] == [429, 429]


def test_rate_limit_is_per_user(client, user):
    other = client.post("/api/v1/users", json={"email": "bob@example.com"}).json()
    for _ in range(5):
        notify(client, user["id"])
    assert notify(client, user["id"]).status_code == 429
    assert notify(client, other["id"]).status_code == 202


def test_template_is_filled_in(client, user):
    client.post("/api/v1/templates", json={"name": "welcome", "type": "email",
                                           "subject": "Hi {name}", "body": "Welcome aboard, {name}!"})
    r = client.post("/api/v1/notify", json={"user_id": user["id"], "type": "email",
                                            "template_name": "welcome", "variables": {"name": "Ada"}})
    assert r.status_code == 202
    log = client.get(f"/api/v1/notifications/{r.json()['notification_id']}").json()
    assert log["content"] == "Welcome aboard, Ada!"


def test_live_websocket_receives_notification(client, user):
    with client.websocket_connect("/ws") as ws:
        notify(client, user["id"], content="live one")
        # The page may first see "queued" and then "sent", so read updates until "sent" arrives.
        statuses = []
        for _ in range(5):
            msg = ws.receive_json()
            assert msg["content"] == "live one"
            statuses.append(msg["status"])
            if msg["status"] == "sent":
                break
        assert statuses[-1] == "sent"
