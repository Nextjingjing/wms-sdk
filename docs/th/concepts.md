# แนวคิดการออกแบบ

**ภาษาไทย** | [English](../en/concepts.md)

หน้านี้อธิบาย **ทำไม** schema หน้าตาแบบนี้ ถ้าจะเพิ่มหรือแก้ตาราง ให้ทำตามหลักเหล่านี้

## 1. SDK เดียว หลายโรงงาน

schema ถูกแบ่งเป็น 3 แบบ ตามว่าทุกโรงงานต้องมีหรือไม่

| แบบ | ตัวอย่าง | ถ้าโรงงานไม่ทำอะไร |
|---|---|---|
| **core** | `plants`, `products`, `locations`, `event_log` | มีตารางเสมอ |
| **interface** | `product_properties`, `zone_properties`, `location_properties`, `pallets`; `tasks` เมื่อ import feature tasks | `verify_factory` raise — ต้อง implement |
| **feature** | `machines`, `brands`, `floor_map`, `routing`, `tasks` | ไม่มีตาราง ไม่ error |

- ของที่ **ทุก** WMS ต้องมี → core
- ของที่ทุกโรงมี แต่ **คอลัมน์ต่างกัน** → interface: SDK กำหนดชื่อตารางและ key โรงงานเพิ่มคอลัมน์
- ของที่ **หลาย** โรงมีแต่ไม่ทุกโรง → feature
- ของที่มี **โรงเดียว** → ตารางของโรงงานเอง (เช่น `ticket_formats` ของตัวอย่างอ้างอิง)

ทิศทางการพึ่งพา: feature พึ่ง core ได้ core ห้ามพึ่ง feature (ไม่อย่างนั้น feature จะมีในทุกโรงทันที)

## 2. ใช้ key ธรรมชาติ ไม่ใช้ id ที่ไม่มีความหมาย

ทุกตารางใช้ค่าที่คนใช้เรียกจริงเป็น primary key:

| ตาราง | PK |
|---|---|
| `plants` | `code` (เช่น `C221`) |
| `products` | `sku` |
| `users` | `username` |
| `warehouses` | `(plant_code, code)` |
| `locations` | `code` (เช่น `tl-w3-1-0102`) |
| `pallets` | `code` (รหัสบน QR) |

ผลคือ query อ่านรู้เรื่องโดยไม่ต้อง join:

```sql
SELECT * FROM machines WHERE plant_code = 'C221';          -- ไม่ต้อง join plants
SELECT * FROM pallets WHERE location_code = 'tl-w3-1-0102'; -- ไม่ต้อง join locations
```

ใช้ `id` แบบ auto-increment เฉพาะตารางที่ไม่มี key ธรรมชาติจริง ๆ — มีตัวเดียวคือ `event_log` (event ไม่มีชื่อ)

FK หลายคอลัมน์ช่วยให้ DB บังคับกฎข้ามตารางได้ เช่น `product_source_machines` ใช้ `plant_code` ตัวเดียวกันใน FK ไป `plant_products` และไป `machines` จึงรับประกันว่าเครื่องอยู่โรงเดียวกับที่ผลิตสินค้านั้น

## 3. ค่าที่เป็นชุด: lookup หรือ enum

| ใช้ | เมื่อ | ตัวอย่าง |
|---|---|---|
| **ตาราง lookup** (`code` เป็น PK) | แต่ละโรงมีชุดค่าต่างกัน | `roles`, `machine_groups`, `brands` |
| **StrEnum + CHECK** | SDK ต้องรู้ความหมายของค่า | `QcStatus` (`passed` = ส่งได้), `RouteStatus` |

ไม่ใช้เลข (`role_id = 5`) — ค่าใน DB ต้องอ่านรู้เรื่องโดยไม่ต้องเปิดโค้ด

ตาราง lookup ทุกตัวสืบทอด `Lookup` (ไม่มีคอลัมน์ในตัว — แค่บอกว่าเป็น lookup) และประกาศ `code`, `name` เอง `verify_factory` หาตาราง lookup ที่ถูก import ทั้งหมดแล้วตรวจว่า seed แล้ว

การเปลี่ยนสถานะของ enum ทำผ่านตารางเดียวในโค้ด เช่น `QC_TRANSITIONS` ไม่กระจายไปหลายที่

## 4. ไม่มีค่า default ปลอม

- ไม่ใส่ `0` หรือ `''` เพื่อให้ insert ผ่าน — ค่าที่ยังไม่รู้คือยังไม่มี
- NOT NULL = ต้องมี, NULL = **ไม่มีจริง** (ไม่ใช่ "ยังไม่รู้")
- ข้อมูลที่อาจยังไม่รู้ตอนสร้าง แยกไปอยู่ตาราง properties: ไม่มีแถว = ยังไม่ได้ตั้ง และ `get_row()` raise `NotSet`
- default ที่เป็นค่าจริงใช้ได้ เช่น `is_enabled = 1` (ตำแหน่งใหม่เปิดใช้) หรือ `clearance_m = 3.00`

