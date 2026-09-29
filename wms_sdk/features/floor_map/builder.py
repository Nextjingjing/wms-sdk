"""Lay out a column of locations on a warehouse drawing. Pure functions, no I/O.

A column is a lane of `rows` locations; each location (row) holds
`max_level` x `sub_column` pallet positions. The admin places row 1 and
picks the direction the other rows follow; this module computes every
row's box and every position's cell, in pixels of the warehouse drawing.

Coordinates: x grows right, y grows down. A row box's (x, y) is its
top-left corner.
"""

from dataclasses import dataclass
from decimal import Decimal

from .models import RowDirection


@dataclass(frozen=True)
class ColumnLayout:
    origin_x: Decimal  # top-left corner of row 1's box
    origin_y: Decimal
    direction: RowDirection  # where rows 2, 3, ... go from row 1
    rows: int
    max_level: int
    sub_column: int
    cell_width: Decimal  # one pallet position
    cell_height: Decimal
    level_gap: Decimal = Decimal(0)  # between positions inside a row
    row_gap: Decimal = Decimal(0)  # between rows

    def __post_init__(self) -> None:
        if min(self.rows, self.max_level, self.sub_column) < 1:
            raise ValueError("rows, max_level and sub_column must be at least 1")
        if self.cell_width <= 0 or self.cell_height <= 0:
            raise ValueError("cell size must be positive")
        if self.level_gap < 0 or self.row_gap < 0:
            raise ValueError("gaps cannot be negative")


@dataclass(frozen=True)
class Box:
    x: Decimal
    y: Decimal
    width: Decimal
    height: Decimal


@dataclass(frozen=True)
class RowPlan:
    row_no: int
    box: Box


@dataclass(frozen=True)
class Cell:
    level: int
    slot: int
    box: Box


def row_size(layout: ColumnLayout) -> tuple[Decimal, Decimal]:
    """(width, height) of one row box: sub_column cells across, max_level down."""
    width = layout.sub_column * layout.cell_width + (layout.sub_column - 1) * layout.level_gap
    height = layout.max_level * layout.cell_height + (layout.max_level - 1) * layout.level_gap
    return width, height


def plan_rows(layout: ColumnLayout) -> list[RowPlan]:
    """Box of every row, row 1 first."""
    width, height = row_size(layout)
    step_x = {RowDirection.RIGHT: width + layout.row_gap, RowDirection.LEFT: -(width + layout.row_gap)}
    step_y = {RowDirection.DOWN: height + layout.row_gap, RowDirection.UP: -(height + layout.row_gap)}
    dx = step_x.get(layout.direction, Decimal(0))
    dy = step_y.get(layout.direction, Decimal(0))
    return [
        RowPlan(
            row_no=n,
            box=Box(layout.origin_x + (n - 1) * dx, layout.origin_y + (n - 1) * dy, width, height),
        )
        for n in range(1, layout.rows + 1)
    ]


def cells(layout: ColumnLayout, row: RowPlan) -> list[Cell]:
    """Every pallet position of a row. Level 1 and slot 1 sit on the side the
    rows come from: level 1 at the bottom when rows go up, slot 1 on the
    right when rows go left (same as the original map editor this ports).
    """
    result = []
    for level in range(1, layout.max_level + 1):
        level_index = level - 1
        if layout.direction is RowDirection.UP:
            level_index = layout.max_level - level
        for slot in range(1, layout.sub_column + 1):
            slot_index = slot - 1
            if layout.direction is RowDirection.LEFT:
                slot_index = layout.sub_column - slot
            x = row.box.x + slot_index * (layout.cell_width + layout.level_gap)
            y = row.box.y + level_index * (layout.cell_height + layout.level_gap)
            result.append(Cell(level, slot, Box(x, y, layout.cell_width, layout.cell_height)))
    return result


@dataclass(frozen=True)
class Snapped:
    x: Decimal
    y: Decimal
    guide_x: Decimal | None  # the x line snapped to, for drawing a guide
    guide_y: Decimal | None


def snap(
    x: Decimal, y: Decimal, neighbours: list[tuple[Decimal, Decimal]], threshold: Decimal
) -> Snapped:
    """Pull a point being dragged onto the nearest x and y of other rows'
    corners, each axis separately, when within `threshold` pixels.
    """
    best_x = min(
        (nx for nx, _ in neighbours if abs(nx - x) <= threshold), key=lambda nx: abs(nx - x), default=None
    )
    best_y = min(
        (ny for _, ny in neighbours if abs(ny - y) <= threshold), key=lambda ny: abs(ny - y), default=None
    )
    return Snapped(
        x=x if best_x is None else best_x,
        y=y if best_y is None else best_y,
        guide_x=best_x,
        guide_y=best_y,
    )
