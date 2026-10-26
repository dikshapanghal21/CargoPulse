"""Initial CargoPulse schema: carriers, routes, shipments, status history, alerts.

Revision ID: 0001
Revises: 
Create Date: 2026-10-26 05:29:32.086727

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('carriers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('code', sa.String(length=10), nullable=False),
    sa.Column('contact_email', sa.String(length=255), nullable=True),
    sa.Column('contact_phone', sa.String(length=40), nullable=True),
    sa.Column('website', sa.String(length=255), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("code ~ '^[A-Z0-9]{2,10}$'", name=op.f('ck_carriers_code_format')),
    sa.CheckConstraint('char_length(trim(name)) >= 2', name=op.f('ck_carriers_name_not_blank')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_carriers')),
    sa.UniqueConstraint('code', name=op.f('uq_carriers_code')),
    sa.UniqueConstraint('name', name=op.f('uq_carriers_name'))
    )
    op.create_table('routes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('origin_city', sa.String(length=100), nullable=False),
    sa.Column('origin_country', sa.String(length=2), nullable=False),
    sa.Column('destination_city', sa.String(length=100), nullable=False),
    sa.Column('destination_country', sa.String(length=2), nullable=False),
    sa.Column('mode', sa.String(length=16), nullable=False),
    sa.Column('distance_km', sa.Integer(), nullable=False),
    sa.Column('estimated_transit_days', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("code ~ '^[A-Z0-9-]{3,20}$'", name=op.f('ck_routes_code_format')),
    sa.CheckConstraint("mode IN ('road', 'rail', 'air', 'ocean')", name=op.f('ck_routes_mode_valid')),
    sa.CheckConstraint('NOT (lower(origin_city) = lower(destination_city) AND upper(origin_country) = upper(destination_country))', name=op.f('ck_routes_origin_ne_destination')),
    sa.CheckConstraint('distance_km > 0', name=op.f('ck_routes_distance_positive')),
    sa.CheckConstraint('estimated_transit_days > 0 AND estimated_transit_days <= 120', name=op.f('ck_routes_transit_days_range')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_routes')),
    sa.UniqueConstraint('code', name=op.f('uq_routes_code')),
    sa.UniqueConstraint('origin_city', 'origin_country', 'destination_city', 'destination_country', 'mode', name='uq_routes_lane_mode')
    )
    op.create_index('ix_routes_origin_destination', 'routes', ['origin_city', 'destination_city'], unique=False)
    op.create_table('shipments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tracking_id', sa.String(length=32), nullable=False),
    sa.Column('reference', sa.String(length=64), nullable=True),
    sa.Column('customer_name', sa.String(length=160), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('carrier_id', sa.Integer(), nullable=False),
    sa.Column('route_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=24), nullable=False),
    sa.Column('priority', sa.String(length=16), nullable=False),
    sa.Column('weight_kg', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('pieces', sa.Integer(), nullable=False),
    sa.Column('current_location', sa.String(length=160), nullable=True),
    sa.Column('shipped_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('eta', sa.DateTime(timezone=True), nullable=False),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(status = 'delivered') = (delivered_at IS NOT NULL)", name=op.f('ck_shipments_delivered_at_matches_status')),
    sa.CheckConstraint("priority IN ('standard', 'express', 'critical')", name=op.f('ck_shipments_priority_valid')),
    sa.CheckConstraint("status IN ('pending', 'picked_up', 'in_transit', 'out_for_delivery', 'delayed', 'delivered', 'cancelled')", name=op.f('ck_shipments_status_valid')),
    sa.CheckConstraint("tracking_id ~ '^[A-Z0-9-]{6,32}$'", name=op.f('ck_shipments_tracking_id_format')),
    sa.CheckConstraint('eta > shipped_at', name=op.f('ck_shipments_eta_after_shipped')),
    sa.CheckConstraint('pieces >= 1', name=op.f('ck_shipments_pieces_positive')),
    sa.CheckConstraint('weight_kg > 0', name=op.f('ck_shipments_weight_positive')),
    sa.ForeignKeyConstraint(['carrier_id'], ['carriers.id'], name=op.f('fk_shipments_carrier_id_carriers'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['route_id'], ['routes.id'], name=op.f('fk_shipments_route_id_routes'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_shipments')),
    sa.UniqueConstraint('tracking_id', name=op.f('uq_shipments_tracking_id'))
    )
    op.create_index(op.f('ix_shipments_carrier_id'), 'shipments', ['carrier_id'], unique=False)
    op.create_index('ix_shipments_created_at', 'shipments', ['created_at'], unique=False)
    op.create_index('ix_shipments_customer_name', 'shipments', ['customer_name'], unique=False)
    op.create_index(op.f('ix_shipments_eta'), 'shipments', ['eta'], unique=False)
    op.create_index(op.f('ix_shipments_route_id'), 'shipments', ['route_id'], unique=False)
    op.create_index('ix_shipments_status_eta', 'shipments', ['status', 'eta'], unique=False)
    op.create_table('alerts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('shipment_id', sa.Integer(), nullable=False),
    sa.Column('alert_type', sa.String(length=32), nullable=False),
    sa.Column('severity', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='active', nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('dedupe_key', sa.String(length=128), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolution_note', sa.Text(), nullable=True),
    sa.Column('resolved_by', sa.String(length=64), nullable=True),
    sa.CheckConstraint("(status = 'resolved') = (resolved_at IS NOT NULL)", name=op.f('ck_alerts_resolved_at_matches_status')),
    sa.CheckConstraint("alert_type IN ('overdue')", name=op.f('ck_alerts_alert_type_valid')),
    sa.CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name=op.f('ck_alerts_severity_valid')),
    sa.CheckConstraint("status IN ('active', 'resolved')", name=op.f('ck_alerts_status_valid')),
    sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], name=op.f('fk_alerts_shipment_id_shipments'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_alerts')),
    sa.UniqueConstraint('dedupe_key', name=op.f('uq_alerts_dedupe_key'))
    )
    op.create_index('ix_alerts_shipment_id', 'alerts', ['shipment_id'], unique=False)
    op.create_index('ix_alerts_status_severity', 'alerts', ['status', 'severity'], unique=False)
    op.create_index('uq_alerts_one_active_per_type', 'alerts', ['shipment_id', 'alert_type'], unique=True, postgresql_where=sa.text("status = 'active'"))
    op.create_table('shipment_status_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('shipment_id', sa.Integer(), nullable=False),
    sa.Column('from_status', sa.String(length=24), nullable=True),
    sa.Column('to_status', sa.String(length=24), nullable=False),
    sa.Column('location', sa.String(length=160), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('changed_by', sa.String(length=64), server_default='user', nullable=False),
    sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("from_status IS NULL OR from_status IN ('pending', 'picked_up', 'in_transit', 'out_for_delivery', 'delayed', 'delivered', 'cancelled')", name=op.f('ck_shipment_status_history_from_status_valid')),
    sa.CheckConstraint("to_status IN ('pending', 'picked_up', 'in_transit', 'out_for_delivery', 'delayed', 'delivered', 'cancelled')", name=op.f('ck_shipment_status_history_to_status_valid')),
    sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], name=op.f('fk_shipment_status_history_shipment_id_shipments'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_shipment_status_history'))
    )
    op.create_index('ix_status_history_shipment_changed', 'shipment_status_history', ['shipment_id', 'changed_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_status_history_shipment_changed', table_name='shipment_status_history')
    op.drop_table('shipment_status_history')
    op.drop_index('uq_alerts_one_active_per_type', table_name='alerts', postgresql_where=sa.text("status = 'active'"))
    op.drop_index('ix_alerts_status_severity', table_name='alerts')
    op.drop_index('ix_alerts_shipment_id', table_name='alerts')
    op.drop_table('alerts')
    op.drop_index('ix_shipments_status_eta', table_name='shipments')
    op.drop_index(op.f('ix_shipments_route_id'), table_name='shipments')
    op.drop_index(op.f('ix_shipments_eta'), table_name='shipments')
    op.drop_index('ix_shipments_customer_name', table_name='shipments')
    op.drop_index('ix_shipments_created_at', table_name='shipments')
    op.drop_index(op.f('ix_shipments_carrier_id'), table_name='shipments')
    op.drop_table('shipments')
    op.drop_index('ix_routes_origin_destination', table_name='routes')
    op.drop_table('routes')
    op.drop_table('carriers')
