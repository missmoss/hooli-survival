"""allow db_readback_found debug event

Revision ID: 20260501_02
Revises: 20260501_01
Create Date: 2026-05-01 10:15:00
"""

from __future__ import annotations

from alembic import op


revision = "20260501_02"
down_revision = "20260501_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("session_debug_events_event_type_check", "session_debug_events", type_="check")
    op.create_check_constraint(
        "session_debug_events_event_type_check",
        "session_debug_events",
        "event_type in ('session_created', 'db_readback_found', 'cookie_mismatch')",
    )


def downgrade() -> None:
    op.drop_constraint("session_debug_events_event_type_check", "session_debug_events", type_="check")
    op.create_check_constraint(
        "session_debug_events_event_type_check",
        "session_debug_events",
        "event_type in ('session_created', 'cookie_mismatch')",
    )
