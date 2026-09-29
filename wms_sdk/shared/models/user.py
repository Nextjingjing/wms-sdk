from datetime import datetime

from sqlalchemy import ForeignKey, String, Unicode, func
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from ...core.db import Base


class User(Base):
    """A person who performs warehouse actions; tables FK here to record who
    did what. Login and passwords belong to the application, not here.
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(150), primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(Unicode(150), nullable=False)
    last_name: Mapped[str] = mapped_column(Unicode(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    # No default on purpose: every user must be given a role explicitly.
    role_code: Mapped[str] = mapped_column(String(30), ForeignKey("roles.code"), nullable=False)
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
