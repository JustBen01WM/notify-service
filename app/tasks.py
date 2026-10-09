"""The worker's job: take a notification id off the queue, send it, record the result."""
from app import email_service, models
from app.database import SessionLocal
from app.queue import huey


@huey.task(retries=2, retry_delay=3)
def deliver_notification(log_id: int) -> None:
    db = SessionLocal()
    try:
        log = db.get(models.NotificationLog, log_id)
        if log is None or log.status == "sent":
            return
        user = db.get(models.User, log.user_id)
        try:
            if log.type == "email":
                email_service.send_email(user.email, log.subject or "Notification", log.content)
            else:
                if not user.phone:
                    raise email_service.DeliveryError("User has no phone number")
                email_service.send_sms(user.phone, log.content)
            log.status, log.error = "sent", None
        except Exception as exc:  # record the failure, then let the queue retry
            log.status, log.error = "failed", str(exc)
            db.commit()
            raise
        db.commit()
    finally:
        db.close()
