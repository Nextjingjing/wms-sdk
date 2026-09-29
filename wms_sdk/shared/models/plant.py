from datetime import datetime

from sqlalchemy import String, Unicode, func
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from ...core.db import Base


class Plant(Base):
    """Factory plant. Other tables reference it by `code`."""

    __tablename__ = "plants"

    # Plant code used by external systems (e.g. SAP plant code C221).
    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(50), unique=True, nullable=False)
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
