from sqlalchemy import String, Unicode
from sqlalchemy.orm import Mapped, mapped_column

from ...core.db import Base, Lookup


class Role(Lookup, Base):
    """User roles; each factory seeds its own set (e.g. 'Forklift', 'Lab')."""

    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False)
