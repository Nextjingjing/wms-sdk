"""Reference factory's map editor actions on top of the SDK's floor_map
builder: location codes in the "mapid" format, and location properties
(column / row / capacity / pallet length) written with every row.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from wms_sdk.features.floor_map.builder import ColumnLayout
from wms_sdk.features.floor_map.repository import retire_locations
from wms_sdk.features.floor_map.repository import save_column as save_column_rows
from wms_sdk.modules.storage.models import Location
from wms_sdk.shared.models.plant import Plant

from .models import LocationProperties


def mapid(plant_name: str, warehouse_code: str, zone_code: str, column_no: int, row_no: int) -> str:
    """e.g. 'tl-w3-1-0102'. Numbers are padded to two digits, never cut."""
    return f"{plant_name.lower()}-{warehouse_code.lower()}-{zone_code}-{column_no:02}{row_no:02}"


def column_codes(session: Session, plant_code: str, warehouse_code: str, column_no: int) -> list[str]:
    return list(
        session.scalars(
            select(LocationProperties.location_code).where(
                LocationProperties.plant_code == plant_code,
                LocationProperties.warehouse_code == warehouse_code,
                LocationProperties.column_no == column_no,
            )
        )
    )


def save_column(
    session: Session,
    *,
    plant_code: str,
    warehouse_code: str,
    zone_code: str,
    column_no: int,
    layout: ColumnLayout,
    pallet_length_cm: int,
    label_gap: Decimal = Decimal(0),
) -> list[str]:
    """Add a column, or edit it (fewer rows retire the extra locations).
    Moving a column to another zone changes its codes: delete it first.
    """
    previous = column_codes(session, plant_code, warehouse_code, column_no)
    zones = {session.get(Location, code).zone_code for code in previous}
    if zones - {zone_code}:
        raise ValueError(
            f"column {column_no} is in zone {sorted(zones)}; delete it before adding it to zone {zone_code}"
        )
    plant_name = session.get(Plant, plant_code).name
    return save_column_rows(
        session,
        plant_code=plant_code,
        warehouse_code=warehouse_code,
        zone_code=zone_code,
        layout=layout,
        code_of=lambda row_no: mapid(plant_name, warehouse_code, zone_code, column_no, row_no),
        label_gap=label_gap,
        properties_of=lambda row, code: LocationProperties(
            location_code=code,
            plant_code=plant_code,
            warehouse_code=warehouse_code,
            column_no=column_no,
            row_no=row.row_no,
            max_level=layout.max_level,
            sub_column=layout.sub_column,
            pallet_length_cm=pallet_length_cm,
        ),
        previous_codes=previous,
    )


def delete_column(session: Session, plant_code: str, warehouse_code: str, column_no: int) -> None:
    """Retire every location of a column; refused while any holds a pallet.
    Their properties are removed, freeing (column, row) for a new column.
    """
    codes = column_codes(session, plant_code, warehouse_code, column_no)
    retire_locations(session, codes)
    # Row by row through the ORM, so event_log captures each deletion.
    for code in codes:
        session.delete(session.get(LocationProperties, code))
