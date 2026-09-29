import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    SmallInteger,
    String,
    Unicode,
    func,
)
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from ...core.db import Base

# Positions and sizes are in pixels of the picture they are drawn on. DECIMAL,
# not FLOAT: values dragged on screen are written back repeatedly, and FLOAT
# drift would make equal positions compare unequal.
Canvas = Numeric(12, 4)


class RowDirection(enum.StrEnum):
    """Which way a location's rows run on screen, from its label."""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class FloorImage(Base):
    """A picture of a site; warehouse outlines are drawn on it. Not tied to
    a plant: plants sharing one site share one picture.
    """

    __tablename__ = "floor_images"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False)
    # Path in the application's file store; the database holds no image bytes.
    image_path: Mapped[str] = mapped_column(Unicode(500), nullable=False)
    width: Mapped[Decimal] = mapped_column(Canvas, nullable=False)
    height: Mapped[Decimal] = mapped_column(Canvas, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DATETIME2, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2, nullable=False, server_default=func.sysutcdatetime()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME2,
        nullable=False,
        server_default=func.sysutcdatetime(),
        onupdate=func.sysutcdatetime(),
    )

    __table_args__ = (CheckConstraint("width > 0 AND height > 0", name="size_positive"),)


class WarehouseMap(Base):
    """Where a warehouse is drawn on its floor image. One row per warehouse."""

    __tablename__ = "warehouse_maps"

    plant_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    warehouse_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    floor_image_code: Mapped[str] = mapped_column(
        String(30), ForeignKey("floor_images.code"), nullable=False
    )
    # Bounding box on the floor image, before rotation.
    x: Mapped[Decimal] = mapped_column(Canvas, nullable=False)
    y: Mapped[Decimal] = mapped_column(Canvas, nullable=False)
    width: Mapped[Decimal] = mapped_column(Canvas, nullable=False)
    height: Mapped[Decimal] = mapped_column(Canvas, nullable=False)
    rotation_deg: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default="0"
    )
    # Picture drawn inside the warehouse outline; NULL = none.
    background_path: Mapped[str | None] = mapped_column(Unicode(500), nullable=True)
    # Metres per pixel of the warehouse drawing, once measured; NULL = not calibrated.
    metres_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
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
        CheckConstraint("width > 0 AND height > 0", name="size_positive"),
        CheckConstraint("rotation_deg >= -360 AND rotation_deg <= 360", name="rotation_range"),
        CheckConstraint(
            "metres_per_unit IS NULL OR metres_per_unit > 0", name="scale_positive"
        ),
    )


class WarehouseMapPoint(Base):
    """Corner of a warehouse outline, as a 0..1 ratio of its bounding box
    before rotation. A warehouse with no points is drawn as the full box;
    otherwise it has exactly 4 (check with geometry.polygon_error).
    """

    __tablename__ = "warehouse_map_points"

    plant_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    warehouse_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    # Corners in order around the outline.
    point_no: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    x_ratio: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    y_ratio: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
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
            ["plant_code", "warehouse_code"],
            ["warehouse_maps.plant_code", "warehouse_maps.warehouse_code"],
        ),
        CheckConstraint("point_no BETWEEN 1 AND 4", name="point_no_range"),
        CheckConstraint(
            "x_ratio BETWEEN 0 AND 1 AND y_ratio BETWEEN 0 AND 1", name="ratio_range"
        ),
    )


class LocationMap(Base):
    """Where a location is drawn inside its warehouse drawing."""

    __tablename__ = "location_maps"

    location_code: Mapped[str] = mapped_column(
        String(50), ForeignKey("locations.code"), primary_key=True
    )
    x: Mapped[Decimal] = mapped_column(Canvas, nullable=False)
    y: Mapped[Decimal] = mapped_column(Canvas, nullable=False)
    width: Mapped[Decimal] = mapped_column(Canvas, nullable=False)
    height: Mapped[Decimal] = mapped_column(Canvas, nullable=False)
    row_direction: Mapped[RowDirection] = mapped_column(
        Enum(
            RowDirection,
            name="row_direction",
            native_enum=False,
            create_constraint=True,
            length=10,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    # Spacing used when drawing, in pixels (see builder.ColumnLayout). 0 is a
    # real value: no gap.
    row_gap: Mapped[Decimal] = mapped_column(Canvas, nullable=False, server_default="0")
    level_gap: Mapped[Decimal] = mapped_column(Canvas, nullable=False, server_default="0")
    label_gap: Mapped[Decimal] = mapped_column(Canvas, nullable=False, server_default="0")
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
        CheckConstraint("width >= 0 AND height >= 0", name="size_not_negative"),
        CheckConstraint(
            "row_gap >= 0 AND level_gap >= 0 AND label_gap >= 0", name="gaps_not_negative"
        ),
    )
