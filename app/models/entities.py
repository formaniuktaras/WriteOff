from datetime import date
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.enums import AssetState, EventItemKind, EventStatus, ValuationKind


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    role: Mapped[Role] = relationship()


class Unit(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "units"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))


class Service(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "services"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class Nomenclature(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "nomenclature"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_of_measure: Mapped[str | None] = mapped_column(String(50))


class DocumentType(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "document_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_extension: Mapped[str | None] = mapped_column(String(10))


class AssetObject(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "asset_objects"
    __table_args__ = (
        UniqueConstraint("inventory_number", name="uq_asset_inventory", postgresql_nulls_not_distinct=False),
        UniqueConstraint("vin", name="uq_asset_vin", postgresql_nulls_not_distinct=False),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nomenclature_id: Mapped[int] = mapped_column(ForeignKey("nomenclature.id"), nullable=False)
    inventory_number: Mapped[str | None] = mapped_column(String(120))
    serial_number: Mapped[str | None] = mapped_column(String(120))
    vin: Mapped[str | None] = mapped_column(String(120))
    plate_number: Mapped[str | None] = mapped_column(String(60))
    state: Mapped[AssetState | None] = mapped_column(Enum(AssetState, name="asset_state"))
    notes: Mapped[str | None] = mapped_column(Text)


class Event(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus, name="event_status"), default=EventStatus.DRAFT, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    short_description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    units: Mapped[list["EventUnit"]] = relationship(back_populates="event", cascade="all,delete-orphan")
    items: Mapped[list["EventItem"]] = relationship(back_populates="event", cascade="all,delete-orphan")


class EventUnit(Base, TimestampMixin):
    __tablename__ = "event_units"
    __table_args__ = (UniqueConstraint("event_id", "unit_id", name="uq_event_unit"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)

    event: Mapped[Event] = relationship(back_populates="units")
    unit: Mapped[Unit] = relationship()


class EventItem(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "event_items"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_event_item_qty_pos"),
        CheckConstraint(
            "(kind='object' AND asset_object_id IS NOT NULL AND nomenclature_id IS NULL AND qty = 1) OR "
            "(kind='group' AND asset_object_id IS NULL AND nomenclature_id IS NOT NULL AND qty > 0)",
            name="ck_event_item_kind_constraints",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=False)
    kind: Mapped[EventItemKind] = mapped_column(Enum(EventItemKind, name="event_item_kind"), nullable=False)
    asset_object_id: Mapped[int | None] = mapped_column(ForeignKey("asset_objects.id"))
    nomenclature_id: Mapped[int | None] = mapped_column(ForeignKey("nomenclature.id"))
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    event: Mapped[Event] = relationship(back_populates="items")


class Document(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    document_type_id: Mapped[int] = mapped_column(ForeignKey("document_types.id"), nullable=False)
    doc_no: Mapped[str] = mapped_column(String(120), nullable=False)
    doc_date: Mapped[date | None] = mapped_column(Date)
    reg_date: Mapped[date | None] = mapped_column(Date)
    title: Mapped[str | None] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    generated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class Valuation(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "valuations"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    valuation_kind: Mapped[ValuationKind] = mapped_column(Enum(ValuationKind, name="valuation_kind"), nullable=False)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    value_uah: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    date_effective: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class ValuationLink(Base, TimestampMixin):
    __tablename__ = "valuation_links"
    __table_args__ = (
        CheckConstraint("applies_qty > 0", name="ck_valuation_link_qty_pos"),
        UniqueConstraint("valuation_id", "event_item_id", name="uq_valuation_item"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    valuation_id: Mapped[int] = mapped_column(ForeignKey("valuations.id", ondelete="CASCADE"), nullable=False)
    event_item_id: Mapped[int] = mapped_column(ForeignKey("event_items.id", ondelete="CASCADE"), nullable=False)
    applies_qty: Mapped[int] = mapped_column(Integer, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    diff_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[date] = mapped_column(Date, nullable=False)
