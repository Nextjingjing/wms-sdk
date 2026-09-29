# เริ่มต้น

**ภาษาไทย** | [English](../en/getting-started.md)

## สิ่งที่ต้องมี

- Python 3.11 ขึ้นไป
- ไม่ต้องมี SQL Server สำหรับการพัฒนา — test และฐานข้อมูลลองเล่นใช้ SQLite

คำสั่งในหน้านี้เขียนแบบ Windows (`.venv\Scripts\python`) บน Linux / macOS ใช้ `.venv/bin/python`

## ติดตั้ง

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` มี SQLAlchemy, pyodbc, pytest และ networkx / shapely สำหรับ feature เสริม

## โครงสร้าง repo

```
wms_sdk/                 ตัว SDK — ส่วนเดียวที่ถูก build เป็น package
  core/                  Base, Lookup, Interface, errors
  shared/models/         plants, roles, users
  modules/master_data/   products, product_properties, plant_products
  modules/storage/       warehouses, zones, locations (+ properties)
  modules/inventory/     pallets, QC, ชื่อ event มาตรฐาน
  modules/events/        event_log, inbox, outbox, ตัวจับการเปลี่ยนแปลง
  features/              ส่วนเสริมที่เลือกเปิด: machines, brand, floor_map, routing
  testing/sqlite.py      SQLite แทน SQL Server สำหรับ test
  checks.py              verify_factory()
  metadata.py            import เพื่อลงทะเบียนตาราง core ทั้งหมด
