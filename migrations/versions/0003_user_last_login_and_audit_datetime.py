"""add user last_login and audit improvements

Revision ID: 0003_user_last_login_and_audit_datetime
Revises: 0002_event_item_kind_check_sync
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_user_last_login_and_audit_datetime"
down_revision = "0002_event_item_kind_check_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("audit_log", sa.Column("description", sa.String(length=255), nullable=True))
    op.add_column("audit_log", sa.Column("created_at_new", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE audit_log SET created_at_new = created_at::timestamp")
    op.drop_column("audit_log", "created_at")
    op.alter_column("audit_log", "created_at_new", new_column_name="created_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.execute("UPDATE audit_log SET description = action WHERE description IS NULL")
    op.alter_column("audit_log", "description", existing_type=sa.String(length=255), nullable=False)


def downgrade() -> None:
    op.add_column("audit_log", sa.Column("created_at_old", sa.Date(), nullable=True))
    op.execute("UPDATE audit_log SET created_at_old = created_at::date")
    op.drop_column("audit_log", "created_at")
    op.alter_column("audit_log", "created_at_old", new_column_name="created_at", existing_type=sa.Date(), nullable=False)
    op.drop_column("audit_log", "description")
    op.drop_column("users", "last_login_at")
