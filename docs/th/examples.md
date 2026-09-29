# ตัวอย่าง

**ภาษาไทย** | [English](../en/examples.md)

ตัวอย่างทุกชิ้นในหน้านี้รันได้ทันทีบน SQLite ในหน่วยความจำ และ `tests/test_examples.py` รันทุกชิ้นให้ จึงถูกต้องอยู่เสมอเมื่อ SDK เปลี่ยน ผลลัพธ์ด้านล่างคัดลอกมาจากการรันจริง

| ตัวอย่าง | แสดงอะไร |
|---|---|
| [`examples/minimal_factory`](../../examples/minimal_factory) | โรงงานที่เล็กที่สุด อธิบายทีละขั้นใน [Tutorial](tutorial.md) |
| [`examples/reference_factory`](../../examples/reference_factory) | โรงงานเต็มรูปแบบ: ทุก interface มีคอลัมน์ของตัวเอง เปิดทุก feature |
| [`examples/cookbook`](../../examples/cookbook) | สูตรงานจริงบนตัวอย่างอ้างอิงด้านล่าง |

ทุกสูตรเริ่มจาก `open_site()` ใน [`cookbook/site.py`](../../examples/cookbook/site.py): โรงงาน C221 (TL), คลัง W1, ผู้ใช้ `planner1` / `forklift1` / `lab1`, สินค้า A001 / A002 และสอง column ที่มี column ละ 3 row สร้างด้วยตัวช่วยสร้างแมพ (`tl-w1-1-0101`..`0103`, `tl-w1-1-0201`..`0203`)

## วงจรพาเลท

```bash
python -m examples.cookbook.pallet_lifecycle
```

ใส่ของลงพาเลทสองใบแล้ววางเก็บผ่านงาน แล็บให้ผ่านหนึ่งใบและล็อกอีกใบ ใบที่ผ่านเท่านั้นที่ส่งออกได้

```python
# planner สร้างงาน putaway ปลายทางถูกจองระหว่างที่งานยังเปิดอยู่
task = Task(task_type_code="putaway", assigned_role_code="Forklift", pallet_code=pallet.code,
            to_location_code=location_code, to_level_no=level_no, to_slot_no=slot_no)
set_task_status(session, task, "open")

# คนขับ forklift ทำงาน
set_task_status(session, task, "in_progress")
pallet.location_code, pallet.level_no, pallet.slot_no = location_code, level_no, slot_no
record_event(session, PalletEvent.PUTAWAY, {"pallet": pallet.code, "to": location_code})
set_task_status(session, task, "done")

# แล็บ
set_qc_status(session, good, QcStatus.PASSED)
set_qc_status(session, bad, QcStatus.LOCKED, reason="moisture above limit")

# ส่งออก
ensure_shippable(pallet)          # NotShippable ถ้าไม่ passed
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

ประวัติมีทั้งการแก้แถวที่จับอัตโนมัติ (`pallets.updated`) และ event ทางธุรกิจ (`pallet.putaway`) พร้อมบอกว่าใครทำ

## แมพและเส้นทาง

```bash
python -m examples.cookbook.map_and_routing
```

```
    A ────────── B ──── D (dock)
      [col 1] [col 2]           ปากช่องของ row 1 ออกถนน A-B
```

วาดถนนหน้า column วางปากช่องจากกล่องของ location ที่วาดไว้ เผยแพร่แผนที่ถนน แล้วหาตำแหน่งว่างที่ใกล้ dock ที่สุด

```python
# วางปากช่องบนถนน A-B จากภาพของ location
mouths = [LaneMouth(code, (box.x + box.width / 2, box.y), LANE_WIDTH_M) for code, box in ...]
layout = layout_road(VERTICES["A"], VERTICES["B"], D(3), D(3), mouths)
# ... เพิ่มแถว RouteMap, RouteVertex, RouteEdge (ความยาว = layout.calculated_length_m), AccessPoint
publish(session, draft, actor="planner1")

# ตำแหน่งว่างที่ใกล้ dock ที่สุด
graph = load_graph(session, published_route_map(session, PLANT, WAREHOUSE))
paths = shortest_from(graph, AccessPosition(road=road_of("B", "D"), ratio=1.0, approach_m=0.0))
cost = cost_to(graph, paths, access_position(route_map, point))   # ทีละ access point
path_to(paths, cost)
```

```
road A-B: 8.40 m, mouths at ['3.6', '4.8'] m
unreachable vertices: none
  tl-w1-1-0101: 17.80 m free
  tl-w1-1-0201: 16.60 m occupied
nearest free location: tl-w1-1-0101 (17.80 m, via ['B'])
```

`tl-w1-1-0201` ใกล้กว่าแต่มีพาเลทอยู่แล้ว จึงเลือกที่ใกล้รองลงมา ต้องติดตั้งตัวเลือก `routing` (networkx)

## งานจ่ายและการจอง

```bash
python -m examples.cookbook.dispatch_tasks
```

ใบสั่งขายหนึ่งใบกลายเป็นงานจ่ายหนึ่งงานต่อพาเลท ใช้ `reference` ร่วมกัน งานที่ยังเปิดอยู่จองช่องพักของ DB ไม่ยอมให้งานที่สองจองช่องเดียวกันจนกว่างานแรกจะเสร็จ

```python
task = Task(task_type_code="dispatch", assigned_role_code="Forklift", pallet_code=pallet_code,
            to_location_code=STAGING, to_level_no=level_no, to_slot_no=1, reference=order)
set_task_status(session, task, "open")
...
except IntegrityError:            # ช่องนี้ถูกงานอื่นที่ยังเปิดอยู่จองไว้
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

งาน QC ไม่มีปลายทาง จึงไม่จองอะไรและไม่ชนกัน

## แชร์คลังเป็นไฟล์เดียว

```bash
python -m examples.cookbook.share_map
```

คลังได้รูปผังโรงงาน, กรอบคลังที่มีรูปพื้นหลังของตัวเอง และถนนจากสูตรก่อนหน้า แล้วถูก export เป็น `W1.wmsmap` จากนั้น import เข้า database ที่สองซึ่งว่างเปล่า (seed แล้ว ไม่มี plant ไม่มีผู้ใช้) และหาเส้นทางได้ทันที

```python
sent = export_map(session, PLANT, WAREHOUSE, file, image_root=ours)

friend = open_empty_wms()                 # model โรงงานชุดเดียวกัน seed แล้ว
start_operation(friend, actor=None)
got = import_map(friend, file, image_root=theirs)
friend.commit()

route_map = published_route_map(friend, PLANT, WAREHOUSE)   # เผยแพร่แล้ว หาเส้นทางได้เลย
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

ระยะทางได้ 17.80 m เท่ากับใน [แมพและเส้นทาง](#แมพและเส้นทาง) แปลว่า route map มาครบ import ไฟล์เดิมซ้ำจะถูกปฏิเสธ รายละเอียดอยู่ใน [feature เสริม](features.md#map_file-ส่งคลังเป็นไฟล์เดียว)

## เขียนสูตรของตัวเอง

1. เริ่มจาก `open_site()` ใน `examples/cookbook/site.py`
2. เรียก `start_operation(session, actor=...)` ก่อนแก้ข้อมูลทุกครั้ง
3. วางไฟล์ไว้ที่ `examples/cookbook/<name>.py` มี `main()` ที่พิมพ์สิ่งที่เกิดขึ้น
4. เพิ่มใน `tests/test_examples.py` พร้อมข้อความที่ต้องพิมพ์ออกมา
