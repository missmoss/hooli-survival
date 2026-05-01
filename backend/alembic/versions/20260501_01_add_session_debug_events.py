"""add session debug events

Revision ID: 20260501_01
Revises: 20260430_01
Create Date: 2026-05-01 08:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260501_01"
down_revision = "20260430_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_debug_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("requested_session_id", sa.String(length=36), nullable=True),
        sa.Column("cookie_session_id", sa.String(length=64), nullable=True),
        sa.Column("cookie_present", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cookie_names", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("cookie_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("method", sa.String(length=8), nullable=True),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("query_string", sa.Text(), nullable=True),
        sa.Column("origin", sa.Text(), nullable=True),
        sa.Column("referer", sa.Text(), nullable=True),
        sa.Column("host", sa.Text(), nullable=True),
        sa.Column("x_forwarded_host", sa.Text(), nullable=True),
        sa.Column("x_forwarded_proto", sa.String(length=32), nullable=True),
        sa.Column("sec_fetch_site", sa.String(length=32), nullable=True),
        sa.Column("sec_fetch_mode", sa.String(length=32), nullable=True),
        sa.Column("sec_fetch_dest", sa.String(length=32), nullable=True),
        sa.Column("browser_id_header", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("cookie_name", sa.String(length=64), nullable=True),
        sa.Column("cookie_secure", sa.Boolean(), nullable=True),
        sa.Column("cookie_samesite", sa.String(length=16), nullable=True),
        sa.Column("cookie_domain", sa.String(length=255), nullable=True),
        sa.Column("cookie_path", sa.String(length=255), nullable=True),
        sa.Column("cookie_max_age_seconds", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "event_type in ('session_created', 'cookie_mismatch')",
            name="session_debug_events_event_type_check",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("session_debug_events_created_at_idx", "session_debug_events", ["created_at"], unique=False)
    op.create_index(
        "session_debug_events_event_type_created_at_idx",
        "session_debug_events",
        ["event_type", "created_at"],
        unique=False,
    )
    op.create_index("session_debug_events_session_id_idx", "session_debug_events", ["session_id"], unique=False)
    op.create_index(
        "session_debug_events_requested_session_id_idx",
        "session_debug_events",
        ["requested_session_id"],
        unique=False,
    )
    op.create_index(
        "session_debug_events_cookie_session_id_idx",
        "session_debug_events",
        ["cookie_session_id"],
        unique=False,
    )
    op.create_index(
        "session_debug_events_browser_id_header_idx",
        "session_debug_events",
        ["browser_id_header"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("session_debug_events_browser_id_header_idx", table_name="session_debug_events")
    op.drop_index("session_debug_events_cookie_session_id_idx", table_name="session_debug_events")
    op.drop_index("session_debug_events_requested_session_id_idx", table_name="session_debug_events")
    op.drop_index("session_debug_events_session_id_idx", table_name="session_debug_events")
    op.drop_index("session_debug_events_event_type_created_at_idx", table_name="session_debug_events")
    op.drop_index("session_debug_events_created_at_idx", table_name="session_debug_events")
    op.drop_table("session_debug_events")
