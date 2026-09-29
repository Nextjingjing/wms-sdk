# API reference

**ภาษาไทย** | [English](../en/api.md)

ฟังก์ชันและคลาสที่โปรเจกต์ของโรงงานเรียกใช้ได้ ตาราง (model) ดูที่ [schema.md](schema.md)

## เริ่มระบบ

### `wms_sdk.metadata`

| ชื่อ | |
|---|---|
| `metadata` | `Base.metadata` หลัง import ตาราง core ทั้งหมด ใช้กับ Alembic / `create_all` |

### `wms_sdk.checks`

| ชื่อ | |
|---|---|
| `verify_factory(session) -> None` | เรียกตอนเริ่มระบบ หลัง import model ของโรงงาน raise `NotImplementedError` ถ้า interface ไม่ครบ, `LookupNotSeeded` ถ้าตาราง lookup ใดยังว่าง |

### `wms_sdk.core.db`

| ชื่อ | |
|---|---|
| `Base` | declarative base พร้อม naming convention ของ constraint |
| `Lookup` | สืบทอดเพื่อบอกว่าเป็นตาราง lookup (ไม่มีคอลัมน์ในตัว — ประกาศ `code`, `name` เอง) |
| `NAMING_CONVENTION` | รูปแบบชื่อ pk / fk / uq / ix / ck |

### `wms_sdk.core.interface`

| ชื่อ | |
|---|---|
| `Interface` | ฐานของ interface; โรงงานสืบทอด `XBase` คู่กับ `Base` |
| `Interface.implementation()` | คลาสที่โรงงาน implement หรือ raise `NotImplementedError` |
| `Interface.roots` | interface ทั้งหมดของ SDK |
| `extra_table_args` | tuple ของ constraint ของโรงงาน (ใช้แทน `__table_args__`) |
| `get_row(session, interface, key)` | อ่านแถวของ interface ตาม key; raise `NotSet` ถ้าไม่มี |

interface ที่มี: `ProductPropertiesBase`, `ZonePropertiesBase`, `LocationPropertiesBase`, `PalletBase`; ถ้าเปิด feature tasks มี `TaskBase` ด้วย

## event

### `wms_sdk.modules.events.capture`

| ชื่อ | |
|---|---|
| `install_capture(session_factory) -> None` | ติดตั้งตัวจับการแก้ข้อมูลบน `sessionmaker` เรียกครั้งเดียว |
| `start_operation(session, actor) -> UUID` | เริ่มการกระทำหนึ่งครั้ง `actor` = username หรือ `None` |
| `record_event(session, event_type, payload, destinations=()) -> EventLog` | บันทึก event ทางธุรกิจ; `destinations` สร้างแถวใน outbox |

flush โดยไม่เรียก `start_operation` → `RuntimeError`

### `wms_sdk.modules.events.receive`

| ชื่อ | |
|---|---|
| `receive_message(session, source, message_id, message_type, payload) -> bool` | เก็บข้อความขาเข้าใน inbox; `False` ถ้าเคยได้รับแล้ว |

### model

`wms_sdk.modules.events.models`: `EventLog`, `Outbox`, `Inbox`

## stock และ QC

### `wms_sdk.modules.inventory.events`

`PalletEvent` (StrEnum): `LOADED`, `PUTAWAY`, `MOVED`, `PICKED`, `ADJUSTED`, `SHIPPED`, `RETURNED`, `RETIRED` → ค่า `pallet.<verb>`

### `wms_sdk.modules.inventory.qc`

| ชื่อ | |
|---|---|
| `QcStatus` | `WAITING`, `LOCKED`, `PASSED` |
| `QC_TRANSITIONS` | การเปลี่ยนสถานะที่อนุญาต |
| `QcEvent` | `PASSED` = `pallet.qc_passed`, `LOCKED` = `pallet.qc_locked` |
| `set_qc_status(session, pallet, new, reason=None) -> None` | เปลี่ยนสถานะ QC; `LOCKED` ต้องมี `reason` |
| `ensure_shippable(pallet) -> None` | raise `NotShippable` ถ้าไม่ `PASSED` |
| `InvalidQcTransition` | เปลี่ยนสถานะที่ไม่อยู่ใน `QC_TRANSITIONS` |
| `MissingLockReason` | ล็อกโดยไม่มีเหตุผล |
| `NotShippable` | ส่งพาเลทที่ยังไม่ผ่าน QC |

