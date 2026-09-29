"""Draw a road in front of the columns, publish it, and find the nearest free
location for a forklift standing at the dock:

    python -m examples.cookbook.map_and_routing

    A ────────── B ──── D (dock)
      [col 1] [col 2]           lane mouths of row 1 open onto road A-B
"""

from decimal import Decimal

from sqlalchemy import select

from examples.cookbook.site import PLANT, WAREHOUSE, open_site
from examples.reference_factory.models import Pallet
from wms_sdk.features.floor_map.models import LocationMap
from wms_sdk.features.routing.graph import (
    AccessPosition,
    LaneMouth,
    cost_to,
    layout_road,
    offset_ratio,
    path_to,
    road_of,
    shortest_from,
    unreachable_vertices,
)
from wms_sdk.features.routing.models import (
    AccessPoint,
    AccessSide,
    DistanceSource,
    RouteEdge,
    RouteMap,
    RouteStatus,
    RouteVertex,
    VertexType,
)
from wms_sdk.features.routing.repository import (
    access_position,
    load_graph,
    publish,
    published_route_map,
)
from wms_sdk.modules.events.capture import start_operation
from wms_sdk.modules.inventory.qc import QcStatus

D = Decimal
KEY = {"plant_code": PLANT, "warehouse_code": WAREHOUSE, "revision_no": 1}
# Road y = -10 on the drawing: just above row 1 of both columns.
VERTICES = {"A": (D(0), D(-10)), "B": (D(100), D(-10)), "D": (D(140), D(-10))}
ENTRANCES = ["tl-w1-1-0101", "tl-w1-1-0201"]  # row 1 of each column opens onto the road
LANE_WIDTH_M = D("1.2")  # pallet length x sub_column


def draw_road(session) -> None:
    session.add(RouteMap(**KEY, status=RouteStatus.DRAFT))
    session.flush()
    session.add_all(
        RouteVertex(**KEY, code=code, vertex_type=VertexType.DOCK if code == "D" else VertexType.CORNER,
                    x=x, y=y, clearance_m=D(3))
        for code, (x, y) in VERTICES.items()
    )  # fmt: skip
    session.flush()

    # Place the lane mouths on road A-B from where the locations are drawn.
    mouths = []
    for code in ENTRANCES:
        box = session.get(LocationMap, code)
        mouths.append(LaneMouth(code, (box.x + box.width / 2, box.y), LANE_WIDTH_M))
    layout = layout_road(VERTICES["A"], VERTICES["B"], D(3), D(3), mouths)

    edges = [("A", "B", layout.calculated_length_m, DistanceSource.CALCULATED),
             ("B", "D", D(10), DistanceSource.MANUAL)]  # fmt: skip
    for a, b, metres, source in edges:
        for start, end in [(a, b), (b, a)]:  # two-way roads
            session.add(RouteEdge(**KEY, from_code=start, to_code=end, distance_m=metres, distance_source=source))
    session.flush()

    for placed in layout.mouths:
        session.add(
            AccessPoint(
                **KEY,
                location_code=placed.key,
                side=AccessSide.FRONT,
                road_start_code="A",
                road_end_code="B",
                road_side=placed.road_side,
                offset_ratio=offset_ratio(placed.offset_m, layout.calculated_length_m),
                allow_putaway=True,
                allow_pick=True,
            )
        )
    print(f"road A-B: {layout.calculated_length_m} m, mouths at {[str(p.offset_m) for p in layout.mouths]} m")


def main() -> None:
    session = open_site()

    start_operation(session, actor="planner1")
    draw_road(session)
    draft = session.get(RouteMap, (PLANT, WAREHOUSE, 1))
    publish(session, draft, actor="planner1")
    session.commit()

    # Column 2's entrance is already taken.
    start_operation(session, actor="forklift1")
    session.add(Pallet(code="P-0100", sku="A001", lot_no="L1", qty=10, qc_status=QcStatus.WAITING,
                       location_code="tl-w1-1-0201", level_no=1, slot_no=1))  # fmt: skip
    session.commit()

    route_map = published_route_map(session, PLANT, WAREHOUSE)
    graph = load_graph(session, route_map)
    print(f"unreachable vertices: {unreachable_vertices(graph) or 'none'}")

    dock = AccessPosition(road=road_of("B", "D"), ratio=1.0, approach_m=0.0)  # at vertex D
    paths = shortest_from(graph, dock)
    occupied = set(session.scalars(select(Pallet.location_code).where(Pallet.location_code.is_not(None))))

    candidates = []
    for point in session.scalars(select(AccessPoint)):
        cost = cost_to(graph, paths, access_position(route_map, point))
        if cost is None:
            print(f"  {point.location_code}: unreachable")
            continue
        free = point.location_code not in occupied
        print(f"  {point.location_code}: {cost.total_m:.2f} m {'free' if free else 'occupied'}")
        if free:
            candidates.append((cost.total_m, point.location_code, cost))
    total, nearest, cost = min(candidates)
    print(f"nearest free location: {nearest} ({total:.2f} m, via {path_to(paths, cost)})")


if __name__ == "__main__":
    main()
