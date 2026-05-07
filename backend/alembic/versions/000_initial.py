"""create initial tables

Revision ID: 000_initial
Revises:
Create Date: 2026-05-07

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '000_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.Text(), nullable=False),
        # email, email_verified, image added in migration 9b2c3d4e5f6a
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # user_settings
    op.create_table(
        'user_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('sender_name', sa.Text(), nullable=False, server_default=''),
        sa.Column('from_email_prefix', sa.Text(), nullable=False, server_default=''),
        sa.Column('reply_to_email', sa.Text(), nullable=False, server_default=''),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('company_profiles.id'), nullable=True),
        # confirmed_at added in migration 8a1b2c3d4e5f
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # company_profiles
    op.create_table(
        'company_profiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id'), nullable=True),
        sa.Column('company_name', sa.Text(), nullable=False, server_default=''),
        sa.Column('profile_data', sa.JSON(), nullable=True),
        sa.Column('profile_markdown', sa.Text(), nullable=False, server_default=''),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # tasks (without ended_at, cancelled - those come in migration 001)
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('type', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='pending'),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('result_summary', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # task_logs
    op.create_table(
        'task_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id'), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('step_name', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='pending'),
        sa.Column('message', sa.Text(), nullable=False, server_default=''),
        sa.Column('progress', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # leads (without user_note - that comes in migration 2697)
    op.create_table(
        'leads',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id'), nullable=False),
        sa.Column('company_name', sa.Text(), nullable=False, server_default=''),
        sa.Column('website', sa.Text(), nullable=False, server_default=''),
        sa.Column('country', sa.Text(), nullable=False, server_default=''),
        sa.Column('industry', sa.Text(), nullable=False, server_default=''),
        sa.Column('company_role', sa.Text(), nullable=False, server_default=''),
        sa.Column('contact_name', sa.Text(), nullable=False, server_default=''),
        sa.Column('email', sa.Text(), nullable=False, server_default=''),
        sa.Column('phone', sa.Text(), nullable=False, server_default=''),
        sa.Column('ai_summary', sa.Text(), nullable=False, server_default=''),
        sa.Column('business_match', sa.Text(), nullable=False, server_default=''),
        sa.Column('outreach_suggestion', sa.Text(), nullable=False, server_default=''),
        sa.Column('match_score', sa.Float(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # outreach_emails (without resend tracking - that comes in migration 7f2c)
    op.create_table(
        'outreach_emails',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('lead_id', sa.Integer(), sa.ForeignKey('leads.id'), nullable=False),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id'), nullable=True),
        sa.Column('email_subject', sa.Text(), nullable=False, server_default=''),
        sa.Column('email_body', sa.Text(), nullable=False, server_default=''),
        sa.Column('send_status', sa.Text(), nullable=False, server_default='draft'),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # alembic_version is managed by Alembic automatically — do NOT create it here


def downgrade() -> None:
    op.drop_table('outreach_emails')
    op.drop_table('leads')
    op.drop_table('task_logs')
    op.drop_table('tasks')
    op.drop_table('user_settings')
    op.drop_table('company_profiles')
    op.drop_table('users')