### properties

| ชื่อ | |
|---|---|
| `wms_sdk.modules.master_data.repository.get_product_properties(session, sku)` | raise `NotSet` ถ้าไม่มี |
| `wms_sdk.modules.storage.repository.get_zone_properties(session, plant_code, warehouse_code, zone_code)` | raise `NotSet` ถ้าไม่มี |
| `wms_sdk.modules.storage.repository.get_location_properties(session, location_code)` | raise `NotSet` ถ้าไม่มี |

## feature

### `wms_sdk.features.brand`

`Brand` (lookup), `HasBrand` (mixin เพิ่ม `brand_code`)

### `wms_sdk.features.machines`

`MachineGroup` (lookup), `Machine`, `ProductSourceMachine`

### `wms_sdk.features.floor_map`

| ชื่อ | |
|---|---|
| `models`: `FloorImage`, `WarehouseMap`, `WarehouseMapPoint`, `LocationMap`, `RowDirection` | |
| `geometry.polygon_error(points) -> str \| None` | ตรวจรูปทรงคลัง |
| `geometry.to_clip_path(points) -> str \| None` | CSS clip-path |
| `builder.ColumnLayout`, `builder.plan_rows(layout)`, `builder.cells(layout, row)`, `builder.row_size(layout)` | คำนวณ row และช่องวางพาเลทของ column |
| `builder.snap(x, y, neighbours, threshold) -> Snapped` | ดูดจุดที่ลากเข้าแนวใกล้เคียง |
| `repository.save_column(session, *, plant_code, warehouse_code, zone_code, layout, code_of, label_gap=0, properties_of=None, previous_codes=()) -> list[str]` | บันทึกตำแหน่งและภาพของ column |
| `repository.retire_locations(session, codes)` | เลิกใช้ตำแหน่ง; raise `LocationInUse` ถ้ายังมีพาเลท |

### `wms_sdk.features.routing`

| ชื่อ | |
|---|---|
| `models`: `RouteMap`, `RouteVertex`, `RouteEdge`, `AccessPoint` | ตาราง |
| `models`: `RouteStatus`, `VertexType`, `DistanceSource`, `AccessSide`, `RoadSide` | StrEnum |
| `repository.published_route_map(session, plant_code, warehouse_code)` | ฉบับที่เผยแพร่ หรือ `NotSet` |
| `repository.load_graph(session, route_map) -> RouteGraph` | โหลด edge ของฉบับนั้น |
| `repository.access_position(route_map, point) -> AccessPosition` | แปลง `AccessPoint` เป็นตำแหน่งบนถนน |
| `repository.publish(session, route_map, actor)` | เผยแพร่ draft; archive ฉบับเดิม; raise `InvalidRouteStatus` |
| `graph.build_graph(edges) -> RouteGraph` | สร้างกราฟจาก `Edge` |
| `graph.shortest_from(graph, source) -> ShortestPaths` | Dijkstra จากปากช่อง |
| `graph.cost_to(graph, paths, target) -> RouteCost \| None` | ระยะไปปากช่อง (`total_m`) |
| `graph.path_to(paths, cost) -> list[str]` | vertex ที่ผ่าน |
| `graph.layout_road(start, end, start_clearance_m, end_clearance_m, mouths) -> RoadLayout` | วางปากช่องบนถนน |
| `graph.offset_ratio(offset_m, calculated_length_m) -> Decimal` | สัดส่วนจากต้นถนน |
| `graph.road_side_of(start, end, point) -> RoadSide \| None` | ฝั่งของจุดเทียบกับถนน |
| `graph.road_of(a, b) -> (start, end)` | key ของถนน (code น้อยกว่าก่อน) |
| `graph.unreachable_vertices(graph) -> set[str]` | vertex ที่ไม่เชื่อมเครือข่ายหลัก |

