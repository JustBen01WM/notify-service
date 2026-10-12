from datetime import datetime

from app import models
from app.database import SessionLocal


def notify(client, user_id, **extra):
    body = {"user_id": user_id, "type": "email", "content": "Hello!", **extra}
    return client.post("/api/v1/notify", json=body)


def test_templates_can_be_listed_and_deleted(client):
    created = client.post("/api/v1/templates", json={"name": "welcome", "type": "email", "body": "Hi {name}"}).json()
    assert [t["name"] for t in client.get("/api/v1/templates").json()] == ["welcome"]
    assert client.delete(f"/api/v1/templates/{created['id']}").status_code == 204
    assert client.get("/api/v1/templates").json() == []
    assert client.delete("/api/v1/templates/999").status_code == 404


def test_history_can_be_filtered_and_searched(client, user):
    notify(client, user["id"], content="your parcel has shipped")
    notify(client, user["id"], type="sms", content="code 1234")
    assert len(client.get("/api/v1/notifications").json()) == 2
    assert len(client.get("/api/v1/notifications?type=sms").json()) == 1
    assert len(client.get("/api/v1/notifications?status=sent").json()) == 2
    assert len(client.get("/api/v1/notifications?status=failed").json()) == 0
    hits = client.get("/api/v1/notifications?q=parcel").json()
    assert len(hits) == 1 and hits[0]["email"] == "ada@example.com"
    assert len(client.get("/api/v1/notifications?q=ada@example").json()) == 2


def test_stats_count_each_status(client, user):
    notify(client, user["id"])
    notify(client, user["id"])
    assert client.get("/api/v1/stats").json() == {"sent": 2, "queued": 0, "failed": 0, "total": 2}


def test_failed_notification_can_be_retried(client, user):
    db = SessionLocal()
    log = models.NotificationLog(user_id=user["id"], type="email", content="Try again", status="failed",
                                 error="boom", created_at=datetime.utcnow())
    db.add(log)
    db.commit()
    log_id = log.id
    db.close()

    assert client.post(f"/api/v1/notifications/{log_id}/retry").status_code == 202
    assert client.get(f"/api/v1/notifications/{log_id}").json()["status"] == "sent"
    # A notification that already went out cannot be retried
    assert client.post(f"/api/v1/notifications/{log_id}/retry").status_code == 409
    assert client.post("/api/v1/notifications/999/retry").status_code == 404


def test_user_list_and_duplicate_email(client, user):
    assert client.get("/api/v1/users").json()[0]["email"] == "ada@example.com"
    assert client.post("/api/v1/users", json={"email": "ada@example.com"}).status_code == 409
