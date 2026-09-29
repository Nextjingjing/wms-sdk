"""Optional feature: production machines. Import this module to enable it;
a warehouse that produces nothing (e.g. a distribution centre) leaves it out
and gets none of these tables.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Index, String, Unicode, func
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base, Lookup


class MachineGroup(Lookup, Base):
    __tablename__ = "machine_groups"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False)


class Machine(Base):
    """Production machine. Codes are unique per plant, not globally."""

    __tablename__ = "machines"

    plant_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("plants.code"), primary_key=True
    )
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    machine_group_code: Mapped[str] = mapped_column(
        String(30), ForeignKey("machine_groups.code"), nullable=False
    )
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


class ProductSourceMachine(Base):
    """A machine that produces a product at a plant. Hard-deleted when the
    link ends.

    Both FKs share `plant_code`, so the database guarantees the product is
    produced at that plant and the machine belongs to that same plant.
    """

    __tablename__ = "product_source_machines"

    plant_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), primary_key=True)
    machine_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2, nullable=False, server_default=func.sysutcdatetime()
    )

    __table_args__ = (
        # Removing a product from a plant removes its source machines there.
        ForeignKeyConstraint(
            ["plant_code", "sku"],
            ["plant_products.plant_code", "plant_products.sku"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["plant_code", "machine_code"],
            ["machines.plant_code", "machines.code"],
        ),
        # "What does this machine make"; the PK has sku before machine_code.
        Index(None, "plant_code", "machine_code"),
    )
