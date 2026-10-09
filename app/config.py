"""All settings live here. They come from environment variables, with safe defaults
so the project runs on a fresh computer with zero configuration."""
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./notify.db")
# Some hosts give "postgres://..." but SQLAlchemy needs "postgresql://..."
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

REDIS_URL = os.getenv("REDIS_URL", "")  # empty -> use the local SQLite queue
QUEUE_FILE = os.getenv("QUEUE_FILE", "queue.db")
QUEUE_IMMEDIATE = os.getenv("QUEUE_IMMEDIATE", "0") == "1"  # tests run tasks instantly

EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "mock")  # "mock" or "resend"
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "onboarding@resend.dev")

RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "10"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
