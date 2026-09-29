from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from wms_sdk.features.routing.graph import (
    AccessPosition,
    Edge,
    LaneMouth,
    RoadSide,
    build_graph,
    cost_to,
    layout_road,
    offset_ratio,
    path_to,
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
    InvalidRouteStatus,
    access_position,
    load_graph,
    publish,
    published_route_map,
)
from wms_sdk.modules.events.capture import start_operation
from wms_sdk.modules.events.models import EventLog
from wms_sdk.modules.storage.models import Location, Warehouse, Zone
from wms_sdk.shared.models.plant import Plant

#  A --10-- B --5--> C --8-- D      (B -> C is one-way)
#  |                         |
#  +-----------40------------+
NETWORK = [
    Edge("A", "B", 10), Edge("B", "A", 10),
    Edge("B", "C", 5),
    Edge("C", "D", 8), Edge("D", "C", 8),
    Edge("A", "D", 40), Edge("D", "A", 40),
]  # fmt: skip


def at(start, end, ratio, approach=0.0):
    return AccessPosition(road=(start, end), ratio=ratio, approach_m=approach)


def test_shortest_route_respects_one_way_roads():
    graph = build_graph(NETWORK)
    paths = shortest_from(graph, at("A", "B", 0.0))  # at vertex A's end of road A-B

    to_d = cost_to(graph, paths, at("C", "D", 1.0))  # at D's end of road C-D
    assert to_d.road_m == pytest.approx(23)  # A->B->C->D, cheaper than A->D (40)
    assert path_to(paths, to_d) == ["B", "C"]

    back = shortest_from(graph, at("C", "D", 0.0))  # at C: cannot go C -> B
    to_b = cost_to(graph, back, at("A", "B", 1.0))
    assert to_b.road_m == pytest.approx(8 + 40 + 10)  # C->D->A->B


def test_same_road_goes_straight_and_adds_approaches():
    graph = build_graph(NETWORK)
    paths = shortest_from(graph, at("A", "D", 0.25, approach=3))
    cost = cost_to(graph, paths, at("A", "D", 0.75, approach=2))
    assert cost.road_m == pytest.approx(20)
    assert cost.last_vertex is None
    assert cost.total_m == pytest.approx(25)


def test_unreachable_vertices_are_reported():
    graph = build_graph(NETWORK + [Edge("X", "Y", 3)])
    assert unreachable_vertices(graph) == {"X", "Y"}
    assert unreachable_vertices(build_graph(NETWORK)) == set()


def test_layout_places_mouths_per_side_in_order():
    start, end = (Decimal(0), Decimal(0)), (Decimal(100), Decimal(0))
    mouths = [
        LaneMouth("L2", (Decimal(60), Decimal(-10)), Decimal("2.4")),
        LaneMouth("L1", (Decimal(20), Decimal(-10)), Decimal("1.2")),
        LaneMouth("R1", (Decimal(50), Decimal(10)), Decimal("1.2")),
    ]
    layout = layout_road(start, end, Decimal(3), Decimal(3), mouths)

    placed = {m.key: m for m in layout.mouths}
    assert placed["L1"].road_side is RoadSide.LEFT and placed["L1"].offset_m == Decimal("3.6")
    assert placed["L2"].offset_m == Decimal("5.4")  # 3 + 1.2 + 2.4 / 2
    assert placed["R1"].road_side is RoadSide.RIGHT
    assert layout.calculated_length_m == Decimal("9.60")  # 3 + widest side (3.6) + 3
    assert offset_ratio(Decimal("5.4"), layout.calculated_length_m) == Decimal("0.5625")


def test_mouth_on_the_road_line_is_rejected():
    start, end = (Decimal(0), Decimal(0)), (Decimal(10), Decimal(0))
    with pytest.raises(ValueError):
        layout_road(start, end, Decimal(1), Decimal(1), [LaneMouth("M", (Decimal(5), Decimal(0)), Decimal(1))])


# ---------- database ----------


