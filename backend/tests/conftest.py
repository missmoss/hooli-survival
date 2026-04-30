import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


MODULE_ORDER = ["state", "prompt_registry", "events", "db", "ai", "main"]


@pytest.fixture
def app_modules(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("OFFICE_SIM_DISABLE_TRANSCRIPT_WRITE", "1")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    monkeypatch.setenv("SESSION_CREATE_DAILY_LIMIT", "100")
    monkeypatch.setenv("TURN_REQUESTS_PER_MINUTE_LIMIT", "100")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("REORG_PROBABILITY", "0")

    for name in MODULE_ORDER:
        sys.modules.pop(name, None)

    modules = {name: importlib.import_module(name) for name in MODULE_ORDER}
    modules["main"].SESSION_CREATE_LIMITER.clear()
    modules["main"].TURN_REQUEST_LIMITER.clear()
    modules["events"].random.seed(7)
    modules["prompt_registry"].random.seed(7)
    return modules


@pytest.fixture
def client(app_modules):
    with TestClient(app_modules["main"].app) as test_client:
        yield test_client
