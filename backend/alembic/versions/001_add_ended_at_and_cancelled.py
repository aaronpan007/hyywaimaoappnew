"""add_ended_at_and_cancelled_to_tasks

Revision ID: 001_add_ended_at_and_cancelled
Revises:
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa

revision = "001_add_ended_at_and_cancelled"
down_revision = '000_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("cancelled", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("tasks", "cancelled")
    op.drop_column("tasks", "ended_at")
