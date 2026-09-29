from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from ....core.db import Base


class PlantProduct(Base):
    """A product that a plant produces. Stored explicitly (not inferred from
    machines) so a product is linked to a plant before any machine is chosen.
    Hard-deleted when the link ends.
    """

    __tablename__ = "plant_products"

    plant_code: Mapped[str] = mapped_column(String(10), ForeignKey("plants.code"), primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), ForeignKey("products.sku"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2, nullable=False, server_default=func.sysutcdatetime()
    )

    # "Which plants make this product"; the PK leads with plant_code.
    __table_args__ = (Index(None, "sku"),)
