# stock, พาเลท และ QC

**ภาษาไทย** | [English](../en/inventory.md)

## แนวคิด

- stock ติดตาม **ทีละพาเลท** — หนึ่งแถวใน `pallets` ต่อพาเลทจริงหนึ่งใบ ตลอดอายุการใช้งาน
- พาเลท **ใช้ซ้ำได้** — ของบนพาเลท (1 sku, 1 lot) มาแล้วก็ไป รหัสพาเลทคงเดิม
- **ยอดคงเหลือ** = `SUM(qty)` ของพาเลท ไม่มีตาราง balance
- **ประวัติการเคลื่อนไหว** อยู่ใน `event_log` ไม่มีตาราง movement (ดู [events.md](events.md))

## คอลัมน์ของ `pallets`

| คอลัมน์ | ความหมาย |
|---|---|
| `code` | รหัสบน QR / LPN ติดกับพาเลทตลอด |
| `sku`, `lot_no`, `qty` | ของที่อยู่บนพาเลทตอนนี้ — NULL ทั้งสามตัว = พาเลทว่าง |
| `qc_status` | `waiting` / `locked` / `passed` — NULL เมื่อพาเลทว่าง |
| `qc_lock_reason` | เหตุผลที่ล็อก มีค่าเฉพาะตอน `locked` |
| `location_code` | ตำแหน่งเก็บ — NULL = ไม่ได้อยู่ในช่อง |
| `left_at` | มีค่าขณะพาเลทอยู่นอกคลัง ล้างเมื่อกลับมา |
| `deleted_at` | เลิกใช้ (พัง / หาย) |

โรงงานเพิ่มคอลัมน์ได้ เช่น ตัวอย่างอ้างอิงเพิ่ม `level_no`, `slot_no` (ชั้นและช่องใน location) พร้อม unique index ให้หนึ่งช่องวางได้พาเลทเดียว

## สถานะของพาเลท

ไม่มีคอลัมน์ status — สถานะคำนวณจากคอลัมน์จริง จึงขัดกันเองไม่ได้

| สถานะ | เงื่อนไข |
|---|---|
| ว่าง | ไม่มี `sku`, ไม่มี `location_code`, ไม่มี `left_at` |
| มีของ รอเก็บ | มี `sku`, ไม่มี `location_code`, ไม่มี `left_at` |
| เก็บอยู่ | มี `sku` และ `location_code` |
| นอกคลัง | มี `left_at` |
| เลิกใช้ | มี `deleted_at` |

```sql
SELECT code,
  CASE
    WHEN deleted_at    IS NOT NULL THEN 'retired'
    WHEN left_at       IS NOT NULL THEN 'out'
    WHEN location_code IS NOT NULL THEN 'stored'
    WHEN sku           IS NOT NULL THEN 'loaded'
    ELSE 'empty'
  END AS status
FROM pallets;
```

กฎที่ DB บังคับ:

- `sku`, `lot_no`, `qty` มีครบ (`qty > 0`) หรือเป็น NULL ทั้งหมด — ไม่มีพาเลท `qty = 0`
- พาเลทที่อยู่ในตำแหน่งต้องมีของ (พาเลทว่างไม่ถูกเก็บในตำแหน่ง)
- มี `left_at` → ไม่มี `location_code`
- มี `deleted_at` → ว่างและไม่มีตำแหน่ง
- มีของ ↔ มี `qc_status`; `locked` ↔ มี `qc_lock_reason`

## วงจรของพาเลท

