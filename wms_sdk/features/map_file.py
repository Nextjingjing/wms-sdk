"""Portable warehouse map: one `.wmsmap` file that rebuilds a warehouse in
another database, pictures included.

A `.wmsmap` file is a ZIP holding

- `manifest.json`: file format version, SDK version, export time, warehouse
- `map.json`: the rows of the warehouse, table by table (plant, warehouse,
  zones, locations, their drawings, floor image, warehouse outline, the
  published route map with its vertices, edges and access points, and the
  factory's zone_properties / location_properties)
- `images/<path>`: the floor image and the warehouse background, stored under
  the same path the database holds

The database stores only image paths, so both sides name the folder the paths
are relative to (`image_root`). Stock, tasks and history are not exported:
the file describes the warehouse, not what is in it.

Both sides must use the same factory models (same property columns and
seeded lookups); the floor_map and routing features are imported by this
module.
"""

import json
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import DateTime, Enum, Numeric, inspect, select
from sqlalchemy.orm import Session

from .. import __version__
from ..modules.events.capture import record_event
from ..modules.storage.models import (
    Location,
    LocationPropertiesBase,
    Warehouse,
    Zone,
    ZonePropertiesBase,
)
from ..shared.models.plant import Plant
from .floor_map.models import FloorImage, LocationMap, WarehouseMap, WarehouseMapPoint
from .routing.models import AccessPoint, RouteEdge, RouteMap, RouteStatus, RouteVertex

FORMAT = "wmsmap"
FORMAT_VERSION = 1
# Set by the database of whoever imports the file.
SKIPPED_COLUMNS = {"created_at", "updated_at"}


class MapFileError(Exception):
    """A `.wmsmap` file cannot be imported."""


class UnsupportedMapFile(MapFileError):
    """Not a `.wmsmap` file, or one written by an incompatible SDK version."""


class WarehouseExists(MapFileError):
    """The warehouse is already in this database; import only creates new ones."""


class LocationCodeTaken(MapFileError):
    """Location codes are unique across all warehouses, and some are in use."""


class PropertiesMismatch(MapFileError):
    """The file's properties columns differ from this factory's implementation."""


@dataclass(frozen=True)
class MapSummary:
    plant_code: str
    warehouse_code: str
    zones: int
    locations: int
    images: list[str]
    route_revision: int | None


def export_map(
    session: Session,
    plant_code: str,
    warehouse_code: str,
    path: str | Path,
    *,
    image_root: str | Path | None = None,
) -> MapSummary:
    """Write one warehouse to a `.wmsmap` file. `image_root` is the folder the
    stored image paths are relative to; needed when the warehouse has pictures.
    Only reads the database.
    """
    warehouse = session.get(Warehouse, (plant_code, warehouse_code))
    if warehouse is None:
        raise ValueError(f"warehouse {plant_code}/{warehouse_code} does not exist")
    in_warehouse = {"plant_code": plant_code, "warehouse_code": warehouse_code}

    zones = _select(session, Zone, **in_warehouse)
    locations = _select(session, Location, **in_warehouse)
    codes = [location.code for location in locations]
    zone_properties = ZonePropertiesBase.implementation()
    location_properties = LocationPropertiesBase.implementation()

    warehouse_map = session.get(WarehouseMap, (plant_code, warehouse_code))
    floor_image = warehouse_map and session.get(FloorImage, warehouse_map.floor_image_code)
    route_map = session.scalars(
        select(RouteMap).filter_by(**in_warehouse, status=RouteStatus.PUBLISHED)
    ).one_or_none()
    route = {**in_warehouse, "revision_no": route_map.revision_no} if route_map else None

    tables = {
        "plants": [session.get(Plant, plant_code)],
        "warehouses": [warehouse],
        "zones": zones,
        "zone_properties": _select(session, zone_properties, **in_warehouse),
        "locations": locations,
        "location_properties": _select_in(session, location_properties, codes),
        "location_maps": _select_in(session, LocationMap, codes),
        "floor_images": [floor_image] if floor_image else [],
        "warehouse_maps": [warehouse_map] if warehouse_map else [],
        "warehouse_map_points": _select(session, WarehouseMapPoint, **in_warehouse),
        "route_maps": [route_map] if route_map else [],
        "route_vertices": _select(session, RouteVertex, **route) if route else [],
        "route_edges": _select(session, RouteEdge, **route) if route else [],
        "location_access_points": _select(session, AccessPoint, **route) if route else [],
    }
    images = [
        image
        for image in [
            floor_image and floor_image.image_path,
            warehouse_map and warehouse_map.background_path,
        ]
        if image
    ]
    if images and image_root is None:
        raise ValueError(f"the warehouse has pictures {images}: pass image_root")

    manifest = {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "sdk_version": __version__,
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "plant_code": plant_code,
        "warehouse_code": warehouse_code,
        "properties_columns": {
            "zone_properties": _columns(zone_properties),
            "location_properties": _columns(location_properties),
        },
    }
    data = {name: [_encode(row) for row in rows] for name, rows in tables.items()}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("map.json", json.dumps(data, ensure_ascii=False, indent=2))
        for image in images:
            archive.write(Path(image_root) / _safe_path(image), f"images/{image}")

    return MapSummary(
        plant_code,
        warehouse_code,
        len(zones),
        len(locations),
        images,
        route_map.revision_no if route_map else None,
    )


