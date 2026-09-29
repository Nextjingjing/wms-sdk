"""Try a .wmsmap file with real pictures: export a warehouse with its site
picture and background, import it into a second, empty database, and check
that the pictures and routing arrived intact.

    python -m dev.demo_map                                          # draws its own pictures
    python -m dev.demo_map --site my-site.png --background my-w1.jpg

Output goes to demo_map/ (git-ignored):

- W1.wmsmap: the file sent
- ours.sqlite, ours/: the sender's database and pictures
- theirs.sqlite, theirs/: the receiver's database and pictures, as written by the import
"""

import argparse
import hashlib
import shutil
import struct
import zipfile
import zlib
from decimal import Decimal as D
from pathlib import Path

from sqlalchemy import func, select

from examples.cookbook.map_and_routing import draw_road
from examples.cookbook.share_map import open_empty_wms
from examples.cookbook.site import PLANT, WAREHOUSE, open_site
from wms_sdk.features.floor_map.models import FloorImage, LocationMap, WarehouseMap
from wms_sdk.features.map_file import export_map, import_map
from wms_sdk.features.routing.graph import AccessPosition, cost_to, path_to, road_of, shortest_from
from wms_sdk.features.routing.models import AccessPoint, RouteMap, RouteVertex
from wms_sdk.features.routing.repository import access_position, load_graph, publish, published_route_map
from wms_sdk.modules.events.capture import start_operation
from wms_sdk.modules.storage.models import Location

OUT = Path("demo_map")


class Canvas:
    """Minimal RGB picture written as PNG, so the demo needs no imaging library."""

    def __init__(self, w: int, h: int, bg: tuple[int, int, int]):
        self.w, self.h = w, h
        self.px = [bytearray(bytes(bg) * w) for _ in range(h)]

    def rect(self, x, y, w, h, color) -> None:
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(self.w, int(x + w)), min(self.h, int(y + h))
        for row in self.px[y0:y1]:
            row[x0 * 3 : x1 * 3] = bytes(color) * (x1 - x0)

    def frame(self, x, y, w, h, color, t=2) -> None:
        self.rect(x, y, w, t, color)
        self.rect(x, y + h - t, w, t, color)
        self.rect(x, y, t, h, color)
        self.rect(x + w - t, y, t, h, color)

    def save_png(self, path: Path) -> None:
        def chunk(tag: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

        raw = b"".join(b"\x00" + bytes(row) for row in self.px)
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b"")
        )


def site_picture(session) -> Canvas:
    c = Canvas(1000, 600, (164, 196, 140))  # grass
    c.rect(0, 360, 1000, 40, (120, 120, 120))  # site roads
    c.rect(480, 0, 40, 600, (120, 120, 120))
    for x, y, w, h in [(560, 60, 180, 120), (780, 60, 170, 250), (560, 440, 390, 120), (60, 440, 380, 120)]:
        c.rect(x, y, w, h, (200, 196, 188))  # other buildings
        c.frame(x, y, w, h, (90, 90, 90))
    c.rect(100, 80, 360, 240, (236, 228, 205))  # W1, where WarehouseMap puts it
    c.frame(100, 80, 360, 240, (180, 60, 40), 4)
    return c


def warehouse_picture(session) -> Canvas:
    """Drawn from the database: road vertices and location boxes, drawing
    units -20..160 x -30..90 at 4 px per unit.
    """
    s, ox, oy = 4, 20, 30
    c = Canvas(720, 480, (236, 228, 205))
    a, b, d = (session.get(RouteVertex, (PLANT, WAREHOUSE, 1, code)) for code in "ABD")
    c.rect((a.x + ox) * s, (a.y + oy) * s - 12, (d.x - a.x) * s, 24, (110, 110, 110))
    for v in (a, b, d):
        c.rect((v.x + ox) * s - 8, (v.y + oy) * s - 8, 16, 16, (40, 90, 170))
    for box in session.scalars(select(LocationMap)):
        x, y, w, h = (box.x + ox) * s, (box.y + oy) * s, box.width * s, box.height * s
        c.rect(x, y, w, h, (250, 214, 120))
        c.frame(x, y, w, h, (120, 80, 20))
    c.frame(0, 0, 720, 480, (60, 60, 60), 6)
    return c


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main() -> None:
    parser = argparse.ArgumentParser(description="Try a .wmsmap file with real pictures.")
    parser.add_argument("--site", type=Path, help="site picture (any image file); drawn if omitted")
    parser.add_argument("--background", type=Path, help="warehouse background; drawn if omitted")
    args = parser.parse_args()

    shutil.rmtree(OUT, ignore_errors=True)
    ours, theirs, file = OUT / "ours", OUT / "theirs", OUT / "W1.wmsmap"

    OUT.mkdir()
    session = open_site(f"sqlite:///{OUT / 'ours.sqlite'}")
    start_operation(session, actor="planner1")
    draw_road(session)
    publish(session, session.get(RouteMap, (PLANT, WAREHOUSE, 1)), actor="planner1")
    session.commit()

    # Stored paths keep the given file's extension; the database holds only the path.
    site = f"floors/tl-site{args.site.suffix if args.site else '.png'}"
    background = f"warehouses/tl-w1{args.background.suffix if args.background else '.png'}"
    for stored, given, draw in [(site, args.site, site_picture), (background, args.background, warehouse_picture)]:
        (ours / stored).parent.mkdir(parents=True, exist_ok=True)
        if given:
            shutil.copyfile(given, ours / stored)
        else:
            draw(session).save_png(ours / stored)

    start_operation(session, actor="planner1")
    session.add(FloorImage(code="TL-SITE", name="TL site", image_path=site, width=D(1000), height=D(600)))
    session.flush()
    session.add(WarehouseMap(plant_code=PLANT, warehouse_code=WAREHOUSE, floor_image_code="TL-SITE",
                             x=D(100), y=D(80), width=D(360), height=D(240), background_path=background))  # fmt: skip
    session.commit()

    sent = export_map(session, PLANT, WAREHOUSE, file, image_root=ours)
    print(f"exported {file}: {sent.locations} locations, route revision {sent.route_revision}")
    with zipfile.ZipFile(file) as archive:
        for info in archive.infolist():
            print(f"  {info.filename:30} {info.file_size:>8} B")

    friend = open_empty_wms(f"sqlite:///{OUT / 'theirs.sqlite'}")
    start_operation(friend, actor=None)
    got = import_map(friend, file, image_root=theirs)
    friend.commit()
    print(f"imported into an empty database: {friend.scalar(select(func.count()).select_from(Location))} locations")
    for image in got.images:
        print(f"  {image}: identical to the sender's = {sha(ours / image) == sha(theirs / image)}")

    route_map = published_route_map(friend, PLANT, WAREHOUSE)
    graph = load_graph(friend, route_map)
    paths = shortest_from(graph, AccessPosition(road=road_of("B", "D"), ratio=1.0, approach_m=0.0))
    for point in friend.scalars(select(AccessPoint)):
        cost = cost_to(graph, paths, access_position(route_map, point))
        print(f"  dock -> {point.location_code}: {cost.total_m:.2f} m via {path_to(paths, cost)}")
    print(f"pictures written by the import: {theirs.resolve()}")
    print(f"databases: {(OUT / 'ours.sqlite').resolve()}, {(OUT / 'theirs.sqlite').resolve()}")
    session.close()
    friend.close()


if __name__ == "__main__":
    main()
