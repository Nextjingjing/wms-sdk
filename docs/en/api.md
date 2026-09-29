# API reference

[ภาษาไทย](../th/api.md) | **English**

Functions and classes a factory project may use. For tables (models) see [schema.md](schema.md).

## Start-up

### `wms_sdk.metadata`

| Name | |
|---|---|
| `metadata` | `Base.metadata` after importing every core table; use with Alembic / `create_all` |

### `wms_sdk.checks`

| Name | |
|---|---|
| `verify_factory(session) -> None` | call at start-up, after importing the factory's models. Raises `NotImplementedError` if an interface is missing, `LookupNotSeeded` if a lookup table is empty |

### `wms_sdk.core.db`

| Name | |
|---|---|
| `Base` | declarative base with the constraint naming convention |
| `Lookup` | subclass to mark a lookup table (adds no columns; declare `code` and `name`) |
| `NAMING_CONVENTION` | name patterns for pk / fk / uq / ix / ck |

### `wms_sdk.core.interface`

| Name | |
|---|---|
| `Interface` | base of interfaces; a factory subclasses `XBase` together with `Base` |
| `Interface.implementation()` | the factory's implementing class, or raises `NotImplementedError` |
| `Interface.roots` | every SDK interface |
| `extra_table_args` | tuple of the factory's constraints (instead of `__table_args__`) |
| `get_row(session, interface, key)` | load an interface row by key; raises `NotSet` if missing |

Interfaces: `ProductPropertiesBase`, `ZonePropertiesBase`, `LocationPropertiesBase`, `PalletBase`; with the tasks feature also `TaskBase`

## Events

### `wms_sdk.modules.events.capture`

| Name | |
|---|---|
| `install_capture(session_factory) -> None` | install change capture on a `sessionmaker`; call once |
| `start_operation(session, actor) -> UUID` | start one action; `actor` = username or `None` |
| `record_event(session, event_type, payload, destinations=()) -> EventLog` | record a business event; `destinations` add outbox rows |

Flushing without `start_operation` → `RuntimeError`.

### `wms_sdk.modules.events.receive`

| Name | |
|---|---|
| `receive_message(session, source, message_id, message_type, payload) -> bool` | store an incoming message in the inbox; `False` if already received |

### Models

`wms_sdk.modules.events.models`: `EventLog`, `Outbox`, `Inbox`

## Stock and QC

### `wms_sdk.modules.inventory.events`

`PalletEvent` (StrEnum): `LOADED`, `PUTAWAY`, `MOVED`, `PICKED`, `ADJUSTED`, `SHIPPED`, `RETURNED`, `RETIRED` → values `pallet.<verb>`

### `wms_sdk.modules.inventory.qc`

| Name | |
|---|---|
| `QcStatus` | `WAITING`, `LOCKED`, `PASSED` |
| `QC_TRANSITIONS` | allowed status changes |
| `QcEvent` | `PASSED` = `pallet.qc_passed`, `LOCKED` = `pallet.qc_locked` |
| `set_qc_status(session, pallet, new, reason=None) -> None` | change QC status; `LOCKED` requires `reason` |
| `ensure_shippable(pallet) -> None` | raises `NotShippable` unless `PASSED` |
| `InvalidQcTransition` | a change not in `QC_TRANSITIONS` |
| `MissingLockReason` | locking without a reason |
| `NotShippable` | shipping a pallet that has not passed QC |

### Properties

| Name | |
|---|---|
| `wms_sdk.modules.master_data.repository.get_product_properties(session, sku)` | raises `NotSet` if missing |
| `wms_sdk.modules.storage.repository.get_zone_properties(session, plant_code, warehouse_code, zone_code)` | raises `NotSet` if missing |
| `wms_sdk.modules.storage.repository.get_location_properties(session, location_code)` | raises `NotSet` if missing |

## Features

### `wms_sdk.features.brand`

`Brand` (lookup), `HasBrand` (mixin adding `brand_code`)

### `wms_sdk.features.machines`

`MachineGroup` (lookup), `Machine`, `ProductSourceMachine`

### `wms_sdk.features.floor_map`

| Name | |
|---|---|
| `models`: `FloorImage`, `WarehouseMap`, `WarehouseMapPoint`, `LocationMap`, `RowDirection` | |
| `geometry.polygon_error(points) -> str \| None` | validate a warehouse outline |
| `geometry.to_clip_path(points) -> str \| None` | CSS clip-path |
| `builder.ColumnLayout`, `builder.plan_rows(layout)`, `builder.cells(layout, row)`, `builder.row_size(layout)` | lay out a column's rows and pallet positions |
| `builder.snap(x, y, neighbours, threshold) -> Snapped` | snap a dragged point to nearby lines |
| `repository.save_column(session, *, plant_code, warehouse_code, zone_code, layout, code_of, label_gap=0, properties_of=None, previous_codes=()) -> list[str]` | save a column's locations and drawings |
| `repository.retire_locations(session, codes)` | soft-delete locations; raises `LocationInUse` if any holds a pallet |

