"""Optional feature: product brands. To enable, mix `HasBrand` into the
factory's product_properties implementation:

    class ProductProperties(ProductPropertiesBase, HasBrand, Base): ...

A factory that does not import this module gets no `brands` table.
"""

from sqlalchemy import ForeignKey, String, Unicode
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base, Lookup


class Brand(Lookup, Base):
    __tablename__ = "brands"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False)


class HasBrand:
    brand_code: Mapped[str] = mapped_column(String(30), ForeignKey("brands.code"), nullable=False)
