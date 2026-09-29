"""Shared starting point for the cookbook recipes: an in-memory SQLite WMS for
the reference factory example with

- plant C221 (TL), warehouse W1, zone 1
- two columns of 3 rows each, drawn with the map builder:
  tl-w1-1-0101..0103 and tl-w1-1-0201..0203 (2 levels x 1 slot per row)
- users planner1 (Planner), forklift1 (Forklift), lab1 (Lab)
- products A001 and A002
"""

from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

import examples.reference_factory.seed as reference_factory
from examples.reference_factory.maps import save_column
from wms_sdk.checks import verify_factory
from wms_sdk.features.floor_map.builder import ColumnLayout
from wms_sdk.features.floor_map.models import RowDirection
from wms_sdk.metadata import metadata
from wms_sdk.modules.events.capture import install_capture, start_operation
from wms_sdk.modules.master_data.models import Product
from wms_sdk.modules.storage.models import Warehouse
from wms_sdk.shared.models.plant import Plant
from wms_sdk.shared.models.user import User
from wms_sdk.testing import create_test_engine
from wms_sdk.testing.sqlite import create_sqlite_engine

PLANT, WAREHOUSE, ZONE = "C221", "W1", "1"


def column_layout(origin_x: int) -> ColumnLayout:
    return ColumnLayout(
        origin_x=Decimal(origin_x),
        origin_y=Decimal(0),
        direction=RowDirection.DOWN,
        rows=3,
        max_level=2,
        sub_column=1,
        cell_width=Decimal(30),
        cell_height=Decimal(10),
        level_gap=Decimal(1),
        row_gap=Decimal(4),
    )


def open_site(url: str | None = None) -> Session:
    """In-memory SQLite by default (SQL Server when WMS_TEST_MSSQL_URL is set);
    pass a file URL (sqlite:///x.sqlite) to keep it.
    """
    engine = create_sqlite_engine(url) if url else create_test_engine("site")
    metadata.create_all(engine)
    factory = sessionmaker(engine)
    install_capture(factory)
    session = factory()

    reference_factory.seed(session)
    verify_factory(session)

    start_operation(session, actor=None)
    for row in [
        Plant(code=PLANT, name="TL"),
        User(username="planner1", employee_id="E001", first_name="Planner", last_name="One", role_code="Planner"),
        User(username="forklift1", employee_id="E002", first_name="Forklift", last_name="One", role_code="Forklift"),
        User(username="lab1", employee_id="E003", first_name="Lab", last_name="One", role_code="Lab"),
        Warehouse(plant_code=PLANT, code=WAREHOUSE),
        Product(sku="A001", name_thai="ปูนฉาบ", name_eng="Plaster"),
        Product(sku="A002", name_thai="ปูนก่อ", name_eng="Mortar"),
    ]:
        session.add(row)
        session.flush()
    session.commit()

    # The map builder creates the zone, the locations and their drawings.
    start_operation(session, actor="planner1")
    for column_no, origin_x in [(1, 0), (2, 40)]:
        save_column(
            session,
            plant_code=PLANT,
            warehouse_code=WAREHOUSE,
            zone_code=ZONE,
            column_no=column_no,
            layout=column_layout(origin_x),
            pallet_length_cm=120,
        )
    session.commit()
    return session
