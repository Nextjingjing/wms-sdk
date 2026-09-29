from datetime import datetime

from sqlalchemy import Boolean, ForeignKeyConstraint, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from ....core.db import Base


class Location(Base):
    """A place where goods are stored. Addressing and capacity differ per
    factory, so they live in `location_properties`.
    """

    __tablename__ = "locations"

    # The code people use for the place, e.g. 'tl-w3-1-0102'. Stock tables FK here.
    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    plant_code: Mapped[str] = mapped_column(String(10), nullable=False)
    warehouse_code: Mapped[str] = mapped_column(String(20), nullable=False)
    zone_code: Mapped[str] = mapped_column(String(20), nullable=False)
    # False = temporarily closed: still exists, but nothing may be put here.
    # Different from deleted_at, which retires the location for good.
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
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

    __table_args__ = (
        ForeignKeyConstraint(
            ["plant_code", "warehouse_code", "zone_code"],
            ["zones.plant_code", "zones.warehouse_code", "zones.code"],
        ),
        # MSSQL does not index FK columns; "locations in this zone" is a common query.
        Index(None, "plant_code", "warehouse_code", "zone_code"),
        # Redundant with the PK on its own, but lets a factory's properties table
        # FK (location_code, plant_code, warehouse_code) and then enforce
        # uniqueness per warehouse (e.g. no two locations at the same column/row).
        UniqueConstraint("code", "plant_code", "warehouse_code"),
    )
