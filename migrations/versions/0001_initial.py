"""initial schema

Revision ID: 0001_initial
Revises: None
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE asset_state AS ENUM ('n_o','on_balance','off_balance','written_off')")
    op.execute("CREATE TYPE event_status AS ENUM ('draft','active','closed')")
    op.execute("CREATE TYPE event_item_kind AS ENUM ('object','group')")
    op.execute("CREATE TYPE valuation_kind AS ENUM ('accounting','assessment_act','price_list','initial_value_act','residual_value_statement')")

    op.create_table('roles', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('code', sa.String(50), nullable=False, unique=True), sa.Column('name', sa.String(120), nullable=False))
    op.create_table('users', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('username', sa.String(120), unique=True, nullable=False), sa.Column('full_name', sa.String(255)), sa.Column('password_hash', sa.String(255), nullable=False), sa.Column('role_id', sa.Integer(), sa.ForeignKey('roles.id'), nullable=False), sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'), sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.create_table('units', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('code', sa.String(80), unique=True, nullable=False), sa.Column('name', sa.String(255), nullable=False), sa.Column('parent_id', sa.Integer(), sa.ForeignKey('units.id')), sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.create_table('services', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('code', sa.String(80), unique=True, nullable=False), sa.Column('name', sa.String(255), nullable=False), sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.create_table('nomenclature', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('code', sa.String(80), unique=True, nullable=False), sa.Column('name', sa.String(255), nullable=False), sa.Column('unit_of_measure', sa.String(50)), sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.create_table('document_types', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('code', sa.String(80), unique=True, nullable=False), sa.Column('name', sa.String(255), nullable=False), sa.Column('default_extension', sa.String(10)), sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.create_table('asset_objects', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('nomenclature_id', sa.Integer(), sa.ForeignKey('nomenclature.id'), nullable=False), sa.Column('inventory_number', sa.String(120), unique=True), sa.Column('serial_number', sa.String(120)), sa.Column('vin', sa.String(120), unique=True), sa.Column('plate_number', sa.String(60)), sa.Column('state', sa.Enum(name='asset_state', native_enum=False)), sa.Column('notes', sa.Text()), sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.create_table('events', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('event_date', sa.Date(), nullable=False), sa.Column('status', sa.Enum(name='event_status', native_enum=False), nullable=False), sa.Column('title', sa.String(255), nullable=False), sa.Column('short_description', sa.Text()), sa.Column('location', sa.String(255)), sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id')), sa.Column('updated_by_id', sa.Integer(), sa.ForeignKey('users.id')), sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.create_table('event_units', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False), sa.Column('unit_id', sa.Integer(), sa.ForeignKey('units.id'), nullable=False), sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False), sa.UniqueConstraint('event_id','unit_id', name='uq_event_unit'))
    op.create_table('event_items', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False), sa.Column('unit_id', sa.Integer(), sa.ForeignKey('units.id'), nullable=False), sa.Column('service_id', sa.Integer(), sa.ForeignKey('services.id'), nullable=False), sa.Column('kind', sa.Enum(name='event_item_kind', native_enum=False), nullable=False), sa.Column('asset_object_id', sa.Integer(), sa.ForeignKey('asset_objects.id')), sa.Column('nomenclature_id', sa.Integer(), sa.ForeignKey('nomenclature.id')), sa.Column('qty', sa.Integer(), nullable=False), sa.Column('notes', sa.Text()), sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False), sa.CheckConstraint('qty > 0', name='ck_event_item_qty_pos'))
    op.create_table('documents', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False), sa.Column('document_type_id', sa.Integer(), sa.ForeignKey('document_types.id'), nullable=False), sa.Column('doc_no', sa.String(120), nullable=False), sa.Column('doc_date', sa.Date()), sa.Column('reg_date', sa.Date()), sa.Column('title', sa.String(255)), sa.Column('file_path', sa.String(500), nullable=False), sa.Column('sha256', sa.String(64), nullable=False), sa.Column('uploaded_by_id', sa.Integer(), sa.ForeignKey('users.id')), sa.Column('generated_by_id', sa.Integer(), sa.ForeignKey('users.id')), sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.create_table('valuations', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False), sa.Column('valuation_kind', sa.Enum(name='valuation_kind', native_enum=False), nullable=False), sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id')), sa.Column('value_uah', sa.Numeric(14,2)), sa.Column('date_effective', sa.Date(), nullable=False), sa.Column('notes', sa.Text()), sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.create_table('valuation_links', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('valuation_id', sa.Integer(), sa.ForeignKey('valuations.id', ondelete='CASCADE'), nullable=False), sa.Column('event_item_id', sa.Integer(), sa.ForeignKey('event_items.id', ondelete='CASCADE'), nullable=False), sa.Column('applies_qty', sa.Integer(), nullable=False), sa.CheckConstraint('applies_qty > 0', name='ck_valuation_link_qty_pos'), sa.UniqueConstraint('valuation_id','event_item_id', name='uq_valuation_item'), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.create_table('audit_log', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('entity_type', sa.String(80), nullable=False), sa.Column('entity_id', sa.String(80), nullable=False), sa.Column('action', sa.String(40), nullable=False), sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id')), sa.Column('diff_json', sa.JSON()), sa.Column('created_at', sa.Date(), nullable=False))


def downgrade() -> None:
    op.drop_table('audit_log')
    op.drop_table('valuation_links')
    op.drop_table('valuations')
    op.drop_table('documents')
    op.drop_table('event_items')
    op.drop_table('event_units')
    op.drop_table('events')
    op.drop_table('asset_objects')
    op.drop_table('document_types')
    op.drop_table('nomenclature')
    op.drop_table('services')
    op.drop_table('units')
    op.drop_table('users')
    op.drop_table('roles')
    op.execute("DROP TYPE valuation_kind")
    op.execute("DROP TYPE event_item_kind")
    op.execute("DROP TYPE event_status")
    op.execute("DROP TYPE asset_state")
