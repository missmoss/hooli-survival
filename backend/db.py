import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, create_engine, func, text
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship, sessionmaker


def _normalize_database_url(raw_url: str) -> str:
    url = (raw_url or "").strip() or "sqlite:///./office_sim.db"
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _database_url_from_parts() -> str | None:
    host = os.getenv("DB_HOST", "").strip()
    name = os.getenv("DB_NAME", "").strip()
    user = os.getenv("DB_USER", "").strip()
    password = os.getenv("DB_PASSWORD", "")
    if not (host and name and user):
        return None

    port = os.getenv("DB_PORT", "").strip() or "5432"
    encoded_user = quote_plus(user)
    encoded_password = quote_plus(password)
    return f"postgresql://{encoded_user}:{encoded_password}@{host}:{port}/{name}"


DATABASE_URL = _normalize_database_url(os.getenv("DATABASE_URL") or _database_url_from_parts() or "sqlite:///./office_sim.db")
ALEMBIC_INI_PATH = Path(__file__).resolve().with_name("alembic.ini")
ALEMBIC_SCRIPT_PATH = Path(__file__).resolve().with_name("alembic")

connect_args = {}
engine_kwargs = {"future": True}

if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "5"))
    engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    engine_kwargs["pool_recycle"] = int(os.getenv("DB_POOL_RECYCLE", "1800"))
    if DATABASE_URL.startswith("postgresql://") and "sslmode=" not in DATABASE_URL:
        connect_args["sslmode"] = os.getenv("DB_SSLMODE", "require")

engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class GameSession(Base):
    __tablename__ = "game_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    locale: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    browser_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    state: Mapped[dict] = mapped_column(JSON, nullable=False)
    characters: Mapped[dict] = mapped_column(JSON, nullable=False)
    current_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    current_project_id: Mapped[str] = mapped_column(String(128), nullable=False)
    current_scene_log_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    end_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    round_in_scene: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scene_round_limit: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    settlement_status: Mapped[str] = mapped_column(String(16), default="idle", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), onupdate=_now, nullable=False
    )

    scene_logs: Mapped[list["SceneLog"]] = relationship(back_populates="session")


class SceneLog(Base):
    __tablename__ = "scene_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    project_id: Mapped[str] = mapped_column(String(128), nullable=False)
    state_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    cast_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    state_delta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    story_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    story_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    eval_rating: Mapped[str | None] = mapped_column(String(16), nullable=True)
    eval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    eval_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    eval_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    eval_debug_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    story_debug_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    memory_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    perf_artifact: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )

    session: Mapped[GameSession] = relationship(back_populates="scene_logs")
    messages: Mapped[list["Message"]] = relationship(back_populates="scene_log")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scene_log_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scene_logs.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False
    )

    scene_log: Mapped[SceneLog] = relationship(back_populates="messages")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_game_sessions_columns()
    _migrate_scene_logs_columns()


def run_migrations() -> None:
    try:
        from alembic import command
        from alembic.config import Config
    except ImportError as exc:
        raise RuntimeError("Alembic is required to run database migrations.") from exc

    config = Config(str(ALEMBIC_INI_PATH))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_PATH))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.upgrade(config, "head")


def prepare_db() -> None:
    if DATABASE_URL.startswith("sqlite"):
        init_db()
        return
    run_migrations()


def _migrate_game_sessions_columns() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        cols = conn.execute(text("PRAGMA table_info(game_sessions)")).fetchall()
        col_names = {row[1] for row in cols}
        if "locale" not in col_names:
            conn.execute(text("ALTER TABLE game_sessions ADD COLUMN locale VARCHAR(16) DEFAULT 'en'"))
        if "browser_id" not in col_names:
            conn.execute(text("ALTER TABLE game_sessions ADD COLUMN browser_id VARCHAR(64)"))
        if "session_meta" not in col_names:
            conn.execute(text("ALTER TABLE game_sessions ADD COLUMN session_meta JSON"))


def _migrate_scene_logs_columns() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        cols = conn.execute(text("PRAGMA table_info(scene_logs)")).fetchall()
        col_names = {row[1] for row in cols}
        if "eval_reason" not in col_names:
            conn.execute(text("ALTER TABLE scene_logs ADD COLUMN eval_reason TEXT"))
        if "eval_rating" not in col_names:
            conn.execute(text("ALTER TABLE scene_logs ADD COLUMN eval_rating VARCHAR(16)"))
        if "eval_debug_json" not in col_names:
            conn.execute(text("ALTER TABLE scene_logs ADD COLUMN eval_debug_json JSON"))
        if "story_debug_json" not in col_names:
            conn.execute(text("ALTER TABLE scene_logs ADD COLUMN story_debug_json JSON"))
        if "story_provider" not in col_names:
            conn.execute(text("ALTER TABLE scene_logs ADD COLUMN story_provider VARCHAR(32)"))
        if "story_model" not in col_names:
            conn.execute(text("ALTER TABLE scene_logs ADD COLUMN story_model VARCHAR(128)"))
        if "eval_provider" not in col_names:
            conn.execute(text("ALTER TABLE scene_logs ADD COLUMN eval_provider VARCHAR(32)"))
        if "eval_model" not in col_names:
            conn.execute(text("ALTER TABLE scene_logs ADD COLUMN eval_model VARCHAR(128)"))
        if "cast_snapshot" not in col_names:
            conn.execute(text("ALTER TABLE scene_logs ADD COLUMN cast_snapshot JSON"))
        if "perf_artifact" not in col_names:
            conn.execute(text("ALTER TABLE scene_logs ADD COLUMN perf_artifact JSON"))
