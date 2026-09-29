"""Forklift road network of a warehouse, as revisions. A draft can be edited;
publishing it archives the previous published revision. Only the published
revision is used for routing.

Vertices are road corners, junctions, gates and docks. A road between two
vertices is stored as one edge per allowed direction. Locations are not
vertices: an access point places a location's mouth on a road at a ratio of
the road's length from its start (the vertex with the smaller code).
"""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from ...core.db import Base

Canvas = Numeric(12, 4)
Metres = Numeric(8, 2)


def _enum(cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(
        cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=12,
        values_callable=lambda e: [m.value for m in e],
    )


class RouteStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class VertexType(enum.StrEnum):
    CORNER = "corner"
    JUNCTION = "junction"
    GATE = "gate"
    DOCK = "dock"


class DistanceSource(enum.StrEnum):
    CALCULATED = "calculated"  # from clearances and lane widths
    MANUAL = "manual"  # measured and entered by hand


class AccessSide(enum.StrEnum):
    FRONT = "front"
    BACK = "back"  # for lanes that can be entered from both ends


class RoadSide(enum.StrEnum):
    LEFT = "left"
    RIGHT = "right"


class RouteMap(Base):
    __tablename__ = "route_maps"

    plant_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    warehouse_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    revision_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[RouteStatus] = mapped_column(_enum(RouteStatus, "status"), nullable=False)
    # Distance from road to lane mouth when an access point does not override it.
    default_approach_m: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default="3.00"
    )
    published_at: Mapped[datetime | None] = mapped_column(DATETIME2, nullable=True)
    published_by: Mapped[str | None] = mapped_column(
        String(150), ForeignKey("users.username"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2, nullable=False, server_default=func.sysutcdatetime()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME2,
        nullable=False,
        server_default=func.sysutcdatetime(),
        onupdate=func.sysutcdatetime(),
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["plant_code", "warehouse_code"], ["warehouses.plant_code", "warehouses.code"]
        ),
        CheckConstraint("revision_no >= 1", name="revision_positive"),
        CheckConstraint("default_approach_m >= 0", name="approach_not_negative"),
        CheckConstraint(
            "(status = 'draft' AND published_at IS NULL)"
            " OR (status = 'published' AND published_at IS NOT NULL)"
            " OR status = 'archived'",
            name="published_at_matches_status",
        ),
        # At most one published and one draft revision per warehouse.
        Index(
            "uq_route_maps_published",
            "plant_code",
            "warehouse_code",
            unique=True,
            mssql_where=text("status = 'published'"),
            sqlite_where=text("status = 'published'"),
        ),
        Index(
            "uq_route_maps_draft",
            "plant_code",
            "warehouse_code",
            unique=True,
            mssql_where=text("status = 'draft'"),
            sqlite_where=text("status = 'draft'"),
        ),
    )


class RouteVertex(Base):
    __tablename__ = "route_vertices"

    plant_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    warehouse_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    revision_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    vertex_type: Mapped[VertexType] = mapped_column(
        _enum(VertexType, "vertex_type"), nullable=False
    )
    # Position on the warehouse drawing: for drawing and ordering only, never distances.
    x: Mapped[Decimal] = mapped_column(Canvas, nullable=False)
    y: Mapped[Decimal] = mapped_column(Canvas, nullable=False)
    # Distance from this vertex to the first lane of every road leaving it.
    clearance_m: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default="3.00"
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2, nullable=False, server_default=func.sysutcdatetime()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME2,
        nullable=False,
        server_default=func.sysutcdatetime(),
        onupdate=func.sysutcdatetime(),
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["plant_code", "warehouse_code", "revision_no"],
            ["route_maps.plant_code", "route_maps.warehouse_code", "route_maps.revision_no"],
        ),
        CheckConstraint("clearance_m >= 0", name="clearance_not_negative"),
    )


_VERTEX = ["route_vertices.plant_code", "route_vertices.warehouse_code", "route_vertices.revision_no", "route_vertices.code"]