## 5. เขียนคอลัมน์ให้เห็นในทุกคลาส

ไม่ใช้ mixin ที่ซ่อนคอลัมน์ เปิดไฟล์ model แล้วต้องเห็นทุกคอลัมน์ของตาราง แม้ `created_at` / `updated_at` จะซ้ำกันหลายไฟล์ ข้อยกเว้นคือ mixin ของ feature (`HasBrand`) ที่ตั้งใจเพิ่มคอลัมน์ให้ตารางของโรงงาน

ตารางที่แถวไม่มีวันถูกแก้ (ตาราง link เช่น `plant_products`) มีแค่ `created_at`

## 6. ลบแบบ soft delete

ตารางที่ถูกอ้างถึง (plants, users, products, locations, pallets …) ใช้ `deleted_at`:

- `NULL` = ยังใช้อยู่, มีค่า = เลิกใช้เมื่อเวลานั้น
- กู้คืน = ตั้งกลับเป็น NULL
- key ธรรมชาติของแถวที่ถูกลบยังจองอยู่ (สร้าง `sku` เดิมใหม่ไม่ได้ ต้องกู้คืน)

ตาราง link และร่างของ route map ลบแถวจริงได้ ประวัติอยู่ใน `event_log`

## 7. ไม่เก็บของที่ไม่มีเหตุผล

ทุกตารางและคอลัมน์ต้องตอบได้ว่าข้อมูลของคลังต้องใช้ ไม่ใช่หน้าจอต้องใช้:

- login, รหัสผ่าน, หน้าแรกหลัง login, ลำดับการแสดงผล → แอป
- ประวัติการแก้ → `event_log` ไม่ต้องมีตาราง history แยกต่อตาราง
- ยอดคงเหลือ → คำนวณจาก `pallets` ไม่มีตาราง balance

## 8. ให้ DB บังคับกฎ

ถ้ากฎเขียนเป็น CHECK / FK / UNIQUE ได้ ให้ DB บังคับ ไม่ใช่แอปอย่างเดียว เพราะข้อมูลอาจเข้ามาจากสคริปต์หรือระบบอื่น

ข้อควรระวัง: **CHECK ผ่านเมื่อผลเป็น UNKNOWN** `qty > 0` เมื่อ `qty` เป็น NULL ได้ UNKNOWN แถวจึงผ่าน ใน CHECK ที่มีคอลัมน์ NULL ได้ ต้องเขียน `IS NOT NULL` ให้ชัด:

```sql
-- ผิด: sku มีค่าแต่ qty เป็น NULL ก็ผ่าน
CHECK ((sku IS NULL AND qty IS NULL) OR (sku IS NOT NULL AND qty > 0))
-- ถูก
CHECK ((sku IS NULL AND qty IS NULL) OR (sku IS NOT NULL AND qty IS NOT NULL AND qty > 0))
```

กฎที่ DB บังคับไม่ได้ (ข้ามตาราง หรือขึ้นกับการกระทำ) มีฟังก์ชันใน SDK เช่น `ensure_shippable()` และแอปต้องเรียกเสมอ

## 9. ข้อตกลงของ SQL Server

- ข้อความภาษาไทย: `NVARCHAR` (`Unicode`); รหัส: `VARCHAR` (`String`)
- ข้อความไม่จำกัดความยาว: `Unicode()` → `NVARCHAR(max)` ห้าม `UnicodeText` (→ `NTEXT` ที่ `ISJSON` ใช้ไม่ได้)
- เวลา: `DATETIME2` เวลา UTC จาก `sysutcdatetime()`
- ชื่อ constraint กำหนดด้วย naming convention ใน `core/db.py` (MSSQL จะสุ่มชื่อถ้าไม่ตั้ง แล้ว Alembic แก้ไม่ได้) — ยกเว้น DEFAULT constraint ซึ่งต้องลบด้วย `op.alter_column(..., mssql_drop_default=True)`
- unique index ที่กรองแถวใส่ทั้ง `mssql_where` และ `sqlite_where`
- SQL Server ไม่สร้าง index ให้คอลัมน์ FK เอง: FK ทุกตัวต้องเป็นคอลัมน์นำของ index หรือ key ยกเว้น FK ไปตาราง lookup (แทบไม่มีการลบแถว index มีแต่ทำให้เขียนช้าลง) และตารางเล็กมากไม่กี่ตาราง `tests/test_schema.py` คอยตรวจ และระบุข้อยกเว้นพร้อมเหตุผลไว้
- ตารางข้อมูลคลังอยู่ schema `dbo`; `inbox` / `outbox` อยู่ schema `messaging`
