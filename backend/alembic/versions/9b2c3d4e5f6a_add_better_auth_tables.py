"""add_better_auth_tables

Revision ID: 9b2c3d4e5f6a
Revises: 8a1b2c3d4e5f
Create Date: 2026-05-07 12:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b2c3d4e5f6a"
down_revision: Union[str, None] = "8a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column("users", sa.Column("image", sa.Text(), nullable=True))
    op.create_unique_constraint("users_email_key", "users", ["email"])
    op.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('users', 'id'),
            COALESCE((SELECT MAX(id) FROM users), 0) + 1,
            false
        )
        """
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("auth_sessions_user_id_idx", "auth_sessions", ["user_id"])

    op.create_table(
        "auth_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("id_token", sa.Text(), nullable=True),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("password", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("auth_accounts_user_id_idx", "auth_accounts", ["user_id"])

    op.create_table(
        "auth_verifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("identifier", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("auth_verifications_identifier_idx", "auth_verifications", ["identifier"])


def downgrade() -> None:
    op.drop_index("auth_verifications_identifier_idx", table_name="auth_verifications")
    op.drop_table("auth_verifications")
    op.drop_index("auth_accounts_user_id_idx", table_name="auth_accounts")
    op.drop_table("auth_accounts")
    op.drop_index("auth_sessions_user_id_idx", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.drop_column("users", "image")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "email")
