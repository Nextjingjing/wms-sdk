from datetime import datetime

from sqlalchemy import ForeignKeyConstraint, String, func
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from ....core.db import Base


class Zone(Base):
    """An area within a warehouse. Flat: zones do not nest."""

    __tablename__ = "zones"

    plant_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    warehouse_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
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
            ["plant_code", "warehouse_code"],
            ["warehouses.plant_code", "warehouses.code"],
        ),
    )
