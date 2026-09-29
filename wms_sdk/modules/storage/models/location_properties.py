from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from ....core.interface import Interface


class LocationPropertiesBase(Interface, root=True):
    """Interface for the `location_properties` table: one optional row per
    location, columns defined by the factory (addressing, capacity). A
    missing row means "not set".
    """

    __tablename__ = "location_properties"

    # sort_order=-1: mixin columns are otherwise placed after the factory's.
    location_code: Mapped[str] = mapped_column(
        String(50), ForeignKey("locations.code"), primary_key=True, sort_order=-1
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2, nullable=False, server_default=func.sysutcdatetime()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME2,
        nullable=False,
        server_default=func.sysutcdatetime(),
        onupdate=func.sysutcdatetime(),
    )
