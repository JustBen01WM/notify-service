import asyncio
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import email_service, models, schemas
from app.database import SessionLocal, get_db
from app.rate_limit import check_rate_limit
from app.tasks import deliver_notification

app = FastAPI(title="WM Notifier")
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def log_to_dict(log: models.NotificationLog, email: str | None = None) -> dict:
    return {
        "id": log.id,
        "user_id": log.user_id,
        "email": email,
        "type": log.type,
        "subject": log.subject,
        "content": log.content,
        "status": log.status,
        "error": log.error,
        "created_at": log.created_at.isoformat() + "Z",
        "updated_at": log.updated_at.isoformat() + "Z",
    }


def _logs_query():
    return select(models.NotificationLog, models.User.email).join(
        models.User, models.User.id == models.NotificationLog.user_id
    )


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(STATIC_DIR / "wm-notifier.ico")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/users", status_code=201)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    user = models.User(email=payload.email, phone=payload.phone)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A user with that email already exists")
    db.refresh(user)
    return {"id": user.id, "email": user.email, "phone": user.phone}


@app.get("/api/v1/users")
def list_users(db: Session = Depends(get_db)):
    users = db.scalars(select(models.User).order_by(models.User.id)).all()
    return [{"id": u.id, "email": u.email, "phone": u.phone} for u in users]


@app.post("/api/v1/templates", status_code=201)
def create_template(payload: schemas.TemplateCreate, db: Session = Depends(get_db)):
    tpl = models.NotificationTemplate(**payload.model_dump())
    db.add(tpl)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A template with that name already exists")
    db.refresh(tpl)
    return {"id": tpl.id, "name": tpl.name}


@app.get("/api/v1/templates")
def list_templates(db: Session = Depends(get_db)):
    rows = db.scalars(select(models.NotificationTemplate).order_by(models.NotificationTemplate.name)).all()
    return [{"id": t.id, "name": t.name, "type": t.type, "subject": t.subject, "body": t.body} for t in rows]


@app.delete("/api/v1/templates/{template_id}", status_code=204)
def delete_template(template_id: int, db: Session = Depends(get_db)):
    tpl = db.get(models.NotificationTemplate, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(tpl)
    db.commit()


def _settings_view() -> dict:
    s = email_service.load_settings()
    key = s["api_key"]
    return {
        "mode": "live" if email_service.is_live(s) else "test",
        "use_real": s["use_real"],
        "api_key_set": bool(key),
        "api_key_hint": f"re_…{key[-4:]}" if key else None,  # the full key is never sent to the browser
        "from_email": s["from_email"],
    }


@app.get("/api/v1/settings")
def get_settings():
    return _settings_view()


@app.put("/api/v1/settings")
def update_settings(payload: schemas.SettingsUpdate):
    updates = payload.model_dump(exclude_unset=True)
    if "api_key" in updates:
        updates["api_key"] = (updates["api_key"] or "").strip()
    if "from_email" in updates:
        updates["from_email"] = (updates["from_email"] or "").strip() or None
    current = email_service.load_settings()
    new_key = updates.get("api_key", current["api_key"])
    if updates.get("use_real") and not new_key:
        raise HTTPException(status_code=422, detail="Add your Resend API key before switching to live mode.")
    email_service.save_settings(**updates)
    return _settings_view()


@app.post("/api/v1/settings/test")
def send_test_email(payload: schemas.TestEmail):
    """Sends one email right now (not queued) so you can see straight away whether it works."""
    try:
        email_service.send_email(payload.to, "WM Notifier test", "If you can read this, WM Notifier is sending real emails.")
    except email_service.DeliveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"mode": _settings_view()["mode"], "to": payload.to}


@app.post("/api/v1/notify", status_code=202)
def notify(payload: schemas.NotifyRequest, db: Session = Depends(get_db)):
    """Ingestion endpoint: validate, save as 'queued', hand off to the worker, reply instantly."""
    user = db.get(models.User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    subject, content = payload.subject, payload.content
    if payload.template_name:
        tpl = db.scalar(
            select(models.NotificationTemplate).where(models.NotificationTemplate.name == payload.template_name)
        )
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        try:
            content = tpl.body.format_map(payload.variables)
            subject = (tpl.subject or "").format_map(payload.variables) or subject
        except KeyError as missing:
            raise HTTPException(status_code=422, detail=f"Missing template variable: {missing}")
    if not content:
        raise HTTPException(status_code=422, detail="Provide either 'content' or 'template_name'")

    check_rate_limit(db, payload.user_id)

    log = models.NotificationLog(user_id=user.id, type=payload.type, subject=subject, content=content)
    db.add(log)
    db.commit()
    db.refresh(log)

    deliver_notification(log.id)  # goes onto the queue; the worker does the real sending
    return {"notification_id": log.id, "status": log.status}


@app.get("/api/v1/notifications")
def list_notifications(
    limit: int = 50,
    status: str | None = None,
    type_: str | None = Query(default=None, alias="type"),
    q: str | None = None,
    db: Session = Depends(get_db),
):
    query = _logs_query()
    if status:
        query = query.where(models.NotificationLog.status == status)
    if type_:
        query = query.where(models.NotificationLog.type == type_)
    if q:
        like = f"%{q}%"
        query = query.where(
            or_(
                models.NotificationLog.content.ilike(like),
                models.NotificationLog.subject.ilike(like),
                models.User.email.ilike(like),
            )
        )
    rows = db.execute(query.order_by(models.NotificationLog.id.desc()).limit(min(limit, 200))).all()
    return [log_to_dict(log, email) for log, email in rows]


@app.get("/api/v1/stats")
def stats(db: Session = Depends(get_db)):
    counts = dict(
        db.execute(
            select(models.NotificationLog.status, func.count()).group_by(models.NotificationLog.status)
        ).all()
    )
    result = {"sent": 0, "queued": 0, "failed": 0, **counts}
    result["total"] = sum(counts.values())
    return result


@app.get("/api/v1/notifications/{notification_id}")
def get_notification(notification_id: int, db: Session = Depends(get_db)):
    row = db.execute(_logs_query().where(models.NotificationLog.id == notification_id)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    return log_to_dict(*row)


@app.post("/api/v1/notifications/{notification_id}/retry", status_code=202)
def retry_notification(notification_id: int, db: Session = Depends(get_db)):
    """Send a failed notification again."""
    log = db.get(models.NotificationLog, notification_id)
    if not log:
        raise HTTPException(status_code=404, detail="Notification not found")
    if log.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed notifications can be retried")
    log.status, log.error = "queued", None
    db.commit()
    deliver_notification(log.id)
    return {"notification_id": log.id, "status": "queued"}


def _recent_logs() -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.execute(_logs_query().order_by(models.NotificationLog.updated_at.desc()).limit(30)).all()
        return [log_to_dict(log, email) for log, email in rows]
    finally:
        db.close()


@app.websocket("/ws")
async def live_updates(websocket: WebSocket):
    """Pushes every new or changed notification to the browser. The worker runs in a
    separate process, so we watch the database for changes once per second."""
    await websocket.accept()
    seen: dict[int, str] = {}
    try:
        while True:
            for item in reversed(await asyncio.to_thread(_recent_logs)):
                if seen.get(item["id"]) != item["status"]:
                    seen[item["id"]] = item["status"]
                    await websocket.send_json(item)
            await asyncio.sleep(1)
    except (WebSocketDisconnect, RuntimeError):
        pass
