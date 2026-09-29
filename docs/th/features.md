# feature เสริม

**ภาษาไทย** | [English](../en/features.md)

feature มีตารางก็ต่อเมื่อโรงงาน import เท่านั้น ไม่ import = ไม่มีตาราง ไม่มี error ตาราง lookup ของ feature ที่เปิดจะถูกบังคับให้ seed โดย `verify_factory`

| feature | เปิดด้วย | ตาราง |
|---|---|---|
| machines | `import wms_sdk.features.machines` | `machine_groups`, `machines`, `product_source_machines` |
| brand | `HasBrand` ใน `ProductProperties` | `brands` + คอลัมน์ `brand_code` |
| floor_map | `import wms_sdk.features.floor_map.models` | `floor_images`, `warehouse_maps`, `warehouse_map_points`, `location_maps` |
| routing | `import wms_sdk.features.routing.models` | `route_maps`, `route_vertices`, `route_edges`, `location_access_points` |
| tasks | `import wms_sdk.features.tasks.models` | `task_types`, `task_statuses`, `tasks` (interface) |
| map_file | `from wms_sdk.features import map_file` | ไม่มี: อ่านและเขียนตารางของ floor_map / routing |

## machines

เครื่องจักรที่ผลิตสินค้า สำหรับคลังของโรงงานผลิต คลังกระจายสินค้าไม่ต้องใช้

- `machine_groups` — lookup (เช่น HS, FM, CM_PK, YARD)
- `machines` — PK `(plant_code, code)`: รหัสเครื่องซ้ำข้ามโรงได้
- `product_source_machines` — เครื่องที่ผลิตสินค้านี้ที่โรงนี้ PK `(plant_code, sku, machine_code)`; FK สองตัวใช้ `plant_code` ร่วมกัน DB จึงรับประกันว่าสินค้าผลิตที่โรงนั้น (`plant_products`) และเครื่องอยู่โรงเดียวกัน ลบสินค้าออกจากโรง (`plant_products`) → เครื่องที่ผูกไว้ถูกลบตาม (CASCADE)

## brand

```python
from wms_sdk.features.brand import HasBrand

class ProductProperties(ProductPropertiesBase, HasBrand, Base): ...
```

เพิ่มตาราง lookup `brands` และคอลัมน์ `product_properties.brand_code` (NOT NULL, FK → brands)

## floor_map — วาดแผนที่บนจอ

เก็บตำแหน่งสำหรับวาดเท่านั้น ไม่เกี่ยวกับ stock ถ้าไม่มี คลังยังทำงานได้ครบ แค่แสดงเป็นรายการแทนแผนที่

| ตาราง | PK | เก็บอะไร |
|---|---|---|
| `floor_images` | `code` | รูปแผนที่ของ site (path ของไฟล์, ความกว้าง / สูงเป็น pixel) ไม่ผูกโรง: หลายโรงใน site เดียวใช้รูปร่วมกัน |
| `warehouse_maps` | `(plant_code, warehouse_code)` | กล่องคลังบนรูป: `x`, `y`, `width`, `height`, `rotation_deg`, รูปพื้นหลังในคลัง, `metres_per_unit` (สเกล NULL = ยังไม่วัด) |
| `warehouse_map_points` | `+ point_no` (1–4) | มุมของรูปทรงคลัง เป็นสัดส่วน 0–1 ของกล่องก่อนหมุน ไม่มีจุด = สี่เหลี่ยมเต็มกล่อง |
| `location_maps` | `location_code` | กล่องของตำแหน่งบนภาพคลัง, `row_direction` (up / down / left / right), ระยะห่างตอนวาด |

พิกัดเป็น DECIMAL ไม่ใช่ FLOAT: ค่าที่ลากบนจอถูกบันทึกซ้ำหลายรอบ FLOAT จะเพี้ยนสะสม

