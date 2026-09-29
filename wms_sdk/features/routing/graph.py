"""Forklift routing on a road network. Pure functions, no I/O. Shortest
paths and connectivity come from networkx; what it lacks (lane mouths in the
middle of a road) is handled here.

- A road is identified by its two vertex codes; its start is the smaller code
  (ordinal), so the identity does not change when a revision is copied.
- A lane mouth is not a vertex: it sits on a road at `ratio` of its length.
- Distances are estimates: offset = start clearance + widths of the lanes
  before + half of this lane.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

try:
    import networkx as nx
except ImportError as error:  # pragma: no cover - depends on the environment
    raise ImportError('routing needs networkx: pip install "wms-sdk[routing]"') from error

from .models import RoadSide

RATIO_STEP = Decimal("0.000001")
METRE_STEP = Decimal("0.01")

Road = tuple[str, str]  # (start_code, end_code), start < end
CanvasPoint = tuple[Decimal, Decimal]


def road_of(vertex_a: str, vertex_b: str) -> Road:
    return (vertex_a, vertex_b) if vertex_a < vertex_b else (vertex_b, vertex_a)


# ---------- placing lane mouths on a road ----------


@dataclass(frozen=True)
class LaneMouth:
    """A lane opening onto a road. Canvas position is only used to order
    mouths along the road and to find the road side.
    """

    key: object  # caller's identity for the mouth, e.g. (location_code, side)
    center: CanvasPoint
    lane_width_m: Decimal


@dataclass(frozen=True)
class PlacedMouth:
    key: object
    road_side: RoadSide
    offset_m: Decimal


@dataclass(frozen=True)
class RoadLayout:
    calculated_length_m: Decimal
    mouths: list[PlacedMouth]


def road_side_of(start: CanvasPoint, end: CanvasPoint, point: CanvasPoint) -> RoadSide | None:
    """Side of `point` looking from start to end, on a canvas whose y axis
    points down. None if the point is on the road line.
    """
    cross = (end[0] - start[0]) * (point[1] - start[1]) - (end[1] - start[1]) * (point[0] - start[0])
    if cross > 0:
        return RoadSide.RIGHT
    if cross < 0:
        return RoadSide.LEFT
    return None


def _along(start: CanvasPoint, end: CanvasPoint, point: CanvasPoint) -> Decimal:
    """Unnormalised distance along the road; only for ordering."""
    return (point[0] - start[0]) * (end[0] - start[0]) + (point[1] - start[1]) * (end[1] - start[1])


def layout_road(
    start: CanvasPoint,
    end: CanvasPoint,
    start_clearance_m: Decimal,
    end_clearance_m: Decimal,
    mouths: list[LaneMouth],
) -> RoadLayout:
    """Offset of every mouth along a road, per side, and the road's estimated
    length. Raises ValueError for a mouth exactly on the road line.
    """
    by_side: dict[RoadSide, list[LaneMouth]] = {RoadSide.LEFT: [], RoadSide.RIGHT: []}
    for mouth in mouths:
        side = road_side_of(start, end, mouth.center)
        if side is None:
            raise ValueError(f"lane mouth {mouth.key} is on the road line; no side")
        by_side[side].append(mouth)

    placed: list[PlacedMouth] = []
    widest = Decimal(0)
    for side, side_mouths in by_side.items():
        # Ties broken by key so the result is the same every time.
        ordered = sorted(side_mouths, key=lambda m: (_along(start, end, m.center), str(m.key)))
        used = Decimal(0)
        for mouth in ordered:
            offset = start_clearance_m + used + mouth.lane_width_m / 2
            placed.append(PlacedMouth(key=mouth.key, road_side=side, offset_m=offset))
            used += mouth.lane_width_m
        widest = max(widest, used)

    length = (start_clearance_m + widest + end_clearance_m).quantize(METRE_STEP, ROUND_HALF_UP)
    return RoadLayout(calculated_length_m=length, mouths=placed)


def offset_ratio(offset_m: Decimal, calculated_length_m: Decimal) -> Decimal:
    """Ratio from the road start. Always from the calculated length, so a
    manually entered length moves mouths proportionally.
    """
    if calculated_length_m <= 0:
        return Decimal(0)
    ratio = min(Decimal(1), max(Decimal(0), offset_m / calculated_length_m))
    return ratio.quantize(RATIO_STEP, ROUND_HALF_UP)


# ---------- shortest paths ----------


@dataclass(frozen=True)
class Edge:
    from_code: str
    to_code: str
    distance_m: float


@dataclass(frozen=True)
class RoadInfo:
    length_m: float
    forward: bool  # start -> end allowed
    backward: bool  # end -> start allowed


@dataclass(frozen=True)
class AccessPosition:
    """A lane mouth on a road, plus the distance from the road into the lane."""

    road: Road
    ratio: float
    approach_m: float


@dataclass(frozen=True)
class RouteGraph:
    network: "nx.DiGraph"  # vertices by code, edge attribute distance_m
    roads: dict[Road, RoadInfo]


def build_graph(edges: list[Edge]) -> RouteGraph:
    network = nx.DiGraph()
    lengths: dict[Road, float] = {}
    directions: dict[Road, set[tuple[str, str]]] = {}
    for edge in edges:
        network.add_edge(edge.from_code, edge.to_code, distance_m=edge.distance_m)
        road = road_of(edge.from_code, edge.to_code)
        lengths[road] = edge.distance_m
        directions.setdefault(road, set()).add((edge.from_code, edge.to_code))
    roads = {
        road: RoadInfo(
            length_m=length,
            forward=road in directions[road],
            backward=(road[1], road[0]) in directions[road],
        )
        for road, length in lengths.items()
    }
    return RouteGraph(network=network, roads=roads)


@dataclass(frozen=True)
class ShortestPaths:
    """One Dijkstra run from a source mouth; ask distances to any target."""

    source: AccessPosition
    distance: dict[str, float]
    previous: dict[str, str | None]  # None = reached straight from the source mouth


# Temporary vertex for the source mouth; a tuple can never equal a vertex code.
_SOURCE = ("source mouth",)


def shortest_from(graph: RouteGraph, source: AccessPosition) -> ShortestPaths:
    """Dijkstra from a lane mouth: leave towards either end of its road, as
    the road's directions allow.
    """
    road = graph.roads.get(source.road)
    if road is None:
        return ShortestPaths(source, {}, {})

    network = graph.network.copy()
    start, end = source.road
    if road.backward:
        network.add_edge(_SOURCE, start, distance_m=source.ratio * road.length_m)
    if road.forward:
        network.add_edge(_SOURCE, end, distance_m=(1 - source.ratio) * road.length_m)
    if _SOURCE not in network:
        return ShortestPaths(source, {}, {})

    lengths, routes = nx.single_source_dijkstra(network, _SOURCE, weight="distance_m")
    distance = {v: d for v, d in lengths.items() if v != _SOURCE}
    previous = {v: (None if r[-2] == _SOURCE else r[-2]) for v, r in routes.items() if v != _SOURCE}
    return ShortestPaths(source, distance, previous)


@dataclass(frozen=True)
class RouteCost:
    """Total = into the road at the source + along roads + into the target lane.
    last_vertex is the vertex before the target's road (None = same road).
    """

    source_approach_m: float
    road_m: float
    target_approach_m: float
    last_vertex: str | None

    @property
    def total_m(self) -> float:
        return self.source_approach_m + self.road_m + self.target_approach_m


def cost_to(graph: RouteGraph, paths: ShortestPaths, target: AccessPosition) -> RouteCost | None:
    """Distance from the paths' source to `target`, or None if unreachable.
    Builds no vertex list, so thousands of targets can be priced per Dijkstra
    run; call path_to on the chosen one. Ties: same road, then via road
    start, then via road end.
    """
    road = graph.roads.get(target.road)
    source = paths.source
    if road is None or source.road not in graph.roads:
        return None

    candidates: list[tuple[float, str | None]] = []
    if source.road == target.road:
        gap = (target.ratio - source.ratio) * road.length_m
        if (gap >= 0 and road.forward) or (gap <= 0 and road.backward):
            candidates.append((abs(gap), None))
    start, end = target.road
    if road.forward and start in paths.distance:
        candidates.append((paths.distance[start] + target.ratio * road.length_m, start))
    if road.backward and end in paths.distance:
        candidates.append((paths.distance[end] + (1 - target.ratio) * road.length_m, end))

    if not candidates:
        return None
    road_m, last_vertex = min(candidates, key=lambda candidate: candidate[0])
    return RouteCost(source.approach_m, road_m, target.approach_m, last_vertex)


def path_to(paths: ShortestPaths, cost: RouteCost) -> list[str]:
    """Vertices passed, in order, on the route cost_to chose."""
    vertices: list[str] = []
    current = cost.last_vertex
    while current is not None:
        vertices.append(current)
        current = paths.previous.get(current)
    vertices.reverse()
    return vertices


def unreachable_vertices(graph: RouteGraph) -> set[str]:
    """Vertices not connected (ignoring direction) to the largest part of
    the network; check before publishing.
    """
    groups = list(nx.weakly_connected_components(graph.network))
    if len(groups) <= 1:
        return set()
    # Largest group is the main network; ties go to the smallest code.
    largest = min(groups, key=lambda g: (-len(g), min(g)))
    return set(graph.network) - largest
