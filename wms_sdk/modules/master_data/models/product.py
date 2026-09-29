from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, Unicode, func
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from ....core.db import Base
from ....core.interface import Interface


class Product(Base):
    """Product identity only. Properties live in `product_properties`; a
    missing row means "not set" and must raise, never fall back to a default.
    """

    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(50), primary_key=True)
    name_thai: Mapped[str] = mapped_column(Unicode(200), nullable=False)
    name_eng: Mapped[str] = mapped_column(String(200), nullable=False)
    name_short: Mapped[str | None] = mapped_column(Unicode(100), nullable=True)
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


class ProductPropertiesBase(Interface, root=True):
    """Interface for the `product_properties` table: one optional row per sku.
    A missing row means "not set". The SDK fixes the properties every factory
    has (`pcs_per_pallet`, `kg_per_pcs`); the factory adds the rest.

    NOT NULL columns are required once the row exists. Nullable columns are
    genuinely optional (NULL = does not apply), not "unknown".
    """

    __tablename__ = "product_properties"

    # sort_order=-1: mixin columns are otherwise placed after the factory's.
    sku: Mapped[str] = mapped_column(
        String(50), ForeignKey("products.sku"), primary_key=True, sort_order=-3
    )
    pcs_per_pallet: Mapped[int] = mapped_column(Integer, nullable=False, sort_order=-2)
    kg_per_pcs: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, sort_order=-1)
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
        CheckConstraint("pcs_per_pallet > 0", name="pcs_per_pallet_positive"),
        CheckConstraint("kg_per_pcs > 0", name="kg_per_pcs_positive"),
    )
