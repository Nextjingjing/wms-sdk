# Optional features

[ภาษาไทย](../th/features.md) | **English**

A feature has tables only when the factory imports it. Not imported = no tables, no error. Lookup tables of enabled features must be seeded (`verify_factory` checks).

| Feature | Enable with | Tables |
|---|---|---|
| machines | `import wms_sdk.features.machines` | `machine_groups`, `machines`, `product_source_machines` |
| brand | `HasBrand` in `ProductProperties` | `brands` + column `brand_code` |
| floor_map | `import wms_sdk.features.floor_map.models` | `floor_images`, `warehouse_maps`, `warehouse_map_points`, `location_maps` |
| routing | `import wms_sdk.features.routing.models` | `route_maps`, `route_vertices`, `route_edges`, `location_access_points` |
| tasks | `import wms_sdk.features.tasks.models` | `task_types`, `task_statuses`, `tasks` (interface) |
| map_file | `from wms_sdk.features import map_file` | none: reads and writes floor_map / routing tables |

## machines

Production machines, for warehouses of producing plants. A distribution centre does not need it.

- `machine_groups`: lookup (e.g. HS, FM, CM_PK, YARD)
- `machines`: PK `(plant_code, code)`; machine codes may repeat across plants
- `product_source_machines`: machines that make a product at a plant, PK `(plant_code, sku, machine_code)`. Both FKs share `plant_code`, so the database guarantees the product is made at that plant (`plant_products`) and the machine belongs to the same plant. Removing a product from a plant (`plant_products`) removes its machines too (CASCADE)

## brand

```python
from wms_sdk.features.brand import HasBrand

class ProductProperties(ProductPropertiesBase, HasBrand, Base): ...
```

Adds the lookup table `brands` and the column `product_properties.brand_code` (NOT NULL, FK → brands).

## floor_map: drawing on screen

Stores drawing positions only; nothing about stock. Without it the warehouse works fully, shown as lists instead of a map.

| Table | PK | Holds |
|---|---|---|
| `floor_images` | `code` | a site picture (file path, width / height in pixels). Not tied to a plant: plants on one site share a picture |
| `warehouse_maps` | `(plant_code, warehouse_code)` | the warehouse box on the picture: `x`, `y`, `width`, `height`, `rotation_deg`, a background picture inside it, `metres_per_unit` (scale; NULL = not measured) |
| `warehouse_map_points` | `+ point_no` (1–4) | outline corners as 0–1 ratios of the box before rotation. No points = the full rectangle |
| `location_maps` | `location_code` | the location's box on the warehouse drawing, `row_direction` (up / down / left / right), drawing gaps |

Coordinates are DECIMAL, not FLOAT: positions dragged on screen are saved repeatedly, and FLOAT would drift.