### `wms_sdk.features.routing`

| Name | |
|---|---|
| `models`: `RouteMap`, `RouteVertex`, `RouteEdge`, `AccessPoint` | tables |
| `models`: `RouteStatus`, `VertexType`, `DistanceSource`, `AccessSide`, `RoadSide` | StrEnums |
| `repository.published_route_map(session, plant_code, warehouse_code)` | the published revision, or `NotSet` |
| `repository.load_graph(session, route_map) -> RouteGraph` | load that revision's edges |
| `repository.access_position(route_map, point) -> AccessPosition` | turn an `AccessPoint` into a road position |
| `repository.publish(session, route_map, actor)` | publish a draft; archives the previous one; raises `InvalidRouteStatus` |
| `graph.build_graph(edges) -> RouteGraph` | graph from `Edge`s |
| `graph.shortest_from(graph, source) -> ShortestPaths` | Dijkstra from a lane mouth |
| `graph.cost_to(graph, paths, target) -> RouteCost \| None` | distance to a lane mouth (`total_m`) |
| `graph.path_to(paths, cost) -> list[str]` | vertices passed |
| `graph.layout_road(start, end, start_clearance_m, end_clearance_m, mouths) -> RoadLayout` | place lane mouths on a road |
| `graph.offset_ratio(offset_m, calculated_length_m) -> Decimal` | ratio from the road start |
| `graph.road_side_of(start, end, point) -> RoadSide \| None` | side of a point relative to a road |
| `graph.road_of(a, b) -> (start, end)` | a road's key (smaller code first) |
| `graph.unreachable_vertices(graph) -> set[str]` | vertices not connected to the main network |

### `wms_sdk.features.tasks`

| Name | |
|---|---|
| `models`: `TaskType`, `TaskStatus` (lookups), `TaskBase` (interface) | |
| `TaskBase.active_statuses`, `reservation_columns`, `transitions` | factory configuration |
| `repository.set_task_status(session, task, new) -> None` | change status (also for new tasks); records `task.status_changed`; raises `InvalidTaskStatus` |

### `wms_sdk.features.map_file`

| Name | |
|---|---|
| `export_map(session, plant_code, warehouse_code, path, *, image_root=None) -> MapSummary` | write one warehouse, its pictures and its published route map to a `.wmsmap` file; read-only |
| `import_map(session, path, *, image_root=None, properties=True) -> MapSummary` | create that warehouse here and copy its pictures into `image_root`; needs an operation; records `map_file.imported` |
| `MapSummary` | `plant_code`, `warehouse_code`, `zones`, `locations`, `images` (paths written), `route_revision` |
| `FORMAT_VERSION` | version of the file format this SDK reads and writes |

## Testing

### `wms_sdk.testing.sqlite`

| Name | |
|---|---|
| `create_sqlite_engine(url="sqlite://") -> Engine` | SQLite that accepts the SDK schema (FKs on, `ISJSON`, `messaging` schema) |

### `wms_sdk.testing`

| Name | |
|---|---|
| `create_test_engine(name="wms") -> Engine` | engine for one test database, no tables: in-memory SQLite, or a fresh SQL Server database `wms_test_<name>` when `WMS_TEST_MSSQL_URL` is set |
| `mssql.create_mssql_test_engine(url, schemas=("messaging",)) -> Engine` | drop and recreate the database in `url`, create `schemas`; refuses names without "test" |

## All exceptions

| Exception | From | When |
|---|---|---|
| `NotSet` | `wms_sdk.core.errors` | the requested properties row / route map does not exist |
| `LookupNotSeeded` | `wms_sdk.core.errors` | a lookup table is empty at `verify_factory` |
| `NotImplementedError` | built-in | no factory implements an interface |
| `TypeError` | built-in | an interface implemented twice, or `__table_args__` in an implementation |
| `RuntimeError` | built-in | flush without `start_operation` |
| `InvalidQcTransition`, `MissingLockReason`, `NotShippable` | `wms_sdk.modules.inventory.qc` | QC |
| `LocationInUse` | `wms_sdk.features.floor_map.repository` | retiring a location that still holds a pallet |
| `InvalidTaskStatus` | `wms_sdk.features.tasks.repository` | a status change not in the factory's `transitions` |
| `InvalidRouteStatus` | `wms_sdk.features.routing.repository` | publishing a revision that is not a draft |
| `WarehouseExists`, `LocationCodeTaken`, `PropertiesMismatch`, `UnsupportedMapFile` (all `MapFileError`) | `wms_sdk.features.map_file` | importing a `.wmsmap` file |