class RouteEdge(Base):
    """One direction of a road. A two-way road has two rows."""

    __tablename__ = "route_edges"

    plant_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    warehouse_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    revision_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_code: Mapped[str] = mapped_column(String(30), primary_key=True)
    to_code: Mapped[str] = mapped_column(String(30), primary_key=True)
    distance_m: Mapped[Decimal] = mapped_column(Metres, nullable=False)
    distance_source: Mapped[DistanceSource] = mapped_column(
        _enum(DistanceSource, "distance_source"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2, nullable=False, server_default=func.sysutcdatetime()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME2,
        nullable=False,
        server_default=func.sysutcdatetime(),
        onupdate=func.sysutcdatetime(),
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["plant_code", "warehouse_code", "revision_no", "from_code"],
            _VERTEX,
            name="fk_route_edges_from_vertex",
        ),
        ForeignKeyConstraint(
            ["plant_code", "warehouse_code", "revision_no", "to_code"],
            _VERTEX,
            name="fk_route_edges_to_vertex",
        ),
        CheckConstraint("from_code <> to_code", name="not_a_loop"),
        CheckConstraint("distance_m > 0", name="distance_positive"),
    )


class AccessPoint(Base):
    """Where a location's mouth meets a road, in one route revision."""

    __tablename__ = "location_access_points"

    plant_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    warehouse_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    revision_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_code: Mapped[str] = mapped_column(String(50), primary_key=True)
    side: Mapped[AccessSide] = mapped_column(_enum(AccessSide, "side"), primary_key=True)
    # The road, by its two vertices; start is the smaller code.
    road_start_code: Mapped[str] = mapped_column(String(30), nullable=False)
    road_end_code: Mapped[str] = mapped_column(String(30), nullable=False)
    # Which side of the road, looking from start to end. Derived from the
    # drawing when saved, not entered by users.
    road_side: Mapped[RoadSide] = mapped_column(_enum(RoadSide, "road_side"), nullable=False)
    # Position along the road, 0 = start, 1 = end.
    offset_ratio: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    allow_putaway: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allow_pick: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # NULL = use the route map's default_approach_m.
    approach_override_m: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2, nullable=False, server_default=func.sysutcdatetime()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME2,
        nullable=False,
        server_default=func.sysutcdatetime(),
        onupdate=func.sysutcdatetime(),
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["plant_code", "warehouse_code", "revision_no"],
            ["route_maps.plant_code", "route_maps.warehouse_code", "route_maps.revision_no"],
        ),
        # Through locations' (code, plant, warehouse) key: the location must be
        # in the same warehouse as the route map.
        ForeignKeyConstraint(
            ["location_code", "plant_code", "warehouse_code"],
            ["locations.code", "locations.plant_code", "locations.warehouse_code"],
            name="fk_location_access_points_location",
        ),
        ForeignKeyConstraint(
            ["plant_code", "warehouse_code", "revision_no", "road_start_code"],
            _VERTEX,
            name="fk_location_access_points_road_start",
        ),
        ForeignKeyConstraint(
            ["plant_code", "warehouse_code", "revision_no", "road_end_code"],
            _VERTEX,
            name="fk_location_access_points_road_end",
        ),
        # Keep vertex codes in one letter case: SQL Server compares with the
        # column collation (usually case-insensitive), Python ordinally.
        CheckConstraint("road_start_code < road_end_code", name="road_start_is_smaller"),
        CheckConstraint("offset_ratio BETWEEN 0 AND 1", name="offset_ratio_range"),
        CheckConstraint("allow_putaway = 1 OR allow_pick = 1", name="allows_something"),
        CheckConstraint(
            "approach_override_m IS NULL OR approach_override_m >= 0",
            name="approach_not_negative",
        ),
        # Access points of one location; also backs the location FK.
        Index(None, "location_code", "plant_code", "warehouse_code"),
    )
