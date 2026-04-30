"""create initial schema

Revision ID: 20260430_01
Revises:
Create Date: 2026-04-30 14:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260430_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("browser_id", sa.String(length=64), nullable=True),
        sa.Column("session_meta", sa.JSON(), nullable=True),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("characters", sa.JSON(), nullable=False),
        sa.Column("current_event_id", sa.String(length=128), nullable=False),
        sa.Column("current_project_id", sa.String(length=128), nullable=False),
        sa.Column("current_scene_log_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("end_reason", sa.String(length=32), nullable=True),
        sa.Column("round_in_scene", sa.Integer(), nullable=False),
        sa.Column("scene_round_limit", sa.Integer(), nullable=False),
        sa.Column("settlement_status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "scene_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("state_snapshot", sa.JSON(), nullable=False),
        sa.Column("cast_snapshot", sa.JSON(), nullable=True),
        sa.Column("state_delta", sa.JSON(), nullable=True),
        sa.Column("story_provider", sa.String(length=32), nullable=True),
        sa.Column("story_model", sa.String(length=128), nullable=True),
        sa.Column("eval_rating", sa.String(length=16), nullable=True),
        sa.Column("eval_reason", sa.Text(), nullable=True),
        sa.Column("eval_provider", sa.String(length=32), nullable=True),
        sa.Column("eval_model", sa.String(length=128), nullable=True),
        sa.Column("eval_debug_json", sa.JSON(), nullable=True),
        sa.Column("story_debug_json", sa.JSON(), nullable=True),
        sa.Column("memory_text", sa.Text(), nullable=True),
        sa.Column("perf_artifact", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["game_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scene_log_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["scene_log_id"], ["scene_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("scene_logs")
    op.drop_table("game_sessions")
