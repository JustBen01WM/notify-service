"""Rate limiter: a user may create at most RATE_LIMIT_MAX notifications per window.

It counts recent rows in the database instead of keeping counters in memory,
so it keeps working when you run several servers."""
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app import config, models


def check_rate_limit(db: Session, user_id: int) -> None:
    since = datetime.utcnow() - timedelta(seconds=config.RATE_LIMIT_WINDOW_SECONDS)
    count = db.scalar(
        select(func.count())
        .select_from(models.NotificationLog)
        .where(models.NotificationLog.user_id == user_id, models.NotificationLog.created_at >= since)
    )
    if count >= config.RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {config.RATE_LIMIT_MAX} notifications "
            f"per {config.RATE_LIMIT_WINDOW_SECONDS}s per user.",
        )