วงจรนี้ในแบบที่รันได้จริง พร้อมงานและการล็อก QC อยู่ที่ [`examples/cookbook/pallet_lifecycle.py`](../../examples/cookbook/pallet_lifecycle.py) (อธิบายใน [ตัวอย่าง](examples.md#วงจรพาเลท))

ทุกขั้นต้องแก้ `pallets` **และ** บันทึก event ใน transaction เดียวกัน การแก้ `pallets` ถูกจับเป็น `pallets.updated` อัตโนมัติ ส่วน `record_event` บอกว่าคือการกระทำอะไร

```python
from datetime import UTC, datetime

from wms_sdk.modules.events.capture import record_event, start_operation
from wms_sdk.modules.inventory.events import PalletEvent
from wms_sdk.modules.inventory.qc import QcStatus, ensure_shippable, set_qc_status

# ใส่ของ
start_operation(session, actor="forklift1")
pallet.sku, pallet.lot_no, pallet.qty = "A001", "L1", 40
set_qc_status(session, pallet, QcStatus.WAITING)
record_event(session, PalletEvent.LOADED, {"pallet": pallet.code, "sku": "A001", "lot_no": "L1"})
session.commit()

# วางเก็บ
start_operation(session, actor="forklift1")
pallet.location_code = "tl-w3-1-0102"
record_event(session, PalletEvent.PUTAWAY, {"pallet": pallet.code, "to": "tl-w3-1-0102"})
session.commit()

# หยิบบางส่วน
pallet.qty -= 10
record_event(session, PalletEvent.PICKED, {"pallet": pallet.code, "qty": 10})

# ส่งออก — ต้องผ่าน QC ก่อน
ensure_shippable(pallet)
origin = pallet.location_code
pallet.location_code = None
pallet.left_at = datetime.now(UTC).replace(tzinfo=None)
record_event(session, PalletEvent.SHIPPED, {"pallet": pallet.code, "from": origin}, destinations=["sap"])

# พาเลทกลับมาเปล่า
pallet.sku = pallet.lot_no = pallet.qty = None
pallet.qc_status = pallet.qc_lock_reason = None   # พาเลทว่างไม่มีสถานะ QC
pallet.left_at = None
record_event(session, PalletEvent.RETURNED, {"pallet": pallet.code})
```

ชื่อ event มาตรฐาน (`PalletEvent`):

| ค่า | ใช้เมื่อ |
|---|---|
| `pallet.loaded` | ใส่ของลงพาเลทว่าง |
| `pallet.putaway` | วางเข้าตำแหน่งเก็บ |
| `pallet.moved` | ย้ายตำแหน่ง |
| `pallet.picked` | หยิบของออกบางส่วน |
| `pallet.adjusted` | แก้จำนวน เช่น หลังนับ stock |
| `pallet.shipped` | ออกจากคลังพร้อมของ |
| `pallet.returned` | กลับมา |
| `pallet.retired` | เลิกใช้ (ตั้ง `deleted_at`) |

ขั้นตอนที่ไม่อยู่ในชุดนี้ ตั้งชื่อ `pallet.<verb>` เองได้

## QC

แล็บตัดสิน **ทีละพาเลท** เฉพาะพาเลทที่ `passed` ส่งออกได้

```
(ใส่ของ) → waiting → passed
                   → locked → passed   (ตรวจซ้ำแล้วผ่าน)
           passed  → locked            (เรียกคืน)
```

การเปลี่ยนที่ไม่อยู่ในแผนภาพ raise `InvalidQcTransition` (กำหนดใน `QC_TRANSITIONS` ที่เดียว)

```python
set_qc_status(session, pallet, QcStatus.PASSED)
set_qc_status(session, pallet, QcStatus.LOCKED, reason="ความชื้นเกินเกณฑ์")  # ต้องมีเหตุผล
ensure_shippable(pallet)   # raise NotShippable ถ้าไม่ passed
```

- ล็อกโดยไม่มีเหตุผล (หรือมีแต่ช่องว่าง) → `MissingLockReason`
- เหตุผลปัจจุบันอยู่ใน `pallets.qc_lock_reason`; เหตุผลทุกครั้งอยู่ใน event `pallet.qc_locked`
- คลังที่ไม่มีแล็บ: ตั้ง `WAITING` แล้ว `PASSED` ทันทีตอนใส่ของ
- DB บังคับไม่ได้ว่าพาเลทที่ส่งออกต้อง passed — ต้องเรียก `ensure_shippable` ก่อนส่งทุกครั้ง

## ตำแหน่ง

```
plant → warehouse → zone → location
```

- `locations.code` เป็นรหัสที่คนในคลังใช้ เช่น `tl-w3-1-0102`
- `is_enabled = 0` = ปิดชั่วคราว (ห้ามวาง) ต่างจาก `deleted_at` ที่เลิกใช้ถาวร
- ที่อยู่และความจุ (column / row / level / slot / ความยาวพาเลท) อยู่ใน `location_properties` ของโรงงาน
- คุณสมบัติโซน (ทิศทางเดินรถ, full / fraction, ABC) อยู่ใน `zone_properties` ของโรงงาน

DB ตรวจไม่ได้ว่า `level_no ≤ max_level` เพราะอยู่คนละตาราง แอปต้องตรวจ

## query ที่ใช้บ่อย

```sql
-- สรุป QC
SELECT qc_status, COUNT(*) AS pallets, SUM(qty) AS qty
FROM pallets WHERE sku IS NOT NULL AND deleted_at IS NULL
GROUP BY qc_status;

-- พาเลทที่ถูกล็อก
SELECT code, sku, lot_no, location_code, qc_lock_reason
FROM pallets WHERE qc_status = 'locked';

-- stock ที่พร้อมจ่าย แยกคลังและสินค้า
SELECT l.warehouse_code, p.sku, COUNT(*) AS pallets, SUM(p.qty) AS qty
FROM pallets p JOIN locations l ON l.code = p.location_code
WHERE p.qc_status = 'passed'
GROUP BY l.warehouse_code, p.sku;

-- ของในตำแหน่งหนึ่ง
SELECT code, sku, lot_no, qty, qc_status FROM pallets WHERE location_code = 'tl-w3-1-0102';

-- ตำแหน่งว่าง
SELECT l.code FROM locations l
WHERE l.is_enabled = 1 AND l.deleted_at IS NULL
  AND NOT EXISTS (SELECT 1 FROM pallets p WHERE p.location_code = l.code);

-- พาเลทนอกคลัง
SELECT code, sku, left_at FROM pallets WHERE left_at IS NOT NULL;
```
