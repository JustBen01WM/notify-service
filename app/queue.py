"""The background queue.

Locally: a SQLite file (no installation needed, works on Windows).
In production: Redis, simply by setting the REDIS_URL environment variable."""
from huey import RedisHuey, SqliteHuey
from app import config

if config.REDIS_URL:
    huey = RedisHuey("notify", url=config.REDIS_URL, immediate=config.QUEUE_IMMEDIATE)
else:
    huey = SqliteHuey("notify", filename=config.QUEUE_FILE, immediate=config.QUEUE_IMMEDIATE)