def import_map(
    session: Session,
    path: str | Path,
    *,
    image_root: str | Path | None = None,
    properties: bool = True,
) -> MapSummary:
    """Create the warehouse in a `.wmsmap` file, with its route map ready to
    use, and copy its pictures into `image_root`.

    - raises WarehouseExists if the warehouse is already here, and
      LocationCodeTaken if another warehouse uses one of its location codes
    - the plant is created if missing
    - the route map keeps its revision number; `published_by` is cleared,
      since that user may not exist here
    - `properties=False` skips zone_properties / location_properties, e.g.
      when this factory's properties columns differ (else PropertiesMismatch)
    - a floor image already here (same code) is kept, not replaced

    Needs an operation started; the caller commits. Pictures are written only
    after every row has been flushed.
    """
    with zipfile.ZipFile(path) as archive:
        manifest = _read_json(archive, "manifest.json")
        if manifest.get("format") != FORMAT or manifest.get("format_version") != FORMAT_VERSION:
            raise UnsupportedMapFile(
                f"{path}: expected {FORMAT} version {FORMAT_VERSION}, got "
                f"{manifest.get('format')} version {manifest.get('format_version')}"
            )
        data = _read_json(archive, "map.json")
        image_bytes = {
            name.removeprefix("images/"): archive.read(name)
            for name in archive.namelist()
            if name.startswith("images/") and not name.endswith("/")
        }

    plant_code, warehouse_code = manifest["plant_code"], manifest["warehouse_code"]
    if session.get(Warehouse, (plant_code, warehouse_code)) is not None:
        raise WarehouseExists(f"warehouse {plant_code}/{warehouse_code} already exists")
    codes = [row["code"] for row in data["locations"]]
    taken = session.scalars(select(Location.code).where(Location.code.in_(codes))).all()
    if taken:
        raise LocationCodeTaken(f"location codes already in use: {sorted(taken)}")
    if properties:
        _check_properties(manifest["properties_columns"])
    if image_bytes and image_root is None:
        raise ValueError(f"the file has pictures {sorted(image_bytes)}: pass image_root")

    new_plant = session.get(Plant, plant_code) is None
    new_floor_images = [
        row for row in data["floor_images"] if session.get(FloorImage, row["code"]) is None
    ]
    new_images = [row["image_path"] for row in new_floor_images] + [
        row["background_path"] for row in data["warehouse_maps"] if row["background_path"]
    ]
    missing = [image for image in new_images if image not in image_bytes]
    if missing:
        raise UnsupportedMapFile(f"{path}: pictures missing from the file: {missing}")

    # Parents before children; each step is flushed because the models have
    # no relationships from which SQLAlchemy could order the inserts.
    steps = [
        ("plants", Plant, new_plant),
        ("warehouses", Warehouse, True),
        ("zones", Zone, True),
        ("zone_properties", ZonePropertiesBase.implementation(), properties),
        ("locations", Location, True),
        ("location_properties", LocationPropertiesBase.implementation(), properties),
        ("location_maps", LocationMap, True),
        ("floor_images", FloorImage, bool(new_floor_images)),
        ("warehouse_maps", WarehouseMap, True),
        ("warehouse_map_points", WarehouseMapPoint, True),
        ("route_maps", RouteMap, True),
        ("route_vertices", RouteVertex, True),
        ("route_edges", RouteEdge, True),
        ("location_access_points", AccessPoint, True),
    ]
    for table, model, wanted in steps:
        if not wanted:
            continue
        for row in data[table]:
            instance = _decode(model, row)
            if isinstance(instance, RouteMap):
                instance.published_by = None
            session.add(instance)
        session.flush()

    for image in new_images:
        target = Path(image_root) / _safe_path(image)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(image_bytes[image])

    route = data["route_maps"][0]["revision_no"] if data["route_maps"] else None
    record_event(
        session,
        "map_file.imported",
        {
            "plant_code": plant_code,
            "warehouse_code": warehouse_code,
            "exported_at": manifest["exported_at"],
            "sdk_version": manifest["sdk_version"],
            "route_revision": route,
        },
    )
    return MapSummary(
        plant_code, warehouse_code, len(data["zones"]), len(codes), new_images, route
    )


