from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    ShipmentPriority,
    ShipmentStatus,
    TransportMode,
    sql_in,
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Carrier(TimestampMixin, Base):
    __tablename__ = "carriers"
    __table_args__ = (
        CheckConstraint("char_length(trim(name)) >= 2", name="name_not_blank"),
        CheckConstraint("code ~ '^[A-Z0-9]{2,10}$'", name="code_format"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    website: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    shipments: Mapped[list[Shipment]] = relationship(back_populates="carrier")


class Route(TimestampMixin, Base):
    __tablename__ = "routes"
    __table_args__ = (
        UniqueConstraint(
            "origin_city",
            "origin_country",
            "destination_city",
            "destination_country",
            "mode",
            name="uq_routes_lane_mode",
        ),
        CheckConstraint("code ~ '^[A-Z0-9-]{3,20}$'", name="code_format"),
        CheckConstraint(f"mode IN ({sql_in(TransportMode)})", name="mode_valid"),
        CheckConstraint("distance_km > 0", name="distance_positive"),
        CheckConstraint(
            "estimated_transit_days > 0 AND estimated_transit_days <= 120",
            name="transit_days_range",
        ),
        CheckConstraint(
            "NOT (lower(origin_city) = lower(destination_city) "
            "AND upper(origin_country) = upper(destination_country))",
            name="origin_ne_destination",
        ),
        Index("ix_routes_origin_destination", "origin_city", "destination_city"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    origin_city: Mapped[str] = mapped_column(String(100), nullable=False)
    origin_country: Mapped[str] = mapped_column(String(2), nullable=False)
    destination_city: Mapped[str] = mapped_column(String(100), nullable=False)
    destination_country: Mapped[str] = mapped_column(String(2), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    distance_km: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_transit_days: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    shipments: Mapped[list[Shipment]] = relationship(back_populates="route")

    @property
    def label(self) -> str:
        return f"{self.origin_city} → {self.destination_city}"


class Shipment(TimestampMixin, Base):
    __tablename__ = "shipments"
    __table_args__ = (
        CheckConstraint(f"status IN ({sql_in(ShipmentStatus)})", name="status_valid"),
        CheckConstraint(f"priority IN ({sql_in(ShipmentPriority)})", name="priority_valid"),
        CheckConstraint("weight_kg > 0", name="weight_positive"),
        CheckConstraint("pieces >= 1", name="pieces_positive"),
        CheckConstraint("eta > shipped_at", name="eta_after_shipped"),
        CheckConstraint(
            "(status = 'delivered') = (delivered_at IS NOT NULL)",
            name="delivered_at_matches_status",
        ),
        CheckConstraint("tracking_id ~ '^[A-Z0-9-]{6,32}$'", name="tracking_id_format"),
        Index("ix_shipments_status_eta", "status", "eta"),
        Index("ix_shipments_created_at", "created_at"),
        Index("ix_shipments_customer_name", "customer_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracking_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(64))
    customer_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    carrier_id: Mapped[int] = mapped_column(
        ForeignKey("carriers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=ShipmentStatus.PENDING.value
    )
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ShipmentPriority.STANDARD.value
    )
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    pieces: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_location: Mapped[str | None] = mapped_column(String(160))
    shipped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    eta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    carrier: Mapped[Carrier] = relationship(back_populates="shipments")
    route: Mapped[Route] = relationship(back_populates="shipments")
    status_history: Mapped[list[ShipmentStatusHistory]] = relationship(
        back_populates="shipment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ShipmentStatusHistory.changed_at.desc(), ShipmentStatusHistory.id.desc()",
    )
    alerts: Mapped[list[Alert]] = relationship(
        back_populates="shipment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Alert.created_at.desc()",
    )


class ShipmentStatusHistory(Base):
    __tablename__ = "shipment_status_history"
    __table_args__ = (
        CheckConstraint(f"to_status IN ({sql_in(ShipmentStatus)})", name="to_status_valid"),
        CheckConstraint(
            f"from_status IS NULL OR from_status IN ({sql_in(ShipmentStatus)})",
            name="from_status_valid",
        ),
        Index("ix_status_history_shipment_changed", "shipment_id", "changed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shipment_id: Mapped[int] = mapped_column(
        ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)
    location: Mapped[str | None] = mapped_column(String(160))
    note: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[str] = mapped_column(
        String(64), nullable=False, default="user", server_default="user"
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    shipment: Mapped[Shipment] = relationship(back_populates="status_history")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(f"alert_type IN ({sql_in(AlertType)})", name="alert_type_valid"),
        CheckConstraint(f"severity IN ({sql_in(AlertSeverity)})", name="severity_valid"),
        CheckConstraint(f"status IN ({sql_in(AlertStatus)})", name="status_valid"),
        CheckConstraint(
            "(status = 'resolved') = (resolved_at IS NOT NULL)",
            name="resolved_at_matches_status",
        ),
        # Never more than one *active* alert of a given type per shipment.
        Index(
            "uq_alerts_one_active_per_type",
            "shipment_id",
            "alert_type",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_alerts_status_severity", "status", "severity"),
        Index("ix_alerts_shipment_id", "shipment_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shipment_id: Mapped[int] = mapped_column(
        ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False
    )
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AlertStatus.ACTIVE.value, server_default="active"
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # Deterministic key (type + shipment + ETA) so the same overdue condition can
    # only ever raise one alert, even after manual resolution.
    dedupe_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[str | None] = mapped_column(String(64))

    shipment: Mapped[Shipment] = relationship(back_populates="alerts")
