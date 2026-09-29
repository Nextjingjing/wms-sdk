from sqlalchemy.orm import Session

from ...core.interface import get_row
from .models import ProductPropertiesBase


def get_product_properties(session: Session, sku: str) -> ProductPropertiesBase:
    return get_row(session, ProductPropertiesBase, sku)
