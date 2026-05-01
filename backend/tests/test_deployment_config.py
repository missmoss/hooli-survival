import importlib
import sys
from pathlib import Path

import sqlalchemy
from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


MODULE_ORDER = ["state", "prompt_registry", "events", "db", "ai", "main"]


def _reload_modules(tmp_path, monkeypatch, **env_overrides):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("OFFICE_SIM_DISABLE_TRANSCRIPT_WRITE", "1")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    monkeypatch.setenv("SESSION_CREATE_DAILY_LIMIT", "100")
    monkeypatch.setenv("TURN_REQUESTS_PER_MINUTE_LIMIT", "100")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("REORG_PROBABILITY", "0")

    for key, value in env_overrides.items():
        monkeypatch.setenv(key, value)

    for name in MODULE_ORDER:
        sys.modules.pop(name, None)

    modules = {name: importlib.import_module(name) for name in MODULE_ORDER}
    modules["main"].SESSION_CREATE_LIMITER.clear()
    modules["main"].TURN_REQUEST_LIMITER.clear()
    return modules


def test_db_normalizes_postgres_scheme(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@localhost:5432/office_sim")
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *args, **kwargs: object())
    sys.modules.pop("db", None)

    db_module = importlib.import_module("db")

    assert db_module.DATABASE_URL == "postgresql+psycopg://user:pass@localhost:5432/office_sim"


def test_db_can_build_url_from_split_env_vars(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "db.example.supabase.co")
    monkeypatch.setenv("DB_NAME", "postgres")
    monkeypatch.setenv("DB_USER", "postgres.user")
    monkeypatch.setenv("DB_PASSWORD", "p@ss word")
    monkeypatch.setenv("DB_PORT", "6543")
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *args, **kwargs: object())
    sys.modules.pop("db", None)

    db_module = importlib.import_module("db")

    assert db_module.DATABASE_URL == "postgresql+psycopg://postgres.user:p%40ss+word@db.example.supabase.co:6543/postgres"


def test_cross_site_cookie_settings_are_applied(tmp_path, monkeypatch):
    modules = _reload_modules(
        tmp_path,
        monkeypatch,
        SESSION_COOKIE_SECURE="1",
        SESSION_COOKIE_SAMESITE="none",
        SESSION_COOKIE_DOMAIN="api.example.com",
        ALLOWED_ORIGIN_REGEX=r"https://.*\.vercel\.app",
    )
    main = modules["main"]
    main.story_response = lambda system_prompt, messages: ("Scene opens.", {"source": "test_opening", "attempts": []})

    with TestClient(main.app) as client:
        response = client.post("/sessions", json={"player_name": "Claire", "locale": "en"})

    assert response.status_code == 200
    assert main._allowed_origin_regex() == r"https://.*\.vercel\.app"
    set_cookie = response.headers["set-cookie"]
    assert "Secure" in set_cookie
    assert "samesite=none" in set_cookie.lower()
    assert "domain=api.example.com" in set_cookie.lower()


def test_browser_id_and_session_meta_are_persisted(tmp_path, monkeypatch):
    modules = _reload_modules(tmp_path, monkeypatch)
    main = modules["main"]
    db_module = modules["db"]
    main.story_response = lambda system_prompt, messages: ("Scene opens.", {"source": "test_opening", "attempts": []})

    with TestClient(main.app) as client:
        response = client.post(
            "/sessions",
            json={"player_name": "Claire", "locale": "en"},
            headers={"X-Office-Sim-Browser-Id": "br_testclient1234"},
        )

    assert response.status_code == 200
    session_id = response.json()["session_id"]

    db = db_module.SessionLocal()
    try:
        session = db.get(db_module.GameSession, session_id)
        assert session is not None
        assert session.browser_id == "br_testclient1234"
        assert session.session_meta["browser_id"] == "br_testclient1234"
        events = (
            db.query(db_module.SessionDebugEvent)
            .filter(db_module.SessionDebugEvent.session_id == session_id)
            .order_by(db_module.SessionDebugEvent.created_at.asc())
            .all()
        )
        assert len(events) == 1
        assert events[0].event_type == "session_created"
        assert events[0].requested_session_id == session_id
        assert events[0].cookie_session_id == session_id
        assert events[0].browser_id_header == "br_testclient1234"
        assert events[0].cookie_name == "office_sim_session"
    finally:
        db.close()


def test_session_routes_require_matching_cookie(tmp_path, monkeypatch):
    modules = _reload_modules(tmp_path, monkeypatch)
    main = modules["main"]
    db_module = modules["db"]
    main.story_response = lambda system_prompt, messages: ("Scene opens.", {"source": "test_opening", "attempts": []})

    with TestClient(main.app) as client:
        response = client.post("/sessions", json={"player_name": "Claire", "locale": "en"})
        session_id = response.json()["session_id"]

    with TestClient(main.app) as unauthenticated_client:
        response = unauthenticated_client.get(f"/sessions/{session_id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Session cookie does not match the requested session"
    db = db_module.SessionLocal()
    try:
        events = (
            db.query(db_module.SessionDebugEvent)
            .filter(db_module.SessionDebugEvent.requested_session_id == session_id)
            .order_by(db_module.SessionDebugEvent.created_at.asc())
            .all()
        )
        assert [event.event_type for event in events] == ["session_created", "cookie_mismatch"]
        mismatch = events[-1]
        assert mismatch.session_id == session_id
        assert mismatch.cookie_session_id is None
        assert mismatch.cookie_present is False
        assert mismatch.path == f"/sessions/{session_id}"
        assert mismatch.notes == "Session cookie does not match the requested session"
    finally:
        db.close()


def test_turn_rate_limit_is_enforced(tmp_path, monkeypatch):
    modules = _reload_modules(tmp_path, monkeypatch, TURN_REQUESTS_PER_MINUTE_LIMIT="1")
    main = modules["main"]
    main.story_response = lambda system_prompt, messages: (
        "Scene opens." if len(messages) == 1 else "Scene continues.",
        {"source": "test", "attempts": []},
    )
    main.evaluate_rating = lambda *args, **kwargs: ("neutral", "test", {})
    main.summarize_memory = lambda *args, **kwargs: "summary"

    with TestClient(main.app) as client:
        response = client.post("/sessions", json={"player_name": "Claire", "locale": "en"})
        assert response.status_code == 200
        session_id = response.json()["session_id"]

        first_turn = client.post(f"/sessions/{session_id}/turn", json={"message": "Keep going"})
        second_turn = client.post(f"/sessions/{session_id}/turn", json={"message": "Keep going"})

    assert first_turn.status_code == 200
    assert second_turn.status_code == 429
    assert second_turn.json()["detail"] == "Too many turn requests"
