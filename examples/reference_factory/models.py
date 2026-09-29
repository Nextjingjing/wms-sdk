"""Reference factory's implementation of the SDK interfaces, its enabled
optional features, and its own lookups.
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Unicode,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

import wms_sdk.features.floor_map.models  # noqa: F401  (enables floor maps)
import wms_sdk.features.machines  # noqa: F401  (enables the machines feature)
import wms_sdk.features.routing.models  # noqa: F401  (enables forklift routing)
from wms_sdk.core.db import Base, Lookup
from wms_sdk.features.brand import HasBrand
from wms_sdk.features.tasks.models import TaskBase
from wms_sdk.modules.inventory.models import PalletBase
from wms_sdk.modules.master_data.models import ProductPropertiesBase
from wms_sdk.modules.storage.models import LocationPropertiesBase, ZonePropertiesBase


class TicketFormat(Lookup, Base):
    __tablename__ = "ticket_formats"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False)


class TrafficFlow(Lookup, Base):
    """How forklifts may move through a zone (one-way / two-way)."""

    __tablename__ = "traffic_flows"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False)


class PalletFill(Lookup, Base):
    """Whether a zone holds full pallets or partial (fraction) pallets."""

    __tablename__ = "pallet_fills"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False)


class AbcClass(Lookup, Base):
    """ABC classification: A = fastest-moving goods."""

    __tablename__ = "abc_classes"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False)


class ProductProperties(ProductPropertiesBase, HasBrand, Base):
    pcs_per_box: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size: Mapped[str] = mapped_column(Unicode(100), nullable=False)
    size_mm: Mapped[str] = mapped_column(String(50), nullable=False)
    length_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tis: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ticket_format_code: Mapped[str] = mapped_column(
        String(30), ForeignKey("ticket_formats.code"), nullable=False
    )
    ticket_thai: Mapped[str | None] = mapped_column(Unicode(150), nullable=True)
    ticket_eng: Mapped[str | None] = mapped_column(String(150), nullable=True)
    customer_sku: Mapped[str | None] = mapped_column(String(20), nullable=True)

    extra_table_args = (
        CheckConstraint("pcs_per_box IS NULL OR pcs_per_box > 0", name="pcs_per_box_positive"),
        CheckConstraint("length_cm IS NULL OR length_cm > 0", name="length_cm_positive"),
    )


class ZoneProperties(ZonePropertiesBase, Base):
    traffic_flow_code: Mapped[str] = mapped_column(
        String(30), ForeignKey("traffic_flows.code"), nullable=False
    )
    pallet_fill_code: Mapped[str] = mapped_column(
        String(30), ForeignKey("pallet_fills.code"), nullable=False
    )
    abc_class_code: Mapped[str] = mapped_column(
        String(30), ForeignKey("abc_classes.code"), nullable=False
    )


class LocationProperties(LocationPropertiesBase, Base):
    """Floor-stacked pallet lanes: a location is one row of a column."""

    # Copied from locations (the composite FK keeps them equal) so that
    # (warehouse, column, row) can be unique.
    plant_code: Mapped[str] = mapped_column(String(10), nullable=False)
    warehouse_code: Mapped[str] = mapped_column(String(20), nullable=False)
    column_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    row_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Pallets stacked on top of each other.
    max_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Pallets placed side by side.
    sub_column: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Length of pallet this location takes, e.g. 120 or 240. Entered in cm.
    pallet_length_cm: Mapped[int] = mapped_column(Integer, nullable=False)

    extra_table_args = (
        ForeignKeyConstraint(
            ["location_code", "plant_code", "warehouse_code"],
            ["locations.code", "locations.plant_code", "locations.warehouse_code"],
            # Named explicitly: the convention would reuse the base FK's name.
            name="fk_location_properties_location_warehouse",
        ),
        UniqueConstraint("plant_code", "warehouse_code", "column_no", "row_no"),
        CheckConstraint("column_no >= 1 AND row_no >= 1", name="address_positive"),
        CheckConstraint("max_level >= 1 AND sub_column >= 1", name="capacity_positive"),
        CheckConstraint("pallet_length_cm > 0", name="pallet_length_positive"),
    )


class Pallet(PalletBase, Base):
    """Pallets are stacked in floor lanes, so a pallet's position is its
    location plus level (height) and slot (side by side).
    """

    level_no: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    slot_no: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    extra_table_args = (
        CheckConstraint(
            "(level_no IS NULL AND slot_no IS NULL)"
            # Explicit IS NOT NULL: a CHECK lets UNKNOWN (e.g. "NULL >= 1") pass.
            " OR (level_no IS NOT NULL AND slot_no IS NOT NULL"
            " AND level_no >= 1 AND slot_no >= 1 AND location_code IS NOT NULL)",
            name="position_complete",
        ),
        # One pallet per position. Filtered: MSSQL treats NULLs as equal in a
        # unique index, so pallets without a location would collide.
        Index(
            "uq_pallets_position",
            "location_code",
            "level_no",
            "slot_no",
            unique=True,
            mssql_where=text("location_code IS NOT NULL"),
            sqlite_where=text("location_code IS NOT NULL"),
        ),
    )


class Task(TaskBase, Base):
    """Forklift, QC and dispatch work. Assigned to a role; whoever of that
    role takes it is recorded in the event log. Reserves the destination
    position (location + level + slot) while active.
    """

    active_statuses = ("open", "in_progress")
    reservation_columns = ("to_location_code", "to_level_no", "to_slot_no")
    transitions = {
        None: {"open"},
        "open": {"in_progress", "cancelled"},
        "in_progress": {"done", "cancelled"},
    }

    assigned_role_code: Mapped[str] = mapped_column(
        String(30), ForeignKey("roles.code"), nullable=False
    )
    pallet_code: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("pallets.code"), nullable=True
    )
    from_location_code: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("locations.code"), nullable=True
    )
    to_location_code: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("locations.code"), nullable=True
    )
    to_level_no: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    to_slot_no: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # External document, e.g. the sales order a dispatch task belongs to.
    reference: Mapped[str | None] = mapped_column(String(50), nullable=True)

    extra_table_args = (
        CheckConstraint(
            "(to_level_no IS NULL AND to_slot_no IS NULL)"
            " OR (to_level_no IS NOT NULL AND to_slot_no IS NOT NULL AND to_location_code IS NOT NULL)",
            name="to_position_complete",
        ),
        # Tasks of a pallet or a location, finished ones included (the
        # reservation index covers only active tasks).
        Index(None, "pallet_code"),
        Index(None, "from_location_code"),
        Index(None, "to_location_code"),
    )
