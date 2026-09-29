"""Database rules of the SDK and the reference factory example, checked by inserting rows."""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from examples.reference_factory.models import LocationProperties, Pallet
from wms_sdk.modules.events.capture import start_operation
from wms_sdk.modules.master_data.models import Product
from wms_sdk.modules.storage.models import Location, Warehouse, Zone
from wms_sdk.shared.models.plant import Plant

LOCATION = "tl-w3-1-0102"


@pytest.fixture
def warehouse(session):
    """Plant C221 / warehouse W3 / zones 1 and 2, two locations, product A001."""
    start_operation(session, actor=None)
    rows = [
        Plant(code="C221", name="TL"),
        Warehouse(plant_code="C221", code="W3"),
        Zone(plant_code="C221", warehouse_code="W3", code="1"),
        Zone(plant_code="C221", warehouse_code="W3", code="2"),
        Location(code=LOCATION, plant_code="C221", warehouse_code="W3", zone_code="1"),
        Location(code="tl-w3-2-0102", plant_code="C221", warehouse_code="W3", zone_code="2"),
        Product(sku="A001", name_thai="ปูน", name_eng="Cement"),
    ]
    # No ORM relationships, so insert order must follow the FKs by hand.
    for row in rows:
        session.add(row)
        session.flush()
    session.commit()
    return session


def assert_rejected(session, row):
    session.add(row)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def location_props(location_code, column_no, row_no):
    return LocationProperties(
        location_code=location_code,
        plant_code="C221",
        warehouse_code="W3",
        column_no=column_no,
        row_no=row_no,
        max_level=3,
        sub_column=2,
        pallet_length_cm=120,
    )


def test_same_column_and_row_in_one_warehouse_is_rejected(warehouse):
    start_operation(warehouse, actor=None)
    warehouse.add(location_props(LOCATION, 1, 2))
    warehouse.commit()

    start_operation(warehouse, actor=None)
    assert_rejected(warehouse, location_props("tl-w3-2-0102", 1, 2))


def pallet(code, **fields):
    load = {"sku": "A001", "lot_no": "L1", "qty": 10, "qc_status": "waiting"}
    return Pallet(code=code, **{**load, **fields})


def test_valid_pallets_are_accepted(warehouse):
    start_operation(warehouse, actor=None)
    warehouse.add(pallet("P1", location_code=LOCATION, level_no=1, slot_no=1))
    warehouse.add(pallet("P2"))  # loaded, not yet put away
    warehouse.add(Pallet(code="E1"))  # empty
    warehouse.add(Pallet(code="E2"))  # several empty pallets without location coexist
    warehouse.commit()


@pytest.mark.parametrize(
    "row",
    [
        pallet("X", qty=0),
        Pallet(code="X", sku="A001", lot_no="L1", qc_status="waiting"),  # load without qty
        Pallet(code="X", qty=5),  # qty without load
        Pallet(code="X", location_code=LOCATION, level_no=1, slot_no=2),  # empty pallet stored
        pallet("X", location_code=LOCATION, left_at=datetime(2026, 1, 1)),  # left but located
        pallet("X", deleted_at=datetime(2026, 1, 1)),  # retired with a load
        pallet("X", level_no=1, slot_no=1),  # position without location
        pallet("X", location_code=LOCATION, level_no=1),  # half a position
    ],
    ids=[
        "qty-zero",
        "load-without-qty",
        "qty-without-load",
        "empty-pallet-stored",
        "left-but-located",
        "retired-with-load",
        "position-without-location",
        "half-position",
    ],
)
def test_invalid_pallet_is_rejected(warehouse, row):
    start_operation(warehouse, actor=None)
    assert_rejected(warehouse, row)


def test_two_pallets_in_one_position_are_rejected(warehouse):
    start_operation(warehouse, actor=None)
    warehouse.add(pallet("P1", location_code=LOCATION, level_no=1, slot_no=1))
    warehouse.commit()

    start_operation(warehouse, actor=None)
    assert_rejected(warehouse, pallet("P2", location_code=LOCATION, level_no=1, slot_no=1))
