# แก้ปัญหา

**ภาษาไทย** | [English](../en/troubleshooting.md)

error แสดงตามข้อความจริงที่ SDK raise

## ตอนเริ่มระบบ

### `RuntimeError: no operation started; call start_operation(session, actor) first`

session flush การแก้ข้อมูลโดยไม่มี operation การเขียนทุกครั้ง รวมถึง seed และสคริปต์ ต้องเริ่ม operation ก่อน:

```python
start_operation(session, actor="somchai")   # หรือ actor=None สำหรับงานของระบบ
...
session.commit()
```

### `NotImplementedError: no factory implements <table>; subclass <XBase> together with Base`

interface ยังไม่มีคลาสที่ implement ส่วนใหญ่เป็นเพราะไม่ได้ import model ของโรงงานก่อน `verify_factory` ให้ import ตอนเริ่มระบบ (`import my_factory.models`) หรือเพิ่มคลาสที่ขาด `class Pallet(PalletBase, Base): ...` ส่วน interface ของ feature (`TaskBase`) บังคับเฉพาะเมื่อ import feature นั้น

### `LookupNotSeeded: table 'roles' is empty; seed it first`

ตาราง lookup ทุกตัวที่ถูก import ต้องมีข้อมูล รวมถึงของ feature ที่เปิด (`machine_groups`, `brands`, `task_types`, `task_statuses` ...) ให้รัน seed ของโรงงานก่อน `verify_factory`

### `TypeError: <table> already implemented by <A>; <B> cannot implement it again`

มีสองคลาส implement interface เดียวกันใน process เดียว ให้เหลือตัวเดียวต่อ interface ถ้า test ต้องใช้หลายโรงงาน ให้รันแยก process (ดู `tests/test_factory.py`)

### `TypeError: <Class>: put constraints in extra_table_args`

คลาสที่ implement interface ประกาศ `__table_args__` ซึ่งจะทับ constraint ของ key ให้ใช้ `extra_table_args = (...)` แทน

### `TypeError: <Class>: reservation_columns needs active_statuses`

คลาสที่ implement `TaskBase` ตั้ง `reservation_columns` แต่ไม่ได้บอกว่าสถานะไหนยังไม่เสร็จ ให้เพิ่ม `active_statuses = (...)`

### `ImportError: routing needs networkx: pip install "wms-sdk[routing]"`

รวมถึง `floor_map geometry needs shapely: pip install "wms-sdk[floor_map]"` ฟังก์ชันช่วยต้องใช้ตัวเลือกเสริม ส่วนตารางของ feature ไม่ต้องใช้ ติดตั้งตัวเลือกตามที่ข้อความบอก

## กฎของข้อมูล

### `IntegrityError` ตอน insert หรือ update

DB ปฏิเสธแถวนั้น สาเหตุที่พบบ่อย:

| สถานการณ์ | กฎที่ปฏิเสธ |
|---|---|
| พาเลทมี sku แต่ไม่มี qty หรือ `qty = 0` | `ck_pallets_load_complete` |
| วางพาเลทว่างในตำแหน่ง | `ck_pallets_stored_pallet_has_load` |
| สองพาเลทในตำแหน่งเดียวกัน (ตัวอย่างอ้างอิง) | `uq_pallets_position` |
| สองงานที่ยังไม่เสร็จจองที่เดียวกัน | `uq_tasks_reservation` |
| ล็อกพาเลทโดยไม่มีเหตุผล | `ck_pallets_qc_lock_reason_when_locked` |
| ใช้ code ที่ไม่มีในตาราง lookup | FK ไปตาราง lookup นั้น |
| insert ผิดลำดับ | FK: ต้อง flush แถวแม่ก่อน (ไม่มี relationship ของ ORM) |

ชื่อ constraint ในข้อความ error บอกว่าเป็นกฎข้อไหน กฎทั้งหมดอยู่ใน [Schema reference](schema.md)

### `InvalidQcTransition: pallet P-0001: waiting -> waiting is not allowed`

เปลี่ยนได้เฉพาะตาม `QC_TRANSITIONS`: waiting → passed / locked, locked → passed, passed → locked ของที่ใส่ใหม่เริ่มที่ `WAITING`

### `MissingLockReason: pallet P-0001: locking needs a reason`

`set_qc_status(session, pallet, QcStatus.LOCKED, reason="...")` ต้องมีเหตุผลที่ไม่ใช่ข้อความว่าง

### `NotShippable: pallet P-0002 is locked, not passed`

`ensure_shippable` ปฏิเสธพาเลทที่สถานะ QC ไม่ใช่ `passed` ต้องเรียกก่อนส่งทุกครั้ง

### `InvalidTaskStatus: task 1: open -> done is not allowed`

การเปลี่ยนนี้ไม่อยู่ใน `transitions` ของโรงงาน งานใหม่ต้องเริ่มที่สถานะที่อนุญาตจาก `None`

### `LocationInUse: locations still hold pallets: [...]`

การบันทึก column ที่สั้นลงหรือการลบ column จะเลิกใช้ตำแหน่งที่ยังมีพาเลท ย้ายพาเลทออกก่อน ไม่มีอะไรถูกเปลี่ยน

