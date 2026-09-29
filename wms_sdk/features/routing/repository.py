from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.errors import NotSet
from ...modules.events.capture import record_event
from .graph import AccessPosition, Edge, RouteGraph, build_graph
from .models import AccessPoint, RouteEdge, RouteMap, RouteStatus


class InvalidRouteStatus(Exception):
    pass


def published_route_map(session: Session, plant_code: str, warehouse_code: str) -> RouteMap:
    route_map = session.scalars(
        select(RouteMap).where(
            RouteMap.plant_code == plant_code,
            RouteMap.warehouse_code == warehouse_code,
            RouteMap.status == RouteStatus.PUBLISHED,
        )
    ).one_or_none()
    if route_map is None:
        raise NotSet(f"warehouse {plant_code}/{warehouse_code} has no published route map")
    return route_map


def load_graph(session: Session, route_map: RouteMap) -> RouteGraph:
    rows = session.scalars(
        select(RouteEdge).where(
            RouteEdge.plant_code == route_map.plant_code,
            RouteEdge.warehouse_code == route_map.warehouse_code,
            RouteEdge.revision_no == route_map.revision_no,
        )
    )
    return build_graph([Edge(r.from_code, r.to_code, float(r.distance_m)) for r in rows])


def access_position(route_map: RouteMap, point: AccessPoint) -> AccessPosition:
    approach = point.approach_override_m
    if approach is None:
        approach = route_map.default_approach_m
    return AccessPosition(
        road=(point.road_start_code, point.road_end_code),
        ratio=float(point.offset_ratio),
        approach_m=float(approach),
    )


def publish(session: Session, route_map: RouteMap, actor: str | None) -> None:
    """Publish a draft; the previously published revision is archived."""
    if route_map.status is not RouteStatus.DRAFT:
        raise InvalidRouteStatus(f"only a draft can be published, not {route_map.status}")
    try:
        current = published_route_map(session, route_map.plant_code, route_map.warehouse_code)
    except NotSet:
        current = None
    if current is not None:
        current.status = RouteStatus.ARCHIVED
        # Flush first: the unique index allows one published revision at a time.
        session.flush()
    route_map.status = RouteStatus.PUBLISHED
    route_map.published_at = datetime.now(UTC).replace(tzinfo=None)
    route_map.published_by = actor
    record_event(
        session,
        "route_map.published",
        {
            "plant_code": route_map.plant_code,
            "warehouse_code": route_map.warehouse_code,
            "revision_no": route_map.revision_no,
            "archived": None if current is None else current.revision_no,
        },
    )
