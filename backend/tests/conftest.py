import os
import tempfile
from pathlib import Path

import pytest

TEST_ROOT = tempfile.TemporaryDirectory(prefix="ututor-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_ROOT.name}/test.db"
os.environ["JWT_SECRET"] = "test-only-secret-not-for-production-1234567890"
os.environ["ADMIN_CREDENTIALS_PATH"] = f"{TEST_ROOT.name}/.admin_credentials"

from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app
from app.auth import login_attempts


@pytest.fixture
def client():
    login_attempts.clear()
    Base.metadata.drop_all(engine)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def admin(client):
    password = Path(os.environ["ADMIN_CREDENTIALS_PATH"]).read_text().split("Пароль: ")[1].strip()
    result = client.post("/api/auth/login", json={"username": "admin", "password": password})
    assert result.status_code == 200
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


@pytest.fixture
def teacher(client, admin):
    data = client.post("/api/teachers", headers=admin, json={"username": "teacher", "name": "Анна"}).json()
    login = client.post("/api/auth/login", json={"username": "teacher", "password": data["password"]}).json()
    return {"Authorization": f"Bearer {login['access_token']}"}
