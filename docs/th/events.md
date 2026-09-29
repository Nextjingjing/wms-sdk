# event log, inbox, outbox

**ภาษาไทย** | [English](../en/events.md)

```
การกระทำของผู้ใช้
  │ start_operation(session, actor)
  ├─ แก้ข้อมูล ──────────► event_log   (อัตโนมัติ: <table>.inserted / updated / deleted)
  ├─ record_event(...) ──► event_log   (event ทางธุรกิจ เช่น pallet.putaway)
  │                        └─► messaging.outbox  (ถ้าระบุ destinations)
  └─ commit

ระบบภายนอก ──► receive_message(...) ──► messaging.inbox ──► worker ประมวลผล
```

## event_log

ตารางเดียวเก็บทุกอย่างที่เกิดใน WMS บันทึกเพิ่มอย่างเดียว

| คอลัมน์ | ความหมาย |
|---|---|
| `id` | ลำดับ (ตารางเดียวที่ใช้ id — event ไม่มี key ธรรมชาติ) |
| `event_type` | `<subject>.<verb>` เช่น `products.updated`, `pallet.putaway` |
| `subject_table`, `subject_key` | แถวที่ถูกแก้ เช่น `products`, `{"sku": "A001"}` (NULL สำหรับ event ทางธุรกิจ) |
| `payload` | JSON: การแก้ข้อมูล = `{"คอลัมน์": [ค่าเดิม, ค่าใหม่]}`; event ทางธุรกิจ = อะไรก็ได้ |
| `operation_id` | ผูกทุก event ที่เกิดจากการกระทำเดียวกัน |
| `actor` | username (FK → users) หรือ NULL = ระบบ |
| `occurred_at` | เวลา UTC |

### ตั้งค่าครั้งเดียว

```python
from wms_sdk.modules.events.capture import install_capture
install_capture(Session)       # Session = sessionmaker(...)
```

### ทุกการกระทำ

```python
from wms_sdk.modules.events.capture import record_event, start_operation

operation_id = start_operation(session, actor="somchai")
product.name_thai = "ปูนใหม่"                         # → products.updated อัตโนมัติ
record_event(session, "putaway.completed", {"sku": "A001"}, destinations=["sap"])
session.commit()
```

- flush โดยไม่เรียก `start_operation` → `RuntimeError`
- ตั้งค่าเดิมซ้ำ (ไม่ได้เปลี่ยนจริง) ไม่ถูกบันทึก
- ตาราง `messaging.*` ไม่ถูกบันทึกลง event_log
- `updated_at` ไม่อยู่ใน payload (DB ตั้งค่าตอน flush) ใช้ `occurred_at` แทน

### ข้อควรรู้

- event_log คือ **ประวัติ** ไม่ใช่แหล่งข้อมูล — ยอด stock ดูจาก `pallets`
- เป็นแหล่งเดียวของประวัติพาเลท ห้ามลบข้อมูลเก่าที่ยังต้องใช้ย้อนดู
- `subject_key` เป็น JSON เรียง key และมีช่องว่างหลัง `:` (`{"code": "P1"}`) ต้องพิมพ์ตรงทุกตัวอักษรเมื่อ query
- `actor` เก็บ username ไม่ใช่ role — ถ้าผู้ใช้เปลี่ยน role รายงานย้อนหลังจะเห็น role ปัจจุบัน

### query

```sql
-- ประวัติของแถวหนึ่ง (มี index)
SELECT occurred_at, actor, event_type, payload FROM event_log
WHERE subject_table = 'pallets' AND subject_key = '{"code": "P-000123"}'
ORDER BY occurred_at;

-- ทุกอย่างที่เกิดจากการกดปุ่มครั้งเดียว (มี index)
SELECT event_type, subject_key, payload FROM event_log WHERE operation_id = @op;

-- ใครล็อกพาเลทอะไร (SQL Server)
SELECT occurred_at, actor, JSON_VALUE(payload, '$.pallet') AS pallet,
       JSON_VALUE(payload, '$.reason') AS reason
FROM event_log WHERE event_type = 'pallet.qc_locked';
```

## outbox — ส่งข้อมูลออก

`record_event(..., destinations=["sap", "notify"])` เพิ่มแถวใน `messaging.outbox` หนึ่งแถวต่อปลายทาง ใน transaction เดียวกับ event จึงไม่หายแม้ส่งไม่สำเร็จ

| คอลัมน์ | ความหมาย |
|---|---|
| `event_id`, `destination` | PK |
| `sent_at` | NULL = ยังไม่ส่ง |
| `attempts`, `last_error` | สำหรับลองใหม่ |

worker (ของแอป ไม่ได้อยู่ใน SDK) อ่านแถวที่ยังไม่ส่ง:

```sql
SELECT o.event_id, o.destination, e.event_type, e.payload
FROM messaging.outbox o JOIN event_log e ON e.id = o.event_id
WHERE o.sent_at IS NULL;          -- มี index ที่กรองเฉพาะแถวนี้
```

ส่งสำเร็จ → ตั้ง `sent_at`; ล้มเหลว → เพิ่ม `attempts` และเก็บ `last_error`

## inbox — รับข้อมูลเข้า

```python
from wms_sdk.modules.events.receive import receive_message

if receive_message(session, "sap", "MSG-001", "sales_order.created", {"order": "SO1"}):
    session.commit()      # ครั้งแรก
# ได้ข้อความเดิมซ้ำ → คืน False ไม่บันทึกซ้ำ
```

- PK คือ `(source, message_id)` ใช้ id ของระบบต้นทาง กันข้อความซ้ำที่ระดับ DB
- worker ประมวลผลแถวที่ `processed_at IS NULL` เรียงตาม `received_at` แล้วตั้ง `processed_at`
- การรับข้อความไม่ต้องเรียก `start_operation`; การประมวลผล (สร้าง order ฯลฯ) ต้องเรียก `start_operation(session, actor=None)` เหมือนงานอื่น

## schema

`inbox` และ `outbox` อยู่ใน schema `messaging` แยกจากข้อมูลคลังใน `dbo` ให้สิทธิ์แยกได้ เช่น worker เข้าถึงแค่ `messaging`
