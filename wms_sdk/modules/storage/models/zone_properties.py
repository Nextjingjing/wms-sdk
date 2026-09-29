from datetime import datetime

from sqlalchemy import ForeignKeyConstraint, String, func
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from ....core.interface import Interface


class ZonePropertiesBase(Interface, root=True):
    """Interface for the `zone_properties` table: one optional row per zone,
    columns defined by the factory (e.g. traffic flow, ABC class). A missing
    row means "not set".
    """

    __tablename__ = "zone_properties"

    # sort_order: mixin columns are otherwise placed after the factory's.
    plant_code: Mapped[str] = mapped_column(String(10), primary_key=True, sort_order=-3)
    warehouse_code: Mapped[str] = mapped_column(String(20), primary_key=True, sort_order=-2)
    zone_code: Mapped[str] = mapped_column(String(20), primary_key=True, sort_order=-1)
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
        ForeignKeyConstraint(
            ["plant_code", "warehouse_code", "zone_code"],
            ["zones.plant_code", "zones.warehouse_code", "zones.code"],
        ),
    )
