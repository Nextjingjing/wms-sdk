from decimal import Decimal

import pytest
from sqlalchemy import select

from examples.reference_factory.maps import delete_column, mapid, save_column
from examples.reference_factory.models import LocationProperties, Pallet
from wms_sdk.features.floor_map.builder import (
    ColumnLayout,
    Box,
    cells,
    plan_rows,
    row_size,
    snap,
)
from wms_sdk.features.floor_map.models import LocationMap, RowDirection
from wms_sdk.features.floor_map.repository import LocationInUse
from wms_sdk.modules.events.capture import start_operation
from wms_sdk.modules.events.models import EventLog
from wms_sdk.modules.master_data.models import Product
from wms_sdk.modules.storage.models import Location, Warehouse, Zone
from wms_sdk.shared.models.plant import Plant

D = Decimal


def layout(direction=RowDirection.DOWN, rows=3, **fields):
    base = dict(
        origin_x=D(100), origin_y=D(200), direction=direction, rows=rows,
        max_level=3, sub_column=2, cell_width=D(10), cell_height=D(8),
        level_gap=D(1), row_gap=D(5),
    )  # fmt: skip
    return ColumnLayout(**{**base, **fields})


# ---------- pure layout ----------


def test_row_size_includes_gaps_between_positions():
    assert row_size(layout()) == (D(21), D(26))  # 2*10+1, 3*8+2*1


@pytest.mark.parametrize(
    "direction, second_row",
    [
        (RowDirection.DOWN, (D(100), D(231))),  # 200 + 26 + 5
        (RowDirection.UP, (D(100), D(169))),
        (RowDirection.RIGHT, (D(126), D(200))),  # 100 + 21 + 5
        (RowDirection.LEFT, (D(74), D(200))),
    ],
)
def test_rows_follow_the_direction(direction, second_row):
    rows = plan_rows(layout(direction))
    assert [r.row_no for r in rows] == [1, 2, 3]
    assert (rows[0].box.x, rows[0].box.y) == (D(100), D(200))
    assert (rows[1].box.x, rows[1].box.y) == second_row


def test_level_one_is_at_the_bottom_when_rows_go_up():
    spec = layout(RowDirection.UP)
    by_position = {(c.level, c.slot): c.box for c in cells(spec, plan_rows(spec)[0])}
    assert by_position[(1, 1)] == Box(D(100), D(218), D(10), D(8))  # bottom row of the box
    assert by_position[(3, 1)].y == D(200)


def test_slot_one_is_on_the_right_when_rows_go_left():
    spec = layout(RowDirection.LEFT)
    by_position = {(c.level, c.slot): c.box for c in cells(spec, plan_rows(spec)[0])}
    assert by_position[(1, 1)].x == D(111)
    assert by_position[(1, 2)].x == D(100)


def test_invalid_layout_is_refused():
    with pytest.raises(ValueError):
        layout(rows=0)
    with pytest.raises(ValueError):
        layout(cell_width=D(0))


def test_snap_pulls_each_axis_to_the_nearest_neighbour():
    snapped = snap(D(103), D(50), [(D(100), D(10)), (D(104), D(90)), (D(300), D(52))], D(5))
    assert (snapped.x, snapped.y) == (D(104), D(52))
    far = snap(D(0), D(0), [(D(100), D(100))], D(5))
    assert (far.x, far.y, far.guide_x, far.guide_y) == (D(0), D(0), None, None)


# ---------- saving columns (reference factory example) ----------


@pytest.fixture
def warehouse(session):
    start_operation(session, actor=None)
    for row in [
        Plant(code="C221", name="TL"),
        Warehouse(plant_code="C221", code="W3"),
        Product(sku="A001", name_thai="ปูน", name_eng="Cement"),
    ]:
        session.add(row)
        session.flush()
    session.commit()
    return session


def save(session, rows=3, zone="1", column_no=2):
    start_operation(session, actor=None)
    codes = save_column(
        session, plant_code="C221", warehouse_code="W3", zone_code=zone,
        column_no=column_no, layout=layout(rows=rows), pallet_length_cm=120,
    )  # fmt: skip
    session.commit()
    return codes


def test_save_column_creates_zone_locations_drawings_and_properties(warehouse):
    codes = save(warehouse)

    assert codes == ["tl-w3-1-0201", "tl-w3-1-0202", "tl-w3-1-0203"]
    assert warehouse.get(Zone, ("C221", "W3", "1")) is not None
    drawing = warehouse.get(LocationMap, "tl-w3-1-0202")
    assert (drawing.y, drawing.height, drawing.row_direction) == (D(231), D(26), RowDirection.DOWN)
    props = warehouse.get(LocationProperties, "tl-w3-1-0203")
    assert (props.column_no, props.row_no, props.max_level, props.sub_column) == (2, 3, 3, 2)
    assert "location_map.column_saved" in warehouse.scalars(select(EventLog.event_type)).all()


def test_fewer_rows_retire_the_extra_locations(warehouse):
    save(warehouse, rows=3)
    save(warehouse, rows=1)

    assert warehouse.get(Location, "tl-w3-1-0201").deleted_at is None
    assert warehouse.get(Location, "tl-w3-1-0203").deleted_at is not None

    save(warehouse, rows=3)  # growing again restores them
    assert warehouse.get(Location, "tl-w3-1-0203").deleted_at is None


def test_location_holding_a_pallet_cannot_be_retired(warehouse):
    save(warehouse, rows=3)
    start_operation(warehouse, actor=None)
    warehouse.add(
        Pallet(code="P1", sku="A001", lot_no="L1", qty=1, qc_status="waiting",
               location_code="tl-w3-1-0203", level_no=1, slot_no=1)
    )  # fmt: skip
    warehouse.commit()

    with pytest.raises(LocationInUse):
        save(warehouse, rows=1)
    warehouse.rollback()
    assert warehouse.get(Location, "tl-w3-1-0203").deleted_at is None


def test_moving_a_column_to_another_zone_needs_delete_first(warehouse):
    save(warehouse, zone="1")
    with pytest.raises(ValueError, match="delete it"):
        save(warehouse, zone="2")
    warehouse.rollback()

    start_operation(warehouse, actor=None)
    delete_column(warehouse, "C221", "W3", 2)
    warehouse.commit()
    assert warehouse.get(Location, "tl-w3-1-0201").deleted_at is not None

    assert save(warehouse, zone="2") == [mapid("TL", "W3", "2", 2, n) for n in (1, 2, 3)]
