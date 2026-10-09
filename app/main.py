import asyncio
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import SessionLocal, get_db
from app.rate_limit import check_rate_limit
from app.tasks import deliver_notification

app = FastAPI(title="Notification Service")
STATIC_DIR = Path(__file__).parent / "static"


def log_to_dict(log: models.NotificationLog) -> dict:
    return {
        "id": log.id,
        "user_id": log.user_id,
        "type": log.type,
        "content": log.content,
        "status": log.status,
        "error": log.error,
        "created_at": log.created_at.isoformat(),
    }


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


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
def list_notifications(limit: int = 50, db: Session = Depends(get_db)):
    logs = db.scalars(
        select(models.NotificationLog).order_by(models.NotificationLog.id.desc()).limit(min(limit, 200))
    ).all()
    return [log_to_dict(log) for log in logs]


@app.get("/api/v1/notifications/{notification_id}")
def get_notification(notification_id: int, db: Session = Depends(get_db)):
    log = db.get(models.NotificationLog, notification_id)
    if not log:
        raise HTTPException(status_code=404, detail="Notification not found")
    return log_to_dict(log)


def _recent_logs() -> list[dict]:
    db = SessionLocal()
    try:
        logs = db.scalars(
            select(models.NotificationLog).order_by(models.NotificationLog.updated_at.desc()).limit(30)
        ).all()
        return [log_to_dict(log) for log in logs]
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
