from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Unicode,
    func,
)
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from ....core.interface import Interface
from ..qc import QcStatus


class PalletBase(Interface, root=True):
    """Interface for the `pallets` table: one row per physical, reusable
    pallet. The goods on it (one sku, one lot) come and go; an empty pallet
    has no sku/lot/qty. Stock on hand is the sum of `qty` over pallets.
    Factories add position columns (e.g. level/slot).

    Every change in position or load must also call
    `record_event(session, PalletEvent.<X>, ...)` in the same transaction;
    `event_log` is the pallet's history, including every load it carried.
    QC status changes go through `qc.set_qc_status`.
    """

    __tablename__ = "pallets"

    # sort_order: mixin columns are otherwise placed after the factory's.
    # Code printed on the pallet's QR / LPN label; stays with the pallet for life.
    code: Mapped[str] = mapped_column(String(50), primary_key=True, sort_order=-8)
    # Current load. All three NULL = empty pallet.
    sku: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("products.sku"), nullable=True, sort_order=-7
    )
    lot_no: Mapped[str | None] = mapped_column(String(50), nullable=True, sort_order=-6)
    qty: Mapped[int | None] = mapped_column(Integer, nullable=True, sort_order=-5)
    # Lab result for the current load; NULL only on an empty pallet. No server
    # default: an empty pallet must stay NULL, so loading sets WAITING.
    qc_status: Mapped[QcStatus | None] = mapped_column(
        Enum(
            QcStatus,
            name="qc_status",
            native_enum=False,
            create_constraint=True,
            length=10,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
        sort_order=-4,
    )
    # Why the lab locked the pallet; set only while locked. Past reasons are
    # in the pallet.qc_locked events.
    qc_lock_reason: Mapped[str | None] = mapped_column(
        Unicode(200), nullable=True, sort_order=-3
    )
    # NULL = not in a storage location (e.g. at the dock, outside the warehouse,
    # or empty: empty pallets are never stored in a location).
    location_code: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("locations.code"), nullable=True, sort_order=-2
    )
    # Set while the pallet is outside the warehouse (e.g. delivering goods);
    # cleared when it comes back.
    left_at: Mapped[datetime | None] = mapped_column(DATETIME2, nullable=True, sort_order=-1)
    # Retired for good (broken, lost); its history stays in event_log.
    deleted_at: Mapped[datetime | None] = mapped_column(DATETIME2, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2, nullable=False, server_default=func.sysutcdatetime()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME2,
        nullable=False,
        server_default=func.sysutcdatetime(),
        onupdate=func.sysutcdatetime(),
    )

    base_table_args = (
        CheckConstraint(
            "(sku IS NULL AND lot_no IS NULL AND qty IS NULL)"
            # qty IS NOT NULL is needed: with qty NULL, "qty > 0" is UNKNOWN
            # and a CHECK lets UNKNOWN pass.
            " OR (sku IS NOT NULL AND lot_no IS NOT NULL AND qty IS NOT NULL AND qty > 0)",
            name="load_complete",
        ),
        CheckConstraint(
            "(sku IS NULL AND qc_status IS NULL) OR (sku IS NOT NULL AND qc_status IS NOT NULL)",
            name="qc_status_when_loaded",
        ),
        # <> '' also rejects blanks (MSSQL ignores trailing spaces).
        CheckConstraint(
            "(qc_status IS NOT NULL AND qc_status = 'locked'"
            " AND qc_lock_reason IS NOT NULL AND qc_lock_reason <> '')"
            " OR ((qc_status IS NULL OR qc_status <> 'locked') AND qc_lock_reason IS NULL)",
            name="qc_lock_reason_when_locked",
        ),
        CheckConstraint("left_at IS NULL OR location_code IS NULL", name="left_has_no_location"),
        CheckConstraint("location_code IS NULL OR sku IS NOT NULL", name="stored_pallet_has_load"),
        CheckConstraint(
            "deleted_at IS NULL OR (sku IS NULL AND location_code IS NULL)",
            name="deleted_pallet_empty",
        ),
        # "What is at this location" is the main stock query.
        Index(None, "location_code"),
        # Stock per product and lot tracing (recalls); also backs the sku FK.
        Index(None, "sku", "lot_no"),
    )