`geometry.py` (needs the `floor_map` extra, which installs [shapely](https://shapely.readthedocs.io/)):

```python
from wms_sdk.features.floor_map.geometry import polygon_error, to_clip_path

polygon_error(points)   # None = fine; otherwise what is wrong (not 4 points, repeated corner, crossing edges, no area)
to_clip_path(points)    # "polygon(0% 0%, 100% 0%, ...)" for CSS clip-path; None = full rectangle
```

The database cannot check the number of points (0 or 4); call `polygon_error` before saving.

Importing from a legacy system: if its old `rotation` used ±720 units (atan2 × 720/π), 720 units = 180°, so divide by 4 for `rotation_deg` (check against real data first). A legacy `type_location` of VR / VL / HB / HT maps to left / right / up / down.

### Map builder (optional helpers)

Build columns of locations the way the reference factory's map editor does: the admin places row 1 of a column and picks a direction; the builder lays out every row and pallet position.

`builder.py` (pure):

```python
from decimal import Decimal
from wms_sdk.features.floor_map.builder import ColumnLayout, cells, plan_rows, snap
from wms_sdk.features.floor_map.models import RowDirection

layout = ColumnLayout(
    origin_x=Decimal(100), origin_y=Decimal(200),   # top-left of row 1
    direction=RowDirection.DOWN,                      # where rows 2, 3, ... go
    rows=5, max_level=3, sub_column=2,
    cell_width=Decimal(10), cell_height=Decimal(8),  # one pallet position
    level_gap=Decimal(1), row_gap=Decimal(5),
)
plan_rows(layout)                    # [RowPlan(row_no, box)]: one box per row (location)
cells(layout, plan_rows(layout)[0])  # [Cell(level, slot, box)]: positions inside a row
snap(x, y, neighbours, threshold)    # pull a dragged point onto nearby x / y lines
```

- Row size = `sub_column x cell_width + gaps` by `max_level x cell_height + gaps`
- Level 1 / slot 1 sit on the side rows come from: level 1 at the bottom when rows go up, slot 1 on the right when rows go left

`repository.py` saves a column:

```python
from wms_sdk.features.floor_map.repository import save_column, retire_locations

codes = save_column(
    session,
    plant_code="C221", warehouse_code="W3", zone_code="1",
    layout=layout,
    code_of=lambda row_no: f"w3-01{row_no:02}",                # the factory's location code format
    properties_of=lambda row, code: MyLocationProperties(...),  # optional
    previous_codes=[...],                                       # the column's codes before this edit
)
```

- Creates the zone if missing (restores it if retired)
- Creates or restores each location, writes its `location_maps` row and the factory's properties
- Retires codes in `previous_codes` that are no longer in the layout (fewer rows)
- Refuses with `LocationInUse`, changing nothing, if a location to retire still holds a pallet
- Records `location_map.column_saved`; needs `start_operation` first

`retire_locations(session, codes)` retires locations (e.g. a deleted column) with the same pallet check.

The reference factory example (`examples/reference_factory/maps.py`) wraps this with "mapid" codes (`tl-w3-1-0102`), its column / row / capacity properties, `delete_column`, and a rule that moving a column to another zone requires deleting it first (its codes change).

Runnable: [`examples/reference_factory/maps.py`](../../examples/reference_factory/maps.py) is used by [`examples/cookbook/site.py`](../../examples/cookbook/site.py) to draw every column of the cookbook.

## routing: forklift roads and distances

Computes the distance a forklift really drives, e.g. to pick the nearest free location or order a worklist to minimise driving.

`graph.py` and `repository.py` need the `routing` extra, which installs [networkx](https://networkx.org/): it provides Dijkstra and connectivity; the SDK adds lane mouths in the middle of roads, which networkx does not model.

### Structure

```
route_maps (plant, warehouse, revision_no, status)
 ├─ route_vertices   points: corner / junction / gate / dock, clearance_m
 ├─ route_edges      one direction of a road (from_code → to_code), distance_m
 └─ location_access_points
        this location is entered from road (road_start_code, road_end_code)
        at offset_ratio (0 = road start, 1 = end), on the left / right side
        putaway allowed? pick allowed? distance from the road into the lane
```

- A road is identified by its two vertices; its start is the smaller code. A two-way road = two edge rows
- A lane mouth is not a vertex: it sits on a road at a ratio of its length
- Keep vertex codes in one letter case (SQL Server compares by collation, usually case-insensitive; Python compares ordinally)
- An access point's `side` is `front` / `back` (lanes that can be entered from both ends)

### Draft and published

- Each warehouse has at most one `draft` and one `published` revision (enforced by the database)
- Only drafts are edited; routing uses the published revision only
- `publish()` archives the previous published revision and records a `route_map.published` event
- Deleting a draft goes in this order: `location_access_points` → `route_edges` → `route_vertices` → `route_maps` (no CASCADE: SQL Server refuses multiple cascade paths into one table)

```python
from wms_sdk.features.routing.repository import publish

start_operation(session, actor="admin")
publish(session, draft_map, actor="admin")     # raises InvalidRouteStatus unless it is a draft
session.commit()
```

### Distances

```python
from wms_sdk.features.routing.graph import cost_to, path_to, shortest_from
from wms_sdk.features.routing.repository import access_position, load_graph, published_route_map

route_map = published_route_map(session, "C221", "W3")    # NotSet if none
graph = load_graph(session, route_map)

source = access_position(route_map, source_point)        # AccessPoint → AccessPosition
paths = shortest_from(graph, source)                     # one Dijkstra run

for point in candidate_points:                           # thousands of targets are fine
    cost = cost_to(graph, paths, access_position(route_map, point))
    if cost is not None:
        print(point.location_code, cost.total_m)

vertices = path_to(paths, best_cost)                     # e.g. ["B", "C"], vertices passed
```

`cost.total_m` = from the source lane out to the road + along roads + into the target lane. The lane distance is the point's `approach_override_m`, or the route map's `default_approach_m`.

### Placing lane mouths on a road

```python
from wms_sdk.features.routing.graph import LaneMouth, layout_road, offset_ratio

layout = layout_road(start_xy, end_xy, start_clearance_m, end_clearance_m, mouths)
for placed in layout.mouths:
    ratio = offset_ratio(placed.offset_m, layout.calculated_length_m)
    # placed.road_side → AccessPoint.road_side, ratio → AccessPoint.offset_ratio
```

Distances are estimates: offset = start clearance + widths of the lanes before + half this lane's width. Road length = both clearances + the wider side's total lane width. If the road is measured and `distance_m` entered by hand (`distance_source = manual`), mouths move proportionally.

### Check before publishing

```python
from wms_sdk.features.routing.graph import unreachable_vertices

unreachable_vertices(graph)   # vertices not connected to the main network (empty set = good)
```

Runnable: [`examples/cookbook/map_and_routing.py`](../../examples/cookbook/map_and_routing.py) draws a road, publishes it and finds the nearest free location (see [Examples](examples.md#map-and-routing)).

## tasks: work and reservations

Forklift work, QC checks, dispatch: one `tasks` table for every kind of work. Each factory's work differs, so the SDK fixes only the shape.

| | The SDK fixes | The factory decides |
|---|---|---|
| Columns | `id` (task number), `task_type_code`, `status_code`, timestamps | everything else: assigned role, pallet, from / to, vehicle ... |
| Types | lookup `task_types` | seeds its own (e.g. putaway, pick, dispatch, qc_check) |
| Statuses | lookup `task_statuses` | seeds its own, lists which count as not finished (`active_statuses`) |
| Status changes | `set_task_status()` checks them and records `task.status_changed` | the allowed changes (`transitions`) |
| Reservations | a unique index over active tasks | which columns reserve a place (`reservation_columns`) |

```python
from wms_sdk.features.tasks.models import TaskBase

class Task(TaskBase, Base):
    active_statuses = ("open", "in_progress")
    reservation_columns = ("to_location_code", "to_level_no", "to_slot_no")
    transitions = {
        None: {"open"},                         # a new task starts open
        "open": {"in_progress", "cancelled"},
        "in_progress": {"done", "cancelled"},
    }

    assigned_role_code: Mapped[str] = mapped_column(String(30), ForeignKey("roles.code"), nullable=False)
    to_location_code: Mapped[str | None] = mapped_column(String(50), ForeignKey("locations.code"))
    ...
```

```python
from wms_sdk.features.tasks.repository import set_task_status

start_operation(session, actor="planner1")
task = Task(task_type_code="putaway", assigned_role_code="Forklift", to_location_code="w1-0101", ...)
set_task_status(session, task, "open")         # adds and flushes: task.id is set
session.commit()
```

- **Reservation:** while a task is in an active status and all its `reservation_columns` are set, no other active task can hold the same values (unique index filtered on `status_code IN (active_statuses)`). A finished or cancelled task frees it. Tasks without a destination (e.g. QC checks) never collide
- `reservation_columns` without `active_statuses` → `TypeError` at import
- A status change not in `transitions` → `InvalidTaskStatus`; a new task must start in a status allowed from `None`
- History (who took it, when it finished) is in `event_log`; no task history table
- The reservation says nothing about pallets already in that place: check that in the application
- The reference factory example (`examples/reference_factory/models.py` `Task`) assigns work to a role, reserves location + level + slot, and keeps a `reference` (e.g. sales order) so a dispatch of many pallets is many tasks with one reference
- Not yet verified on SQL Server: the reservation index uses `IN (...)` in its filter

Runnable: [`examples/cookbook/dispatch_tasks.py`](../../examples/cookbook/dispatch_tasks.py) shows reservations, a refused double booking and a freed position (see [Examples](examples.md#dispatch-and-reservations)).

## map_file: send a warehouse as one file

Draw a warehouse once, then give it to someone else as one `.wmsmap` file. They import it with the SDK and have the warehouse ready, pictures and route map included, without a copy of your database.

```python
from wms_sdk.features.map_file import export_map, import_map

# your side: read-only
export_map(session, "C221", "W1", "W1.wmsmap", image_root="media/")

# their side: same factory models, seeded
start_operation(session, actor="planner1")
import_map(session, "W1.wmsmap", image_root="media/")
session.commit()
```

A `.wmsmap` file is a ZIP:

| Member | Content |
|---|---|
| `manifest.json` | file format version, SDK version, export time, plant and warehouse, the properties columns |
| `map.json` | rows of `plants`, `warehouses`, `zones`, `zone_properties`, `locations`, `location_properties`, `location_maps`, `floor_images`, `warehouse_maps`, `warehouse_map_points`, and the **published** route map with its `route_vertices`, `route_edges`, `location_access_points` |
| `images/<path>` | the floor image and the warehouse background, under the path the database stores |

- The database holds image paths only; `image_root` is the folder those paths are relative to, on each side
- Not exported: pallets, tasks, event history, drafts and archived route maps. The file describes the warehouse, not what is in it
- Values keep their exact precision (decimals are written as text); `created_at` / `updated_at` are set by the importing database
- Both sides must use the same factory models: the same properties columns and the same seeded lookups

Import rules:

| Case | Result |
|---|---|
| The warehouse is already in the database | `WarehouseExists`; nothing is written. Import only creates new warehouses |
| Another warehouse uses one of the location codes | `LocationCodeTaken` (location codes are unique across all warehouses) |
| The properties columns differ from this factory's | `PropertiesMismatch`; pass `properties=False` to import without properties |
| The plant is missing | it is created |
| A floor image with the same code exists | the existing one is kept, its picture is not overwritten |
| The route map | keeps its revision number, stays published; `published_by` is cleared because that user may not exist here |
| An image path outside `image_root` (`..`, absolute) | `UnsupportedMapFile`; nothing is written outside `image_root` |

The import runs inside your operation, so every row is captured in `event_log`, followed by a `map_file.imported` event. Pictures are written only after all rows have been flushed; the caller commits.

Runnable: [`examples/cookbook/share_map.py`](../../examples/cookbook/share_map.py) exports a warehouse with its pictures and routes on it in a second, empty database (see [Examples](examples.md#share-a-warehouse-as-one-file)).