@pytest.fixture
def warehouse(session):
    start_operation(session, actor=None)
    for row in [
        Plant(code="C221", name="TL"),
        Warehouse(plant_code="C221", code="W1"),
        Warehouse(plant_code="C221", code="W2"),
        Zone(plant_code="C221", warehouse_code="W1", code="1"),
        Zone(plant_code="C221", warehouse_code="W2", code="1"),
        Location(code="w1-0101", plant_code="C221", warehouse_code="W1", zone_code="1"),
        Location(code="w2-0101", plant_code="C221", warehouse_code="W2", zone_code="1"),
    ]:
        session.add(row)
        session.flush()
    session.commit()
    return session


def draft(session, revision_no, edges=(("A", "B", 10),)):
    key = {"plant_code": "C221", "warehouse_code": "W1", "revision_no": revision_no}
    route_map = RouteMap(**key, status=RouteStatus.DRAFT)
    session.add(route_map)
    session.flush()
    codes = sorted({code for edge in edges for code in edge[:2]})
    session.add_all(
        RouteVertex(**key, code=c, vertex_type=VertexType.CORNER, x=0, y=0) for c in codes
    )
    session.flush()
    session.add_all(
        RouteEdge(**key, from_code=a, to_code=b, distance_m=d, distance_source=DistanceSource.MANUAL)
        for a, b, d in edges
    )
    session.flush()
    return route_map


def test_publish_archives_previous_revision(warehouse):
    session = warehouse
    start_operation(session, actor=None)
    first = draft(session, 1)
    publish(session, first, actor=None)
    session.commit()

    start_operation(session, actor=None)
    second = draft(session, 2)
    publish(session, second, actor=None)
    session.commit()

    assert first.status is RouteStatus.ARCHIVED
    assert published_route_map(session, "C221", "W1") is second
    assert second.published_at is not None
    types = session.scalars(select(EventLog.event_type)).all()
    assert types.count("route_map.published") == 2

    with pytest.raises(InvalidRouteStatus):
        publish(session, second, actor=None)


def test_only_one_draft_per_warehouse(warehouse):
    start_operation(warehouse, actor=None)
    draft(warehouse, 1)
    warehouse.add(RouteMap(plant_code="C221", warehouse_code="W1", revision_no=2, status=RouteStatus.DRAFT))
    with pytest.raises(IntegrityError):
        warehouse.flush()


def test_graph_and_access_point_load_from_database(warehouse):
    session = warehouse
    start_operation(session, actor=None)
    route_map = draft(session, 1, edges=(("A", "B", 10), ("B", "A", 10)))
    point = AccessPoint(
        plant_code="C221", warehouse_code="W1", revision_no=1,
        location_code="w1-0101", side=AccessSide.FRONT,
        road_start_code="A", road_end_code="B", road_side=RoadSide.LEFT,
        offset_ratio=Decimal("0.5"), allow_putaway=True, allow_pick=True,
    )  # fmt: skip
    session.add(point)
    session.commit()

    graph = load_graph(session, route_map)
    position = access_position(route_map, point)
    assert position == AccessPosition(road=("A", "B"), ratio=0.5, approach_m=3.0)
    assert graph.roads[("A", "B")].forward and graph.roads[("A", "B")].backward


def access(**fields):
    base = dict(
        plant_code="C221", warehouse_code="W1", revision_no=1,
        location_code="w1-0101", side=AccessSide.FRONT,
        road_start_code="A", road_end_code="B", road_side=RoadSide.LEFT,
        offset_ratio=Decimal("0.5"), allow_putaway=True, allow_pick=True,
    )  # fmt: skip
    return AccessPoint(**{**base, **fields})


@pytest.mark.parametrize(
    "row",
    [
        access(location_code="w2-0101"),  # location of another warehouse
        access(road_start_code="B", road_end_code="A"),  # start must be the smaller code
        access(allow_putaway=False, allow_pick=False),
        access(offset_ratio=Decimal("1.5")),
    ],
    ids=["other-warehouse", "start-not-smaller", "allows-nothing", "ratio-out-of-range"],
)
def test_invalid_access_point_is_rejected(warehouse, row):
    start_operation(warehouse, actor=None)
    draft(warehouse, 1)
    warehouse.add(row)
    with pytest.raises(IntegrityError):
        warehouse.flush()