### `ValueError: column 2 is in zone ['1']; delete it before adding it to zone 2`

ตัวอย่างอ้างอิง: ย้าย column ไปโซนอื่นทำให้รหัสตำแหน่งเปลี่ยน ให้เรียก `delete_column` ก่อน แล้วบันทึกใหม่ในโซนใหม่

### `NotSet: product_properties has no row for 'A001'`

รวมถึง `warehouse C221/W1 has no published route map` แถวนั้นยังไม่ได้ตั้ง ซึ่งเป็นสถานะจริง ไม่ใช่ค่า default ให้สร้างแถวนั้น (หรือเผยแพร่แผนที่ถนน) ก่อน

### CHECK ปล่อย NULL ผ่าน

CHECK ผ่านเมื่อผลเป็น UNKNOWN เวลาเขียน CHECK ที่มีคอลัมน์ NULL ได้ ให้เพิ่ม `col IS NOT NULL` ให้ชัด ดู [แนวคิดการออกแบบ](concepts.md#8-ให้-db-บังคับกฎ)

## ไฟล์แมพ (`.wmsmap`)

### `WarehouseExists: warehouse C221/W1 already exists`

import สร้างได้แค่คลังใหม่ ไม่เขียนทับคลังที่มีอยู่ ถ้าต้องการแทนที่ ให้ import เข้า database ที่ยังไม่มีคลังนั้น

### `LocationCodeTaken: location codes already in use: [...]`

รหัส location ห้ามซ้ำทุกคลัง และคลังอื่นในฝั่งนี้ใช้รหัสบางตัวในไฟล์ไปแล้ว ยังไม่มีอะไรถูกเขียน ให้เปลี่ยนรหัส location ฝั่งใดฝั่งหนึ่ง หรือ import เข้า database อื่น

### `PropertiesMismatch: location_properties: file has columns [...], this factory has [...]`

ไฟล์มาจากโรงงานที่ `zone_properties` / `location_properties` มีคอลัมน์ต่างกัน ใช้ `import_map(..., properties=False)` เพื่อเอาทุกอย่างยกเว้น properties แล้วค่อยกรอก properties เอง

### `UnsupportedMapFile: ...`

- `manifest.json is missing`: ไฟล์นี้ไม่ใช่ `.wmsmap`
- `expected wmsmap version 1, got ...`: ไฟล์เขียนโดย SDK ที่ใช้รูปแบบไฟล์ต่างกัน ให้สองฝั่งใช้ SDK เวอร์ชันเดียวกัน
- `image path must be relative, inside image_root`: path รูปในไฟล์ชี้ออกนอก `image_root` (`..` หรือ path เต็ม) ไฟล์ถูกแก้ด้วยมือหรือไม่น่าไว้ใจ ยังไม่มีอะไรถูกเขียน
- `pictures missing from the file`: ZIP ถูกแก้แล้วรูปหายไป

### `ValueError: the warehouse has pictures [...]: pass image_root`

ตอน import ข้อความจะเป็น `the file has pictures [...]: pass image_root` ทั้ง export และ import ต้องมี `image_root` (โฟลเดอร์ที่ path รูปใน database อ้างอิง) เมื่อคลังมีรูปผังโรงงานหรือรูปพื้นหลัง

## การติดตั้งและเครื่องมือ

### `pip install ... git+https://github.com/...` ล้มด้วย "Repository not found" หรือถามรหัสผ่าน

repo เป็น private ขอสิทธิ์เข้าก่อน แล้ว login: ดู [การติดตั้ง](installation.md#เข้าสู่ระบบสำหรับ-repo-private)

### `tests/test_docs.py` ล้ม: `docs/en/schema.md is stale`

schema เปลี่ยน ให้รัน `python -m dev.gen_schema_doc` แล้ว commit ไฟล์ที่สร้างใหม่

### `tests/test_mock.py` หรือ `tests/test_examples.py` ล้มหลังแก้ schema

แก้ `dev/mock.py` หรือตัวอย่างใน `examples/` ให้ตรงกับ schema ใหม่ ทั้งสองอย่างเป็นเอกสารและต้องรันได้เสมอ

### SQL Server ทำงานไม่เหมือนตอน test

โดยปกติ test รันบน SQLite ถ้าจะรันบน SQL Server ให้ตั้ง `WMS_TEST_MSSQL_URL` (ดู [เริ่มต้น](getting-started.md#บน-sql-server)) ส่วนการเรียงตาม collation และความละเอียดของ `DATETIME2` อาจต่างกัน ดู [SQLite ต่างจาก SQL Server ตรงไหน](getting-started.md#sqlite-ต่างจาก-sql-server-ตรงไหน)

### `alembic check` รายงาน `remove_fk` / `add_fk` ของ `fk_outbox_event_id_event_log` ทุกครั้ง

FK จาก `messaging.outbox` ไป `event_log` ถูกอ่านกลับมาเป็น `dbo.event_log` ให้ copy ฟังก์ชัน `drop_default_schema_fk_noise` จาก [`migrations/env.py`](../../examples/reference_factory/migrations/env.py) ของตัวอย่างอ้างอิง ไปใส่ใน `env.py` ของคุณ
