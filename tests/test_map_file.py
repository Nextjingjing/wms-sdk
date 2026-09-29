import json
import zipfile

import pytest
from sqlalchemy import select

from examples.cookbook.share_map import draw_warehouse, open_empty_wms
from examples.cookbook.site import PLANT, WAREHOUSE, open_site
from examples.reference_factory.models import LocationProperties
from wms_sdk.features.floor_map.models import FloorImage
from wms_sdk.features.map_file import (
    LocationCodeTaken,
    PropertiesMismatch,
    UnsupportedMapFile,
    WarehouseExists,
    _encode,
    export_map,
    import_map,
)
from wms_sdk.features.routing.models import RouteMap, RouteStatus
from wms_sdk.modules.events.capture import start_operation
from wms_sdk.modules.events.models import EventLog
from wms_sdk.modules.storage.models import Location, Warehouse, Zone
from wms_sdk.shared.models.plant import Plant


@pytest.fixture
def exported(tmp_path):
    session = open_site()
    draw_warehouse(session, tmp_path / "ours")
    path = tmp_path / "W1.wmsmap"
    export_map(session, PLANT, WAREHOUSE, path, image_root=tmp_path / "ours")
    return session, path


def rewrite(path, name, change):
    """Edit one JSON member of a .wmsmap file in place."""
    with zipfile.ZipFile(path) as archive:
        members = {n: archive.read(n) for n in archive.namelist()}
    content = json.loads(members[name])
    change(content)
    members[name] = json.dumps(content).encode()
    with zipfile.ZipFile(path, "w") as archive:
        for n, data in members.items():
            archive.writestr(n, data)


def rows(session, model):
    return [_encode(row) for row in session.scalars(select(model).order_by(*model.__table__.primary_key))]


def test_round_trip_rebuilds_the_warehouse(exported, tmp_path):
    ours, path = exported
    friend = open_empty_wms()
    start_operation(friend, actor=None)
    summary = import_map(friend, path, image_root=tmp_path / "theirs")
    friend.commit()

    for model in (Plant, Warehouse, Zone, Location, LocationProperties, FloorImage):
        assert rows(friend, model) == rows(ours, model), model.__tablename__
    assert rows(friend, LocationProperties)  # properties really travelled

    route_map = friend.get(RouteMap, (PLANT, WAREHOUSE, 1))
    assert route_map.status == RouteStatus.PUBLISHED
    assert route_map.published_by is None  # planner1 does not exist on the friend's side

    assert summary.images == ["floors/tl-site.png", "warehouses/tl-w1.png"]
    assert (tmp_path / "theirs/floors/tl-site.png").read_bytes() == b"site picture"
    assert friend.scalar(select(EventLog).where(EventLog.event_type == "map_file.imported"))


def test_existing_warehouse_is_refused(exported, tmp_path):
    ours, path = exported
    start_operation(ours, actor=None)
    with pytest.raises(WarehouseExists):
        import_map(ours, path, image_root=tmp_path / "ours")


def test_location_code_used_by_another_warehouse_is_refused(exported, tmp_path):
    _, path = exported
    friend = open_empty_wms()
    start_operation(friend, actor=None)
    for row in [
        Plant(code="C999", name="Other"),
        Warehouse(plant_code="C999", code="W9"),
        Zone(plant_code="C999", warehouse_code="W9", code="1"),
        Location(code="tl-w1-1-0101", plant_code="C999", warehouse_code="W9", zone_code="1"),
    ]:
        friend.add(row)
        friend.flush()
    with pytest.raises(LocationCodeTaken, match="tl-w1-1-0101"):
        import_map(friend, path, image_root=tmp_path / "theirs")


def test_different_properties_columns_need_properties_false(exported, tmp_path):
    _, path = exported
    rewrite(path, "manifest.json", lambda m: m["properties_columns"]["location_properties"].append("bay_no"))
    friend = open_empty_wms()
    start_operation(friend, actor=None)
    with pytest.raises(PropertiesMismatch, match="bay_no"):
        import_map(friend, path, image_root=tmp_path / "theirs")

    import_map(friend, path, image_root=tmp_path / "theirs", properties=False)
    assert friend.scalars(select(Location)).all()
    assert not friend.scalars(select(LocationProperties)).all()


def test_existing_floor_image_is_kept(exported, tmp_path):
    _, path = exported
    friend = open_empty_wms()
    start_operation(friend, actor=None)
    friend.add(FloorImage(code="TL-SITE", name="ours", image_path="floors/mine.png", width=1, height=1))
    friend.flush()
    summary = import_map(friend, path, image_root=tmp_path / "theirs")
    assert friend.get(FloorImage, "TL-SITE").name == "ours"
    assert summary.images == ["warehouses/tl-w1.png"]
    assert not (tmp_path / "theirs/floors/tl-site.png").exists()


def test_image_path_outside_image_root_is_refused(exported, tmp_path):
    _, path = exported
    rewrite(path, "map.json", lambda m: m["warehouse_maps"][0].update(background_path="../evil.png"))
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("images/../evil.png", b"x")
    friend = open_empty_wms()
    start_operation(friend, actor=None)
    with pytest.raises(UnsupportedMapFile, match="inside image_root"):
        import_map(friend, path, image_root=tmp_path / "theirs")
    assert not (tmp_path / "evil.png").exists()


def test_other_files_are_not_map_files(tmp_path):
    path = tmp_path / "notes.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("readme.txt", "hello")
    friend = open_empty_wms()
    start_operation(friend, actor=None)
    with pytest.raises(UnsupportedMapFile, match="manifest.json is missing"):
        import_map(friend, path)