def _select(session: Session, model: type, **filters: Any) -> list:
    return list(session.scalars(select(model).filter_by(**filters).order_by(*_key(model))))


def _select_in(session: Session, model: type, codes: list[str]) -> list:
    if not codes:
        return []
    column = model.location_code
    return list(session.scalars(select(model).where(column.in_(codes)).order_by(*_key(model))))


def _key(model: type) -> list:
    return list(inspect(model).primary_key)


def _columns(model: type) -> list[str]:
    return sorted(
        attr.key for attr in inspect(model).column_attrs if attr.key not in SKIPPED_COLUMNS
    )


def _encode(row: Any) -> dict[str, Any]:
    out = {}
    for attr in inspect(type(row)).column_attrs:
        if attr.key in SKIPPED_COLUMNS:
            continue
        value = getattr(row, attr.key)
        if isinstance(value, Decimal):
            value = str(value)  # exact: JSON numbers are floats
        elif isinstance(value, datetime):
            value = value.isoformat()
        out[attr.key] = value
    return out


def _decode(model: type, row: dict[str, Any]) -> Any:
    values = {}
    for attr in inspect(model).column_attrs:
        if attr.key not in row:
            continue
        value, column_type = row[attr.key], attr.columns[0].type
        if value is not None:
            if isinstance(column_type, Enum) and column_type.enum_class is not None:
                value = column_type.enum_class(value)
            elif isinstance(column_type, Numeric):
                value = Decimal(value)
            elif isinstance(column_type, DateTime):
                value = datetime.fromisoformat(value)
        values[attr.key] = value
    return model(**values)


def _check_properties(expected: dict[str, list[str]]) -> None:
    for root in (ZonePropertiesBase, LocationPropertiesBase):
        here = _columns(root.implementation())
        there = expected[root.__tablename__]
        if here != there:
            raise PropertiesMismatch(
                f"{root.__tablename__}: file has columns {there}, this factory has {here}; "
                "import with properties=False to skip them"
            )


def _read_json(archive: zipfile.ZipFile, name: str) -> Any:
    try:
        return json.loads(archive.read(name))
    except KeyError:
        raise UnsupportedMapFile(f"not a {FORMAT} file: {name} is missing") from None


def _safe_path(image: str) -> PurePosixPath:
    # Image paths come from the file: never write outside image_root.
    path = PurePosixPath(image)
    if path.is_absolute() or ".." in path.parts or ":" in image:
        raise UnsupportedMapFile(f"image path must be relative, inside image_root: {image!r}")
    return path
