from sqlalchemy.orm import Session

from ...core.interface import get_row
from .models import LocationPropertiesBase, ZonePropertiesBase


def get_zone_properties(
    session: Session, plant_code: str, warehouse_code: str, zone_code: str
) -> ZonePropertiesBase:
    return get_row(session, ZonePropertiesBase, (plant_code, warehouse_code, zone_code))


def get_location_properties(session: Session, location_code: str) -> LocationPropertiesBase:
    return get_row(session, LocationPropertiesBase, location_code)