`geometry.py` (ต้องติดตั้งตัวเลือก `floor_map` ซึ่งติดตั้ง [shapely](https://shapely.readthedocs.io/)):

```python
from wms_sdk.features.floor_map.geometry import polygon_error, to_clip_path

polygon_error(points)   # None = ใช้ได้, ข้อความ = ผิดตรงไหน (ไม่ครบ 4 จุด, จุดซ้ำ, ขอบตัดกัน, ไม่มีพื้นที่)
to_clip_path(points)    # "polygon(0% 0%, 100% 0%, ...)" สำหรับ CSS clip-path, None = สี่เหลี่ยมเต็ม
```

DB ตรวจจำนวนจุดไม่ได้ (0 หรือ 4) — เรียก `polygon_error` ก่อนบันทึก

import จากระบบเดิม: ถ้า `rotation` เดิมเก็บหน่วย ±720 (atan2 × 720/π) 720 หน่วย = 180° ต้องหาร 4 ก่อนใส่ `rotation_deg` (ตรวจกับข้อมูลจริงก่อน); `type_location` เดิม VR / VL / HB / HT = left / right / up / down

### ตัวช่วยสร้างแมพ (เลือกใช้)

สร้าง column ของตำแหน่งแบบหน้า Admin Map ของ reference factory: admin วาง row 1 ของ column และเลือกทิศ ตัวช่วยคำนวณกล่องของทุก row และทุกช่องวางพาเลท

`builder.py` (ฟังก์ชันล้วน):

```python
from decimal import Decimal
from wms_sdk.features.floor_map.builder import ColumnLayout, cells, plan_rows, snap
from wms_sdk.features.floor_map.models import RowDirection

layout = ColumnLayout(
    origin_x=Decimal(100), origin_y=Decimal(200),   # มุมซ้ายบนของ row 1
    direction=RowDirection.DOWN,                      # row 2, 3, ... ไปทางไหน
    rows=5, max_level=3, sub_column=2,
    cell_width=Decimal(10), cell_height=Decimal(8),  # ขนาดช่องวางพาเลทหนึ่งช่อง
    level_gap=Decimal(1), row_gap=Decimal(5),
)
plan_rows(layout)                    # [RowPlan(row_no, box)]: กล่องของแต่ละ row (ตำแหน่ง)
cells(layout, plan_rows(layout)[0])  # [Cell(level, slot, box)]: ช่องภายใน row
snap(x, y, neighbours, threshold)    # ดูดจุดที่กำลังลากเข้าแนว x / y ที่ใกล้
```

- ขนาด row = `sub_column x cell_width + ระยะห่าง` คูณ `max_level x cell_height + ระยะห่าง`
- ชั้น 1 / ช่อง 1 อยู่ฝั่งที่ row เริ่มต้น: ถ้า row ไปทางขึ้น ชั้น 1 อยู่ล่าง ถ้า row ไปทางซ้าย ช่อง 1 อยู่ขวา

`repository.py` บันทึก column:

```python
from wms_sdk.features.floor_map.repository import save_column, retire_locations

codes = save_column(
    session,
    plant_code="C221", warehouse_code="W3", zone_code="1",
    layout=layout,
    code_of=lambda row_no: f"w3-01{row_no:02}",                # รูปแบบรหัสตำแหน่งของโรงงาน
    properties_of=lambda row, code: MyLocationProperties(...),  # ไม่บังคับ
    previous_codes=[...],                                       # รหัสของ column ก่อนแก้
)
```

- สร้างโซนถ้ายังไม่มี (กู้คืนถ้าถูกลบ)
- สร้างหรือกู้คืนแต่ละตำแหน่ง บันทึก `location_maps` และ properties ของโรงงาน
- รหัสใน `previous_codes` ที่ไม่อยู่ใน layout แล้ว (ลดจำนวน row) ถูกเลิกใช้
- ถ้าตำแหน่งที่จะเลิกใช้ยังมีพาเลท raise `LocationInUse` และไม่เปลี่ยนอะไรเลย
- บันทึก event `location_map.column_saved`; ต้องเรียก `start_operation` ก่อน

`retire_locations(session, codes)` เลิกใช้ตำแหน่ง (เช่น ลบทั้ง column) พร้อมตรวจพาเลทแบบเดียวกัน

ตัวอย่างอ้างอิง (`examples/reference_factory/maps.py`) ห่อฟังก์ชันนี้ด้วยรหัสแบบ mapid (`tl-w3-1-0102`), properties column / row / ความจุ, `delete_column` และกฎว่าย้าย column ไปโซนอื่นต้องลบก่อน (เพราะรหัสเปลี่ยน)

แบบที่รันได้: [`examples/cookbook/site.py`](../../examples/cookbook/site.py) ใช้ [`examples/reference_factory/maps.py`](../../examples/reference_factory/maps.py) วาดทุก column ของ cookbook

## routing — ถนน forklift และระยะทาง

ใช้คำนวณระยะที่ forklift ต้องขับจริง เช่น หาตำแหน่งว่างที่ใกล้ที่สุด หรือเรียงงานให้ขับน้อยที่สุด

`graph.py` และ `repository.py` ต้องติดตั้งตัวเลือก `routing` ซึ่งติดตั้ง [networkx](https://networkx.org/) ใช้ทำ Dijkstra และตรวจการเชื่อมต่อ ส่วนปากช่องที่อยู่กลางถนนซึ่ง networkx ไม่มี SDK เขียนเพิ่มเอง

### โครงสร้าง

```
route_maps (plant, warehouse, revision_no, status)
 ├─ route_vertices   จุด: corner / junction / gate / dock, clearance_m
 ├─ route_edges      ถนนหนึ่งทิศ (from_code → to_code), distance_m
 └─ location_access_points
        ตำแหน่งนี้เข้าจากถนน (road_start_code, road_end_code)
        ที่ offset_ratio (0 = ต้นถนน, 1 = ปลาย), ฝั่ง left / right
        วางได้ไหม / หยิบได้ไหม, ระยะจากถนนเข้าช่อง
```

- ถนนระบุด้วย vertex สองตัว จุดเริ่มคือ code ที่น้อยกว่า ถนนสองทาง = edge สองแถว
- ปากช่องไม่ใช่ vertex — อยู่บนถนนที่สัดส่วนความยาว
- ใช้ตัวพิมพ์เดียวกันกับ code ของ vertex เสมอ (SQL Server เทียบตาม collation ซึ่งมักไม่สนตัวพิมพ์ แต่ Python เทียบตามรหัสตัวอักษร)
- `side` ของปากช่อง: `front` / `back` (ช่องที่เข้าได้สองด้าน)

### ฉบับร่างและเผยแพร่

- แต่ละคลังมีฉบับ `draft` ได้หนึ่งฉบับ และ `published` ได้หนึ่งฉบับ (DB บังคับ)
- แก้ได้เฉพาะ draft; การคำนวณเส้นทางใช้ published เท่านั้น
- `publish()` เปลี่ยนฉบับเดิมเป็น `archived` แล้วบันทึก event `route_map.published`
- ลบ draft ต้องลบตามลำดับ: `location_access_points` → `route_edges` → `route_vertices` → `route_maps` (ไม่ใช้ CASCADE เพราะ SQL Server ไม่ยอมให้มีหลายเส้นทาง cascade มาที่ตารางเดียว)

```python
from wms_sdk.features.routing.repository import publish

start_operation(session, actor="admin")
publish(session, draft_map, actor="admin")     # raise InvalidRouteStatus ถ้าไม่ใช่ draft
session.commit()
```

### หาระยะทาง

```python
from wms_sdk.features.routing.graph import cost_to, path_to, shortest_from
from wms_sdk.features.routing.repository import access_position, load_graph, published_route_map

route_map = published_route_map(session, "C221", "W3")    # NotSet ถ้ายังไม่มี
graph = load_graph(session, route_map)

source = access_position(route_map, source_point)        # AccessPoint → AccessPosition
paths = shortest_from(graph, source)                     # Dijkstra ครั้งเดียว

for point in candidate_points:                           # ถามได้หลายพันปลายทาง
    cost = cost_to(graph, paths, access_position(route_map, point))
    if cost is not None:
        print(point.location_code, cost.total_m)

best = ...                                               # เลือกเอง
vertices = path_to(paths, best_cost)                     # ["B", "C"] จุดที่ผ่าน
```

`cost.total_m` = ระยะจากช่องต้นทางออกถนน + ตามถนน + เข้าช่องปลายทาง ระยะเข้าช่องใช้ `approach_override_m` ของจุดนั้น หรือ `default_approach_m` ของ route map

### วางปากช่องบนถนน

```python
from wms_sdk.features.routing.graph import LaneMouth, layout_road, offset_ratio

layout = layout_road(start_xy, end_xy, start_clearance_m, end_clearance_m, mouths)
for placed in layout.mouths:
    ratio = offset_ratio(placed.offset_m, layout.calculated_length_m)
    # placed.road_side → AccessPoint.road_side, ratio → AccessPoint.offset_ratio
```

ระยะเป็นค่าประมาณ: offset = clearance ต้นถนน + ความกว้างช่องก่อนหน้า + ครึ่งหนึ่งของช่องนี้ ความยาวถนน = clearance สองปลาย + ด้านที่ช่องกว้างรวมมากที่สุด ถ้าวัดจริงแล้วใส่ `distance_m` เอง (`distance_source = manual`) ปากช่องเลื่อนตามสัดส่วน

### ตรวจก่อนเผยแพร่

```python
from wms_sdk.features.routing.graph import unreachable_vertices

unreachable_vertices(graph)   # vertex ที่ไม่เชื่อมกับเครือข่ายหลัก (set ว่าง = ดี)
```

แบบที่รันได้: [`examples/cookbook/map_and_routing.py`](../../examples/cookbook/map_and_routing.py) วาดถนน เผยแพร่ และหาตำแหน่งว่างที่ใกล้ที่สุด (ดู [ตัวอย่าง](examples.md#แมพและเส้นทาง))

## tasks — งานและการจอง

งาน forklift, งาน QC, งานจ่าย ใช้ตาราง `tasks` ตารางเดียวสำหรับงานทุกประเภท งานของแต่ละโรงไม่เหมือนกัน SDK จึงกำหนดแค่โครง

| | SDK กำหนด | โรงงานกำหนด |
|---|---|---|
| คอลัมน์ | `id` (เลขที่งาน), `task_type_code`, `status_code`, timestamps | ที่เหลือทั้งหมด: มอบให้ role ไหน, พาเลท, ต้นทาง / ปลายทาง, รถ ... |
| ประเภทงาน | lookup `task_types` | seed เอง (เช่น putaway, pick, dispatch, qc_check) |
| สถานะ | lookup `task_statuses` | seed เอง และบอกว่าสถานะไหนนับว่ายังไม่เสร็จ (`active_statuses`) |
| การเปลี่ยนสถานะ | `set_task_status()` ตรวจให้และบันทึก `task.status_changed` | การเปลี่ยนที่อนุญาต (`transitions`) |
| การจอง | unique index ของงานที่ยังไม่เสร็จ | คอลัมน์ไหนใช้จอง (`reservation_columns`) |

```python
from wms_sdk.features.tasks.models import TaskBase

class Task(TaskBase, Base):
    active_statuses = ("open", "in_progress")
    reservation_columns = ("to_location_code", "to_level_no", "to_slot_no")
    transitions = {
        None: {"open"},                         # งานใหม่เริ่มที่ open
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
set_task_status(session, task, "open")         # add และ flush ให้: task.id มีค่าแล้ว
session.commit()
```

- **การจอง:** ขณะที่งานอยู่ในสถานะที่ยังไม่เสร็จและคอลัมน์ใน `reservation_columns` มีค่าครบ งานอื่นที่ยังไม่เสร็จจะใช้ค่าเดียวกันไม่ได้ (unique index ที่กรอง `status_code IN (active_statuses)`) งานที่เสร็จหรือยกเลิกคืนที่จองเอง งานที่ไม่มีปลายทาง (เช่น QC) ไม่ชนกัน
- มี `reservation_columns` แต่ไม่มี `active_statuses` → `TypeError` ตอน import
- เปลี่ยนสถานะที่ไม่อยู่ใน `transitions` → `InvalidTaskStatus`; งานใหม่ต้องเริ่มที่สถานะที่อนุญาตจาก `None`
- ประวัติ (ใครรับ เสร็จเมื่อไหร่) อยู่ใน `event_log` ไม่มีตาราง history ของงาน
- การจองไม่ได้ตรวจว่าที่นั้นมีพาเลทอยู่แล้วหรือไม่ แอปต้องตรวจเอง
- ตัวอย่างอ้างอิง (`examples/reference_factory/models.py` คลาส `Task`) มอบงานให้ role, จองระดับ location + ชั้น + ช่อง และมี `reference` (เช่น เลขออเดอร์) งานจ่ายหลายพาเลทจึงเป็นหลายงานที่ใช้ reference เดียวกัน
- ยังไม่ได้ยืนยันบน SQL Server: index การจองใช้ `IN (...)` ในเงื่อนไขกรอง

แบบที่รันได้: [`examples/cookbook/dispatch_tasks.py`](../../examples/cookbook/dispatch_tasks.py) แสดงการจอง การจองซ้ำที่ถูกปฏิเสธ และการคืนที่จอง (ดู [ตัวอย่าง](examples.md#งานจ่ายและการจอง))

## map_file: ส่งคลังเป็นไฟล์เดียว

วาดคลังครั้งเดียว แล้วส่งให้คนอื่นเป็นไฟล์ `.wmsmap` ไฟล์เดียว ฝั่งนั้น import ด้วย SDK แล้วได้คลังพร้อมใช้ทันที มีทั้งรูปและ route map โดยไม่ต้อง copy database

```python
from wms_sdk.features.map_file import export_map, import_map

# ฝั่งเรา: อ่านอย่างเดียว
export_map(session, "C221", "W1", "W1.wmsmap", image_root="media/")

# ฝั่งเพื่อน: ใช้ model ของโรงงานชุดเดียวกัน และ seed แล้ว
start_operation(session, actor="planner1")
import_map(session, "W1.wmsmap", image_root="media/")
session.commit()
```

ไฟล์ `.wmsmap` คือ ZIP:

| ข้างใน | เนื้อหา |
|---|---|
| `manifest.json` | เวอร์ชันรูปแบบไฟล์, เวอร์ชัน SDK, เวลา export, plant และคลัง, คอลัมน์ของ properties |
| `map.json` | แถวของ `plants`, `warehouses`, `zones`, `zone_properties`, `locations`, `location_properties`, `location_maps`, `floor_images`, `warehouse_maps`, `warehouse_map_points` และ route map ที่ **เผยแพร่แล้ว** พร้อม `route_vertices`, `route_edges`, `location_access_points` |
| `images/<path>` | รูปผังโรงงานและรูปพื้นหลังในคลัง เก็บไว้ใต้ path เดียวกับที่ database เก็บ |

- database เก็บแค่ path ของรูป `image_root` คือโฟลเดอร์ที่ path เหล่านั้นอ้างอิง ของแต่ละฝั่ง
- ไม่ถูก export: พาเลท งาน ประวัติ event และ route map ที่เป็น draft หรือ archived ไฟล์นี้บอกว่าคลังหน้าตาเป็นอย่างไร ไม่ได้บอกว่ามีอะไรอยู่ข้างใน
- ค่าตัวเลขได้ความละเอียดเท่าเดิม (ทศนิยมเขียนเป็นข้อความ) ส่วน `created_at` / `updated_at` ให้ database ฝั่งที่ import ตั้งเอง
- สองฝั่งต้องใช้ model ของโรงงานชุดเดียวกัน: คอลัมน์ properties เหมือนกัน และ seed lookup ชุดเดียวกัน

กฎตอน import:

| กรณี | ผล |
|---|---|
| มีคลังนี้ใน database แล้ว | `WarehouseExists` ไม่เขียนอะไรเลย import สร้างได้แค่คลังใหม่ |
| คลังอื่นใช้รหัส location ซ้ำ | `LocationCodeTaken` (รหัส location ห้ามซ้ำทุกคลัง) |
| คอลัมน์ properties ไม่ตรงกับของโรงงานนี้ | `PropertiesMismatch` ส่ง `properties=False` เพื่อ import โดยไม่เอา properties |
| ยังไม่มี plant | สร้างให้ |
| มีรูปผังโรงงานรหัสเดียวกันอยู่แล้ว | ใช้ของเดิม ไม่เขียนรูปทับ |
| route map | ได้เลขฉบับเดิม และยังเป็นฉบับเผยแพร่ ส่วน `published_by` ถูกล้าง เพราะผู้ใช้คนนั้นอาจไม่มีในฝั่งนี้ |
| path รูปออกนอก `image_root` (`..`, path เต็ม) | `UnsupportedMapFile` ไม่เขียนอะไรนอก `image_root` |

import ทำงานใน operation ของคุณ ทุกแถวจึงถูกบันทึกใน `event_log` แล้วตามด้วย event `map_file.imported` รูปจะถูกเขียนหลังจาก flush ทุกแถวสำเร็จแล้วเท่านั้น และผู้เรียกเป็นคน commit

แบบที่รันได้: [`examples/cookbook/share_map.py`](../../examples/cookbook/share_map.py) export คลังพร้อมรูป แล้วหาเส้นทางบน database ที่สองซึ่งว่างเปล่า (ดู [ตัวอย่าง](examples.md#แชร์คลังเป็นไฟล์เดียว))
