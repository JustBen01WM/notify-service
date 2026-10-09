import os
import tempfile

# Settings must be set BEFORE the app is imported.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["QUEUE_FILE"] = f"{_tmp}/queue.db"
os.environ["QUEUE_IMMEDIATE"] = "1"  # run background tasks instantly inside tests
os.environ["EMAIL_PROVIDER"] = "mock"
os.environ["RATE_LIMIT_MAX"] = "5"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def user(client):
    r = client.post("/api/v1/users", json={"email": "ada@example.com", "phone": "+2348000000000"})
    return r.json()
