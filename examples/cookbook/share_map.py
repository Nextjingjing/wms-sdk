"""Send a warehouse to a friend as one file: draw it, export it with its
pictures and route map, then import it into an empty database and route on it
there:

    python -m examples.cookbook.share_map
"""

import tempfile
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

import examples.reference_factory.seed as reference_factory
from examples.cookbook.map_and_routing import draw_road
from examples.cookbook.site import PLANT, WAREHOUSE, open_site
from wms_sdk.checks import verify_factory
from wms_sdk.features.floor_map.models import FloorImage, WarehouseMap
from wms_sdk.features.map_file import WarehouseExists, export_map, import_map
from wms_sdk.features.routing.graph import AccessPosition, cost_to, road_of, shortest_from
from wms_sdk.features.routing.models import AccessPoint, RouteMap
from wms_sdk.features.routing.repository import (
    access_position,
    load_graph,
    publish,
    published_route_map,
)
from wms_sdk.metadata import metadata
from wms_sdk.modules.events.capture import install_capture, start_operation
from wms_sdk.modules.storage.models import Location
from wms_sdk.testing import create_test_engine
from wms_sdk.testing.sqlite import create_sqlite_engine

D = Decimal


def draw_warehouse(session, media: Path) -> None:
    """Site picture, warehouse outline with its own background, and a road."""
    (media / "floors").mkdir(parents=True)
    (media / "floors" / "tl-site.png").write_bytes(b"site picture")
    (media / "warehouses").mkdir()
    (media / "warehouses" / "tl-w1.png").write_bytes(b"warehouse picture")

    start_operation(session, actor="planner1")
    session.add(FloorImage(code="TL-SITE", name="TL site", image_path="floors/tl-site.png",
                           width=D(2000), height=D(1200)))  # fmt: skip
    session.flush()
    session.add(WarehouseMap(plant_code=PLANT, warehouse_code=WAREHOUSE, floor_image_code="TL-SITE",
                             x=D(100), y=D(80), width=D(600), height=D(400),
                             background_path="warehouses/tl-w1.png"))  # fmt: skip
    draw_road(session)
    publish(session, session.get(RouteMap, (PLANT, WAREHOUSE, 1)), actor="planner1")
    session.commit()


def open_empty_wms(url: str | None = None):
    """The friend's side: same factory models, seeded, no warehouse yet."""
    engine = create_sqlite_engine(url) if url else create_test_engine("friend")
    metadata.create_all(engine)
    factory = sessionmaker(engine)
    install_capture(factory)
    session = factory()
    reference_factory.seed(session)
    verify_factory(session)
    return session


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ours, theirs, file = Path(tmp, "ours"), Path(tmp, "theirs"), Path(tmp, "W1.wmsmap")

        session = open_site()
        draw_warehouse(session, ours)
        sent = export_map(session, PLANT, WAREHOUSE, file, image_root=ours)
        print(f"exported {file.name}: {sent.zones} zone, {sent.locations} locations, "
              f"pictures {sent.images}, route revision {sent.route_revision}")  # fmt: skip

        friend = open_empty_wms()
        start_operation(friend, actor=None)
        got = import_map(friend, file, image_root=theirs)
        friend.commit()
        print(f"imported {got.plant_code}/{got.warehouse_code}: "
              f"{friend.scalar(select(func.count()).select_from(Location))} locations")  # fmt: skip
        for image in got.images:
            print(f"  picture {image}: {(theirs / image).read_bytes().decode()!r}")

        route_map = published_route_map(friend, PLANT, WAREHOUSE)
        graph = load_graph(friend, route_map)
        paths = shortest_from(graph, AccessPosition(road=road_of("B", "D"), ratio=1.0, approach_m=0.0))
        point = friend.get(AccessPoint, (PLANT, WAREHOUSE, 1, "tl-w1-1-0101", "front"))
        cost = cost_to(graph, paths, access_position(route_map, point))
        print(f"routing works on the friend's side: dock -> tl-w1-1-0101 {cost.total_m:.2f} m")

        start_operation(friend, actor=None)
        try:
            import_map(friend, file, image_root=theirs)
        except WarehouseExists as error:
            print(f"second import refused: {error}")


if __name__ == "__main__":
    main()
