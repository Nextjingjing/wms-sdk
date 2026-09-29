# Examples

[ภาษาไทย](../th/examples.md) | **English**

Every example here runs as is, on in-memory SQLite, and `tests/test_examples.py` runs them all, so they stay correct as the SDK changes. Outputs below are copied from real runs.

| Example | Shows |
|---|---|
| [`examples/minimal_factory`](../../examples/minimal_factory) | the smallest factory; walked through in the [Tutorial](tutorial.md) |
| [`examples/reference_factory`](../../examples/reference_factory) | a full factory: every interface with its own columns, every feature enabled |
| [`examples/cookbook`](../../examples/cookbook) | recipes on the reference factory example, below |

All recipes start from [`cookbook/site.py`](../../examples/cookbook/site.py) `open_site()`: plant C221 (TL), warehouse W1, users `planner1` / `forklift1` / `lab1`, products A001 / A002, and two columns of three rows drawn with the map builder (`tl-w1-1-0101`..`0103`, `tl-w1-1-0201`..`0203`).

## Pallet life cycle

```bash
python -m examples.cookbook.pallet_lifecycle
```

Two pallets are loaded and put away through tasks. The lab passes one and locks the other; only the passed one can ship.

```python
# the planner creates a putaway task; its destination is reserved while open
task = Task(task_type_code="putaway", assigned_role_code="Forklift", pallet_code=pallet.code,
            to_location_code=location_code, to_level_no=level_no, to_slot_no=slot_no)
set_task_status(session, task, "open")

# the forklift driver does it
set_task_status(session, task, "in_progress")
pallet.location_code, pallet.level_no, pallet.slot_no = location_code, level_no, slot_no
record_event(session, PalletEvent.PUTAWAY, {"pallet": pallet.code, "to": location_code})
set_task_status(session, task, "done")

# the lab
set_qc_status(session, good, QcStatus.PASSED)
set_qc_status(session, bad, QcStatus.LOCKED, reason="moisture above limit")

# shipping
ensure_shippable(pallet)          # NotShippable unless passed
pallet.location_code = pallet.level_no = pallet.slot_no = None
pallet.left_at = datetime.now(UTC).replace(tzinfo=None)
record_event(session, PalletEvent.SHIPPED, {"pallet": pallet.code, "from": origin}, destinations=["sap"])
```

```
P-0001: put away at tl-w1-1-0101 level 1 slot 1 (task 1)
P-0002: put away at tl-w1-1-0102 level 1 slot 1 (task 2)
P-0002: locked, reason: moisture above limit
P-0001: shipped from tl-w1-1-0101
P-0002: refused: pallet P-0002 is locked, not passed
history of P-0001:
  pallet.loaded      by forklift1
  pallets.inserted   by forklift1
  pallets.updated    by forklift1
  pallet.putaway     by forklift1
  pallet.qc_passed   by lab1
  pallets.updated    by lab1
  pallet.shipped     by forklift1
  pallets.updated    by forklift1
outbox waiting to send: ['sap']
```

The history mixes automatic row changes (`pallets.updated`) and business events (`pallet.putaway`), each with who did it.

## Map and routing

```bash
python -m examples.cookbook.map_and_routing
```

```
    A ────────── B ──── D (dock)
      [col 1] [col 2]           lane mouths of row 1 open onto road A-B
```

A road is drawn in front of the columns, its lane mouths are placed from the drawn location boxes, the road map is published, and the nearest free location to the dock is found.

```python
# place lane mouths on road A-B from the location drawings
mouths = [LaneMouth(code, (box.x + box.width / 2, box.y), LANE_WIDTH_M) for code, box in ...]
layout = layout_road(VERTICES["A"], VERTICES["B"], D(3), D(3), mouths)
# ... add RouteMap, RouteVertex, RouteEdge (length = layout.calculated_length_m), AccessPoint rows
publish(session, draft, actor="planner1")

# nearest free location from the dock
graph = load_graph(session, published_route_map(session, PLANT, WAREHOUSE))
paths = shortest_from(graph, AccessPosition(road=road_of("B", "D"), ratio=1.0, approach_m=0.0))
cost = cost_to(graph, paths, access_position(route_map, point))   # for each access point
path_to(paths, cost)
```

```
road A-B: 8.40 m, mouths at ['3.6', '4.8'] m
unreachable vertices: none
  tl-w1-1-0101: 17.80 m free
  tl-w1-1-0201: 16.60 m occupied
nearest free location: tl-w1-1-0101 (17.80 m, via ['B'])
```

`tl-w1-1-0201` is closer but already holds a pallet, so the next nearest is chosen. Needs the `routing` extra (networkx).

## Dispatch and reservations

```bash
python -m examples.cookbook.dispatch_tasks
```

One sales order becomes one dispatch task per pallet, sharing a `reference`. Each open task reserves its staging position; the database refuses a second task for the same position until the first is finished.

```python
task = Task(task_type_code="dispatch", assigned_role_code="Forklift", pallet_code=pallet_code,
            to_location_code=STAGING, to_level_no=level_no, to_slot_no=1, reference=order)
set_task_status(session, task, "open")
...
except IntegrityError:            # the position is reserved by another open task
    session.rollback()
```

```
SO-100: tasks 1 and 2 reserve tl-w1-1-0203 levels 1 and 2
SO-101: refused, tl-w1-1-0203 level 1 is already reserved
qc_check tasks: 2 open, no reservation
SO-101: task 5 reserves tl-w1-1-0203 level 1 after task 1 is done
tasks of SO-100:
  task 1: P-0001 -> tl-w1-1-0203 L1 (done)
  task 2: P-0002 -> tl-w1-1-0203 L2 (open)
```

QC check tasks have no destination, so they reserve nothing and never collide.

## Share a warehouse as one file

```bash
python -m examples.cookbook.share_map
```

The warehouse gets a site picture, an outline with its own background picture, and the road from the previous recipe. It is exported to `W1.wmsmap`, imported into a second, empty database (seeded, no plant, no users), and routing works there straight away.

```python
sent = export_map(session, PLANT, WAREHOUSE, file, image_root=ours)

friend = open_empty_wms()                 # same factory models, seeded
start_operation(friend, actor=None)
got = import_map(friend, file, image_root=theirs)
friend.commit()

route_map = published_route_map(friend, PLANT, WAREHOUSE)   # published, ready to route
```

```
road A-B: 8.40 m, mouths at ['3.6', '4.8'] m
exported W1.wmsmap: 1 zone, 6 locations, pictures ['floors/tl-site.png', 'warehouses/tl-w1.png'], route revision 1
imported C221/W1: 6 locations
  picture floors/tl-site.png: 'site picture'
  picture warehouses/tl-w1.png: 'warehouse picture'
routing works on the friend's side: dock -> tl-w1-1-0101 17.80 m
second import refused: warehouse C221/W1 already exists
```

The distance is the same 17.80 m as in [Map and routing](#map-and-routing): the route map arrived intact. Importing the same file again is refused. Details in [Features](features.md#map_file-send-a-warehouse-as-one-file).

## Writing your own recipe

1. Start from `open_site()` in `examples/cookbook/site.py`
2. Call `start_operation(session, actor=...)` before every change
3. Put the recipe in `examples/cookbook/<name>.py` with a `main()` that prints what happened
4. Add it to `tests/test_examples.py` with the lines it must print
