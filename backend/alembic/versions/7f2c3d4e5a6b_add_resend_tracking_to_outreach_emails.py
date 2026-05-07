"""add_resend_tracking_to_outreach_emails

Revision ID: 7f2c3d4e5a6b
Revises: 2697a3a6df88
Create Date: 2026-05-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f2c3d4e5a6b"
down_revision: Union[str, None] = "2697a3a6df88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "outreach_emails",
        sa.Column("resend_message_id", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "outreach_emails",
        sa.Column("last_send_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outreach_emails",
        sa.Column("last_event", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("outreach_emails", "resend_message_id", server_default=None)
    op.alter_column("outreach_emails", "last_event", server_default=None)


def downgrade() -> None:
    op.drop_column("outreach_emails", "last_event")
    op.drop_column("outreach_emails", "last_send_attempt_at")
    op.drop_column("outreach_emails", "resend_message_id")
