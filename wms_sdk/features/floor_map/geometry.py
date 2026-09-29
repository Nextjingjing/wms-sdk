"""Warehouse outline checks and drawing helpers. Pure functions, no I/O.
Shape validity comes from shapely.

Points are (x_ratio, y_ratio) in 0..1 of the bounding box before rotation,
in order around the outline. No points = the full rectangle.
"""

from decimal import Decimal

try:
    from shapely.geometry import Polygon
except ImportError as error:  # pragma: no cover - depends on the environment
    raise ImportError('floor_map geometry needs shapely: pip install "wms-sdk[floor_map]"') from error

Point = tuple[Decimal, Decimal]


def polygon_error(points: list[Point]) -> str | None:
    """Why an outline is invalid, or None if it is fine."""
    if not points:
        return None
    if len(points) != 4:
        return "an outline needs exactly 4 points"
    if len(set(points)) != 4:
        return "outline corners repeat"
    # shapely works in float; ratios have 6 decimals, well within float precision.
    polygon = Polygon([(float(x), float(y)) for x, y in points])
    if polygon.area == 0:
        return "outline has no area"
    if not polygon.is_valid:
        return "outline edges cross"
    return None


def to_clip_path(points: list[Point]) -> str | None:
    """CSS clip-path for the outline, or None for the full rectangle."""
    if not points:
        return None
    corners = ", ".join(f"{_percent(x)} {_percent(y)}" for x, y in points)
    return f"polygon({corners})"


def _percent(value: Decimal) -> str:
    text = format((value * 100).quantize(Decimal("0.0001")).normalize(), "f")
    return f"{text}%"