examples/minimal_factory/  โรงงานที่เล็กที่สุด (ดู Tutorial)
examples/reference_factory/    ตัวอย่างโปรเจกต์โรงงานอ้างอิง เปิดทุก feature
examples/cookbook/       สูตรที่รันได้บนตัวอย่างอ้างอิง
dev/                     เครื่องมือของ repo นี้: create_db, mock, gen_schema_doc
tests/                   pytest
docs/                    เอกสารนี้ (en / th)
```

## รัน test

```bash
.venv\Scripts\python -m pytest                                    # ทั้งหมด
.venv\Scripts\python -m pytest tests/test_quality.py              # ไฟล์เดียว
.venv\Scripts\python -m pytest tests/test_routing.py -k publish   # เฉพาะ test ที่ชื่อมีคำนี้
```

test ทุกตัวรันบน SQLite ในหน่วยความจำ แต่ละ test ได้ฐานข้อมูลใหม่ (fixture `session` ใน `tests/conftest.py`)

### บน SQL Server

ถ้าตั้ง `WMS_TEST_MSSQL_URL` ไว้ test ชุดเดียวกันจะรันบน SQL Server จริง แต่ละ test ได้ database ที่สร้างใหม่ชื่อ `wms_test_<name>` บน server นั้น (ตัวช่วยจะไม่ยอมลบ database ที่ชื่อไม่มีคำว่า "test") รัน server ในเครื่องด้วย Docker ได้:

```powershell
$env:MSSQL_SA_PASSWORD = '<ตั้งรหัสผ่านเอง>'          # บังคับตั้ง ไม่มีค่า default ไว้ให้ commit
docker compose -f dev/mssql/compose.yml up -d        # SQL Server 2022 ที่ 127.0.0.1:14333
$env:WMS_TEST_MSSQL_URL = "mssql+pyodbc://sa:$env:MSSQL_SA_PASSWORD@127.0.0.1,14333/x?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
.venv\Scripts\python -m pytest                       # ประมาณ 5 นาที เพราะทุก test สร้าง database ใหม่
```

`tests/test_alembic.py` รันเฉพาะตอนนี้: migrate database เปล่าด้วย migration ของตัวอย่างอ้างอิง, ตรวจว่าไม่ต่างจาก model แล้ว downgrade กลับเป็นว่าง

| ไฟล์ | ตรวจ |
|---|---|
| `test_constraints.py` | CHECK / UNIQUE ของตำแหน่งและพาเลท |
| `test_quality.py` | การเปลี่ยนสถานะ QC และเหตุผลที่ล็อก |
| `test_events.py` | การบันทึกลง event_log, outbox, inbox |
| `test_factory.py` | interface ที่ไม่ได้ implement, feature, verify_factory |
| `test_routing.py`, `test_floor_map.py` | feature เสริม |
| `test_schema.py` | ชื่อ constraint ไม่ซ้ำ ไม่ยาวเกิน ไม่มี NTEXT, FK ทุกตัวมี index, filtered index กรองบน SQLite ด้วย |
| `test_map_file.py` | export / import ไฟล์ `.wmsmap` |
| `test_alembic.py` | migration ของตัวอย่างอ้างอิง ตรงกับ model (เฉพาะบน SQL Server) |
| `test_mock.py` | ข้อมูลตัวอย่างยังโหลดได้ |
| `test_docs.py` | `docs/*/schema.md` ตรงกับโค้ด; en / th มีหน้าตรงกัน; ลิงก์ใช้ได้ |
| `test_examples.py` | ตัวอย่างทุกชิ้นใน `examples/` ยังรันได้ |

## รันตัวอย่าง

```bash
.venv\Scripts\python -m examples.minimal_factory.main
.venv\Scripts\python -m examples.cookbook.pallet_lifecycle
.venv\Scripts\python -m examples.cookbook.map_and_routing
.venv\Scripts\python -m examples.cookbook.dispatch_tasks
.venv\Scripts\python -m examples.cookbook.share_map
```

แต่ละตัวแสดงอะไร: [ตัวอย่าง](examples.md)

## ฐานข้อมูลลองเล่น

```bash
.venv\Scripts\python -m dev.create_db            # dev.sqlite: schema ครบ + lookup ของตัวอย่างอ้างอิง
.venv\Scripts\python -m dev.create_db --mock     # + ข้อมูลตัวอย่าง
```

สร้างไฟล์ใหม่ทุกครั้ง ไฟล์ `*.sqlite` ไม่ถูก commit

ข้อมูลตัวอย่าง (`dev/mock.py`) เป็นข้อมูลสมมุติ รหัสขึ้นต้นด้วย `MOCK-` / `mock.` และได้ชุดเดิมทุกครั้ง:

- โรงงาน TL (C221), คลัง W1 และ W2, คลังละ 3 โซน
- 60 ตำแหน่ง บางตำแหน่งปิดใช้ (`is_enabled = 0`)
- สินค้า 5 รายการ, เครื่องจักร 3 ตัว, ผู้ใช้ 3 คน (Lab 1, Forklift 2)
- พาเลท 130 ใบ: มีของ 120 (waiting / locked / passed), ว่าง 10, บางใบส่งออกไปแล้ว
- ประวัติใน `event_log`, ข้อความใน outbox (ไป `sap`) และ inbox 1 ข้อความ

เปิด `dev.sqlite` ด้วย DB Browser for SQLite, DBeaver หรือ extension ของ VS Code แล้วลอง query ใน [inventory.md](inventory.md#query-ที่ใช้บ่อย)

SQLite ใช้ `json_extract` แทน `JSON_VALUE` ของ SQL Server

## ดู DDL ของ SQL Server

```bash
.venv\Scripts\python -c "from sqlalchemy.schema import CreateTable; from sqlalchemy.dialects import mssql; from wms_sdk.metadata import metadata; import examples.reference_factory.seed; [print(CreateTable(t).compile(dialect=mssql.dialect())) for t in metadata.sorted_tables]"
```

## แก้ schema แล้วต้องทำอะไร

1. รัน test
2. `python -m dev.gen_schema_doc` เพื่ออัปเดต [schema.md](schema.md) ทั้งสองภาษา (ถ้าลืม `test_docs.py` จะล้ม)
3. ถ้าข้อมูลตัวอย่างโหลดไม่ได้ แก้ `dev/mock.py`

## SQLite ต่างจาก SQL Server ตรงไหน

`wms_sdk/testing/sqlite.py` แปลงส่วนที่เป็นของ SQL Server ให้ SQLite ใช้ได้ (DATETIME2, `sysutcdatetime()`, `ISJSON`, schema `messaging`) สิ่งที่ SQLite ยังพิสูจน์แทนไม่ได้:

- `ISJSON` ของจริง — ใน SQLite เป็นฟังก์ชันจำลอง
- ความละเอียดของ `DATETIME2`
- การเรียงตัวอักษรตาม collation ของ SQL Server (มีผลกับ `road_start_code < road_end_code` ใน routing)

unique index ที่กรองแถวพิสูจน์ได้ เพราะทุกตัวใส่ทั้ง `mssql_where` และ `sqlite_where` (`tests/test_schema.py` คอยตรวจ)

test ทั้งชุดผ่านบน SQL Server 2022 ด้วย รวมถึง Alembic migration ของตัวอย่างอ้างอิง ดู [บน SQL Server](#บน-sql-server) หลังแก้ constraint หรือ index ควรรันบน SQL Server อีกครั้ง