### `wms_sdk.features.tasks`

| ชื่อ | |
|---|---|
| `models`: `TaskType`, `TaskStatus` (lookup), `TaskBase` (interface) | |
| `TaskBase.active_statuses`, `reservation_columns`, `transitions` | ค่าที่โรงงานกำหนด |
| `repository.set_task_status(session, task, new) -> None` | เปลี่ยนสถานะ (รวมงานใหม่); บันทึก `task.status_changed`; raise `InvalidTaskStatus` |

### `wms_sdk.features.map_file`

| ชื่อ | |
|---|---|
| `export_map(session, plant_code, warehouse_code, path, *, image_root=None) -> MapSummary` | เขียนคลังหนึ่งคลัง รูป และ route map ที่เผยแพร่แล้ว ลงไฟล์ `.wmsmap`; อ่านอย่างเดียว |
| `import_map(session, path, *, image_root=None, properties=True) -> MapSummary` | สร้างคลังนั้นในฝั่งนี้ และ copy รูปลง `image_root`; ต้องมี operation; บันทึก `map_file.imported` |
| `MapSummary` | `plant_code`, `warehouse_code`, `zones`, `locations`, `images` (path ที่เขียน), `route_revision` |
| `FORMAT_VERSION` | เวอร์ชันรูปแบบไฟล์ที่ SDK นี้อ่านและเขียน |

## test

### `wms_sdk.testing.sqlite`

| ชื่อ | |
|---|---|
| `create_sqlite_engine(url="sqlite://") -> Engine` | SQLite ที่รองรับ schema ของ SDK (FK เปิด, `ISJSON`, schema `messaging`) |

### `wms_sdk.testing`

| ชื่อ | |
|---|---|
| `create_test_engine(name="wms") -> Engine` | engine ของ database สำหรับ test หนึ่งตัว ยังไม่มีตาราง: SQLite ในหน่วยความจำ หรือ database `wms_test_<name>` บน SQL Server ที่สร้างใหม่ เมื่อตั้ง `WMS_TEST_MSSQL_URL` |
| `mssql.create_mssql_test_engine(url, schemas=("messaging",)) -> Engine` | ลบแล้วสร้าง database ใน `url` ใหม่ และสร้าง `schemas`; ไม่ยอมทำกับ database ที่ชื่อไม่มีคำว่า "test" |

## exception ทั้งหมด

| exception | จาก | เมื่อ |
|---|---|---|
| `NotSet` | `wms_sdk.core.errors` | ไม่มีแถว properties / route map ที่ขอ |
| `LookupNotSeeded` | `wms_sdk.core.errors` | ตาราง lookup ยังว่างตอน `verify_factory` |
| `NotImplementedError` | built-in | interface ยังไม่มีโรงงาน implement |
| `TypeError` | built-in | implement ซ้ำ หรือใช้ `__table_args__` ใน implementation |
| `RuntimeError` | built-in | flush โดยไม่ `start_operation` |
| `InvalidQcTransition`, `MissingLockReason`, `NotShippable` | `wms_sdk.modules.inventory.qc` | QC |
| `LocationInUse` | `wms_sdk.features.floor_map.repository` | เลิกใช้ตำแหน่งที่ยังมีพาเลท |
| `InvalidTaskStatus` | `wms_sdk.features.tasks.repository` | เปลี่ยนสถานะที่ไม่อยู่ใน `transitions` ของโรงงาน |
| `InvalidRouteStatus` | `wms_sdk.features.routing.repository` | publish ฉบับที่ไม่ใช่ draft |
| `WarehouseExists`, `LocationCodeTaken`, `PropertiesMismatch`, `UnsupportedMapFile` (ทั้งหมดเป็น `MapFileError`) | `wms_sdk.features.map_file` | import ไฟล์ `.wmsmap` |
