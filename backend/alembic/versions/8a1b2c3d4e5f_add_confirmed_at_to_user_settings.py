"""add_confirmed_at_to_user_settings

Revision ID: 8a1b2c3d4e5f
Revises: 7f2c3d4e5a6b
Create Date: 2026-05-06 13:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8a1b2c3d4e5f"
down_revision: Union[str, None] = "7f2c3d4e5a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "confirmed_at")
