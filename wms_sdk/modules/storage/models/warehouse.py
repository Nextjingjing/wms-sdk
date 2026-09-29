from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from ....core.db import Base


class Warehouse(Base):
    """A storage building or area within a plant. Codes are unique per plant,
    not globally (two plants may both have a W3).
    """

    __tablename__ = "warehouses"

    plant_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("plants.code"), primary_key=True
    )
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
