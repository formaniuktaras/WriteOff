"""sync event_items kind check with SQLAlchemy model

Revision ID: 0002_event_item_kind_check_sync
Revises: 0001_initial
Create Date: 2026-03-28
"""

from alembic import op


revision = "0002_event_item_kind_check_sync"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_event_item_kind_constraints",
        "event_items",
        "(kind='object' AND asset_object_id IS NOT NULL AND nomenclature_id IS NULL AND qty = 1) OR "
        "(kind='group' AND asset_object_id IS NULL AND nomenclature_id IS NOT NULL AND qty > 0)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_event_item_kind_constraints", "event_items", type_="check")
