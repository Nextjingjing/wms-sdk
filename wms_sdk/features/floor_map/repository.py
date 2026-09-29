from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...modules.events.capture import record_event
from ...modules.inventory.models import PalletBase
from ...modules.storage.models import Location, LocationPropertiesBase, Zone
from .builder import ColumnLayout, RowPlan, plan_rows
from .models import LocationMap


class LocationInUse(Exception):
    """A location still holding pallets cannot be retired."""


def save_column(
    session: Session,
    *,
    plant_code: str,
    warehouse_code: str,
    zone_code: str,
    layout: ColumnLayout,
    code_of: Callable[[int], str],
    label_gap: Decimal = Decimal(0),
    properties_of: Callable[[RowPlan, str], LocationPropertiesBase] | None = None,
    previous_codes: Sequence[str] = (),
) -> list[str]:
    """Create or update the locations of one column and their drawings.

    - `code_of(row_no)` gives each row's location code (factory format)
    - `properties_of(row, code)` builds the factory's location_properties
      row, if the factory stores addressing / capacity there
    - `previous_codes` are the column's codes before this edit; those no
      longer in the layout are retired (raises LocationInUse if any still
      holds a pallet, and then nothing is saved)

    The zone is created if missing and restored if retired. Returns the
    column's location codes, row 1 first. Needs an operation started.
    """
    plans = plan_rows(layout)
    codes = [code_of(plan.row_no) for plan in plans]
    if len(set(codes)) != len(codes):
        raise ValueError(f"code_of gave duplicate codes: {codes}")
    removed = [code for code in previous_codes if code not in codes]
    _ensure_empty(session, removed)

    _ensure_zone(session, plant_code, warehouse_code, zone_code)
    for code in codes:
        location = session.get(Location, code)
        if location is None:
            session.add(
                Location(
                    code=code,
                    plant_code=plant_code,
                    warehouse_code=warehouse_code,
                    zone_code=zone_code,
                )
            )
            continue
        if (location.plant_code, location.warehouse_code) != (plant_code, warehouse_code):
            raise ValueError(f"location {code} belongs to another warehouse")
        location.zone_code = zone_code
        location.deleted_at = None
    session.flush()  # locations before the rows that FK them

    for plan, code in zip(plans, codes):
        session.merge(
            LocationMap(
                location_code=code,
                x=plan.box.x,
                y=plan.box.y,
                width=plan.box.width,
                height=plan.box.height,
                row_direction=layout.direction,
                row_gap=layout.row_gap,
                level_gap=layout.level_gap,
                label_gap=label_gap,
            )
        )
        if properties_of is not None:
            session.merge(properties_of(plan, code))

    retire_locations(session, removed)
    record_event(
        session,
        "location_map.column_saved",
        {
            "plant_code": plant_code,
            "warehouse_code": warehouse_code,
            "zone_code": zone_code,
            "locations": codes,
            "retired": removed,
        },
    )
    return codes


def retire_locations(session: Session, codes: Sequence[str]) -> None:
    """Soft-delete locations (e.g. a deleted column). Raises LocationInUse,
    changing nothing, if any of them still holds a pallet.
    """
    _ensure_empty(session, codes)
    now = datetime.now(UTC).replace(tzinfo=None)
    for code in codes:
        location = session.get(Location, code)
        if location is not None and location.deleted_at is None:
            location.deleted_at = now


def _ensure_empty(session: Session, codes: Sequence[str]) -> None:
    if not codes:
        return
    pallet = PalletBase.implementation()
    occupied = session.scalars(
        select(pallet.location_code).where(pallet.location_code.in_(codes)).distinct()
    ).all()
    if occupied:
        raise LocationInUse(f"locations still hold pallets: {sorted(occupied)}")


def _ensure_zone(session: Session, plant_code: str, warehouse_code: str, zone_code: str) -> None:
    zone = session.get(Zone, (plant_code, warehouse_code, zone_code))
    if zone is None:
        session.add(Zone(plant_code=plant_code, warehouse_code=warehouse_code, code=zone_code))
    elif zone.deleted_at is not None:
        zone.deleted_at = None
    session.flush()
