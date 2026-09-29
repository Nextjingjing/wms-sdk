# สร้างโปรเจกต์ของโรงงาน

**ภาษาไทย** | [English](../en/factory-guide.md)

โรงงานแต่ละแห่งมีโปรเจกต์ของตัวเอง แล้วติดตั้ง SDK เป็น package ถ้าเพิ่งเริ่ม ให้ทำ [Tutorial](tutorial.md) ก่อน ซึ่งสร้างโรงงานที่เล็กที่สุด [`examples/minimal_factory/`](../../examples/minimal_factory) ตัวอย่างที่ครบที่สุดคือ [`examples/reference_factory/`](../../examples/reference_factory)

```
my_factory/
  models.py      implement interface, เปิด feature, ตาราง lookup ของโรงงาน
  seed.py        ค่าของตาราง lookup
  roles.py       enum ของ role (ไม่บังคับ)
  alembic/       migration ของโรงงาน
tests/
```

## เริ่มเร็ว: เจนโปรเจกต์

`wms-sdk init` เขียนทั้งโปรเจกต์ให้ โดยทำหัวข้อด้านล่างไว้แล้ว และใส่ `TODO(wms)` ตรงที่โรงงานต้องตัดสินใจเอง โปรเจกต์ยังได้ **สำเนาของ SDK** ใน `wms_sdk/` (เฉพาะ feature ที่เลือก) ด้วย ทีมของโรงงาน, CI และ image จึงไม่ต้องติดตั้งอะไรจาก repo private และไม่ต้องมีสิทธิ์เข้า GitHub คนที่ต้องติดตั้ง SDK มีแค่คนที่รัน `wms-sdk`:

```bash
pip install "wms-sdk[mssql] @ git+https://github.com/Nextjingjing/wms-sdk.git@v0.1.2"
wms-sdk init                                    # หรือ: python -m wms_sdk init
```

CLI จะถามชื่อ package แล้วแสดงเมนู: ลูกศรขึ้น/ลงเพื่อเลื่อน, spacebar เพื่อติ๊ก, Enter เพื่อยืนยัน

```
Optional features (up/down move, space select, Enter confirm)
  [ ] brand      brands, and brand_code on product properties
  [ ] machines   production machines and machine groups
  [ ] floor_map  warehouse drawings and the map builder
  [ ] routing    forklift road network and shortest routes
  [x] tasks      work orders (forklift, QC, dispatch) and location reservations
  [ ] map_file   export / import a warehouse as .wmsmap (adds floor_map, routing)
> [x] container  Containerfile to build an image (Podman / Docker)
```

หรือใส่ทุกอย่างในคำสั่งเลย (ไม่ถามอะไร ใช้ใน script ได้):

```bash
wms-sdk init demo_plant --features tasks --container
```

```
Created demo_plant: 16 files + wms_sdk/ (copy of wms-sdk 0.1.2, 46 files)
Features: tasks. Container: yes.

Next:
  cd demo_plant
  1. Fill in every TODO(wms): demo_plant/models.py, roles.py, seed.py
  2. pip install -r requirements-dev.txt, then python -m pytest
  3. Database and container image: README.md
```

| ตัวเลือก | |
|---|---|
| `--features a,b` | brand, machines, floor_map, routing, tasks, map_file (map_file เพิ่ม floor_map และ routing ให้เอง) ถ้าไม่ใส่: รันใน terminal จะแสดงเมนู ถ้าไม่ใช่ terminal จะไม่เปิด feature ใด |
| `--container` | เพิ่ม `Containerfile`, `.containerignore`, `.env.example` (ค่าเริ่มต้น: ไม่เพิ่ม) |
| `--dir PATH` | โฟลเดอร์ที่จะเขียน (ค่าเริ่มต้น `./<package>`) |
| `--dry-run` | แสดงรายการไฟล์ ไม่เขียนจริง |
| `--force` | เขียนทับไฟล์ที่เจนในโฟลเดอร์ที่ไม่ว่าง ไฟล์อื่นไม่ถูกแตะ |

สิ่งที่ได้:

- `wms_sdk/`: ตัว SDK เอง import ได้ตามปกติ (`import wms_sdk...`) เมื่อรัน Python จากโฟลเดอร์โปรเจกต์ ห้ามแก้ (ดูด้านล่าง)
- `models.py`: คลาสละหนึ่งตัวต่อ interface (และ `Task` ถ้าเลือก tasks) เปิด feature ให้แล้ว
- `seed.py`: dict ว่างหนึ่งตัวต่อ lookup ถ้ายังว่าง `seed()` จะ raise `LookupNotSeeded` พร้อมชื่อตารางที่ขาด ส่วน `python -m <package>.seed` seed ฐานข้อมูลที่ `WMS_DATABASE_URL`
- `tests/test_factory.py`: รัน `verify_factory` บน SQLite จะ fail จนกว่าทุก lookup มีค่า
- Alembic ตั้งค่าแบบ[หัวข้อ 7](#7-alembic) พร้อม migration `0001` ที่สร้าง schema `messaging`
- `requirements.txt`: มีแต่ package สาธารณะจาก PyPI คือ dependency ของ SDK สำหรับ feature ที่เลือก (เช่น `shapely` สำหรับ floor_map) และ Alembic
- `README.md` ที่มีขั้นตอนเหล่านี้ให้ทีมของโรงงาน ถ้าใส่ `--container` จะได้ `Containerfile` ด้วย (ดู[หัวข้อ 9](#9-container-image))

### อัปเกรดสำเนา SDK

`wms-sdk vendor` แทนที่ `wms_sdk/` ของโปรเจกต์ด้วย SDK เวอร์ชันที่ติดตั้งอยู่ โดยเก็บ feature เดิมของโปรเจกต์ไว้ ไฟล์นอก `wms_sdk/` ไม่ถูกแตะ ส่วนที่แก้ไว้ข้างใน `wms_sdk/` จะหายหมด จึงห้ามแก้ รันในโฟลเดอร์โปรเจกต์ (หรือระบุโฟลเดอร์):

```
wms_sdk/ in .: 0.1.2 -> 0.1.2 (46 files)
Features: tasks

requirements.txt must include:
  sqlalchemy>=2.0.43,<2.1
  pyodbc>=5.2

Then read the release notes and create a migration (README.md, section 3).
```

จากนั้น commit `wms_sdk/` ตัวใหม่พร้อม migration ([หัวข้อ 7](#7-alembic))

เพิ่ม feature ทีหลัง: `wms-sdk vendor --features routing` จะเพิ่มเข้าไปในสำเนา แล้วเปิดใน `models.py` และ seed lookup ของมัน ([หัวข้อ 3](#3-เลือก-feature))

## 1. ติดตั้ง

```bash
pip install "wms-sdk[mssql] @ git+https://github.com/Nextjingjing/wms-sdk.git@v0.1.2"
```

repo เป็น private ต้องมีสิทธิ์เข้าและ login git ไว้ วิธี login, การระบุเวอร์ชัน, การอัปเกรด และการติดตั้งจาก wheel อยู่ใน [การติดตั้ง](installation.md)

## 2. implement interface

ทุกโรงต้อง implement interface ของ core ทั้ง 4 ตัวด้านล่าง และ `TaskBase` ถ้าเปิด feature tasks ทุกโรงต้องมีคลาสละหนึ่งตัว สืบทอดจาก interface คู่กับ `Base` ไม่เพิ่มคอลัมน์ก็ได้ แต่ต้องมีคลาส

```python
from sqlalchemy import CheckConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column

from wms_sdk.core.db import Base
from wms_sdk.modules.inventory.models import PalletBase
from wms_sdk.modules.master_data.models import ProductPropertiesBase
from wms_sdk.modules.storage.models import LocationPropertiesBase, ZonePropertiesBase


class ProductProperties(ProductPropertiesBase, Base):
    pcs_per_box: Mapped[int | None] = mapped_column(Integer, nullable=True)

    extra_table_args = (
        CheckConstraint("pcs_per_box IS NULL OR pcs_per_box > 0", name="pcs_per_box_positive"),
    )


class ZoneProperties(ZonePropertiesBase, Base): ...
class LocationProperties(LocationPropertiesBase, Base): ...
class Pallet(PalletBase, Base): ...
```

| interface | key ที่ SDK กำหนด | SDK กำหนดคอลัมน์อื่นด้วยไหม |
|---|---|---|
| `ProductPropertiesBase` → `product_properties` | `sku` | ใช่ — `pcs_per_pallet`, `kg_per_pcs` (NOT NULL, > 0) เพราะทุกโรงมี |
| `ZonePropertiesBase` → `zone_properties` | `(plant_code, warehouse_code, zone_code)` | ไม่ |
| `LocationPropertiesBase` → `location_properties` | `location_code` | ไม่ |
| `PalletBase` → `pallets` | `code` | ใช่ — ของบนพาเลท, ตำแหน่ง, QC (ดู [inventory.md](inventory.md)) |
| `TaskBase` → `tasks` (เฉพาะ feature tasks) | `id` | `task_type_code`, `status_code` และค่าตั้ง `active_statuses`, `reservation_columns`, `transitions` (ดู [features.md](features.md#tasks--งานและการจอง)) |

กฎ:

- constraint ของโรงงานใส่ใน **`extra_table_args`** ถ้าเขียน `__table_args__` จะ raise `TypeError` (เพราะจะทับ FK ของ key)
- implement interface เดียวกันสองครั้ง → `TypeError`
- ไม่ implement → `verify_factory` raise `NotImplementedError`
- FK หลายคอลัมน์ที่ชื่อชนกับ FK ของ SDK ให้ตั้ง `name=` เอง (ดู `LocationProperties` ของตัวอย่างอ้างอิง)

ตัวอย่างการใช้ FK ย้อนกลับเพื่อบังคับ UNIQUE ข้ามตาราง: ตัวอย่างอ้างอิงเก็บ `plant_code`, `warehouse_code` ซ้ำใน `location_properties` แล้ว FK `(location_code, plant_code, warehouse_code)` ไป `locations` จึงบังคับ `UNIQUE (plant_code, warehouse_code, column_no, row_no)` ได้

## 3. เลือก feature

```python
import wms_sdk.features.machines             # noqa: F401
import wms_sdk.features.floor_map.models      # noqa: F401
import wms_sdk.features.routing.models        # noqa: F401
from wms_sdk.features.brand import HasBrand

class ProductProperties(ProductPropertiesBase, HasBrand, Base): ...
```

ไม่ import = ไม่มีตาราง รายละเอียดใน [features.md](features.md)

## 4. ตาราง lookup ของโรงงานเอง

```python
from sqlalchemy import String, Unicode
from sqlalchemy.orm import Mapped, mapped_column

from wms_sdk.core.db import Base, Lookup

class TicketFormat(Lookup, Base):
    __tablename__ = "ticket_formats"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False)
```

สืบทอด `Lookup` แล้ว `verify_factory` จะบังคับให้ seed

## 5. seed

ต้อง seed ทุกตาราง lookup ที่ถูก import: อย่างน้อย `roles` และของ feature ที่เปิด

```python
from wms_sdk.modules.events.capture import start_operation
from wms_sdk.shared.models.role import Role

def seed(session):
    start_operation(session, actor=None)       # ทุกการเขียนต้องอยู่ใน operation
    for code, name in {"Forklift": "Forklift", "Lab": "Lab"}.items():
        session.merge(Role(code=code, name=name))
    session.commit()
```

`session.merge` ทำให้รันซ้ำได้ ดูตัวอย่างเต็มที่ `examples/reference_factory/seed.py`

## 6. เริ่มระบบ

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import wms_sdk.metadata                    # ลงทะเบียนตาราง core
import my_factory.models                   # ลงทะเบียนตารางของโรงงาน
from wms_sdk.checks import verify_factory
from wms_sdk.modules.events.capture import install_capture

engine = create_engine(
    "mssql+pyodbc://user:password@host/wms?driver=ODBC+Driver+18+for+SQL+Server"
)
Session = sessionmaker(engine)
install_capture(Session)                   # บันทึกทุกการแก้ข้อมูลลง event_log

with Session() as session:
    verify_factory(session)                # raise ถ้า implement ไม่ครบหรือยังไม่ seed
```

ทุกการกระทำของผู้ใช้:

```python
with Session() as session:
    start_operation(session, actor="somchai")   # username หรือ None สำหรับงานของระบบ
    ...                                          # แก้ข้อมูล
    session.commit()
```

flush โดยไม่เรียก `start_operation` → `RuntimeError`

## 7. Alembic

migration อยู่ในโปรเจกต์ของโรงงาน ไม่ได้อยู่ใน SDK เพราะ schema สุดท้ายของแต่ละโรงต่างกัน

ตัวอย่างที่ใช้งานได้จริง ทดสอบบน SQL Server 2022 แล้ว อยู่ในตัวอย่างอ้างอิง: [`examples/reference_factory/alembic.ini`](../../examples/reference_factory/alembic.ini) และ [`migrations/env.py`](../../examples/reference_factory/migrations/env.py) ให้ copy ทั้งสองไฟล์ `env.py` ทำสิ่งเหล่านี้:

- import model ของโรงงาน (ซึ่ง import model ของ SDK และเปิด feature ให้) แล้วส่ง `wms_sdk.metadata.metadata` ให้ Alembic
- อ่าน URL ของ database จาก `WMS_DATABASE_URL` ไม่เก็บไว้ใน `alembic.ini`
- ตั้ง `include_schemas=True` ไม่อย่างนั้นไม่เห็นตารางใน schema `messaging`
- กรองความต่างปลอมที่ Alembic รายงานทุกครั้ง: FK `messaging.outbox → event_log` ถูกอ่านกลับมาเป็น `dbo.event_log` ถ้าไม่กรอง `alembic check` จะไม่ผ่านเลย

```bash
set WMS_DATABASE_URL=mssql+pyodbc://user:password@host,1433/wms?driver=ODBC+Driver+18+for+SQL+Server
alembic -c examples/reference_factory/alembic.ini revision --autogenerate -m "initial schema"
alembic -c examples/reference_factory/alembic.ini upgrade head
alembic -c examples/reference_factory/alembic.ini check        # model กับ database ตรงกัน
```

autogenerate สร้าง filtered index, CHECK ของ enum และตารางใน `messaging` ได้ถูกต้อง แต่ไม่สร้าง schema ให้ ต้องเพิ่มเองที่ต้น migration แรก และลบที่ท้าย downgrade:

```python
def upgrade():
    op.execute("CREATE SCHEMA messaging")
    ...

def downgrade():
    ...
    op.execute("DROP SCHEMA messaging")
```

ข้อควรระวัง:

- ตรวจ migration ที่ autogenerate ทุกครั้งก่อนรัน — การแก้คอลัมน์ที่มี index / default / FK บน SQL Server มักต้องแก้เอง
- **Alembic ไม่ตรวจการเปลี่ยนค่าของ enum** (เช่นเพิ่มสถานะใน `QcStatus`) ต้องเขียน migration แก้ CHECK เอง
- เพิ่มคอลัมน์ NOT NULL ในตารางที่มีข้อมูล: เพิ่มแบบ NULL ได้ → เติมค่า → เปลี่ยนเป็น NOT NULL (ห้ามใส่ default ปลอม)

## 8. test ของโรงงาน

```python
import pytest
from sqlalchemy.orm import sessionmaker

import my_factory.models  # noqa: F401
from wms_sdk.metadata import metadata
from wms_sdk.modules.events.capture import install_capture
from wms_sdk.testing.sqlite import create_sqlite_engine


@pytest.fixture
def session():
    engine = create_sqlite_engine()        # SQLite ในหน่วยความจำ
    metadata.create_all(engine)
    factory = sessionmaker(engine)
    install_capture(factory)
    with factory() as session:
        yield session
```

ดู `tests/conftest.py` ของ repo SDK เป็นตัวอย่าง

การลงทะเบียน interface เป็นระดับ process ถ้าต้องทดสอบหลายโรงงานใน test ชุดเดียว ให้รันแยก process (ดู `tests/test_factory.py`)

## 9. container image

มีเฉพาะเมื่อใช้ `wms-sdk init --container` (หรือติ๊ก `container` ในเมนู) `Containerfile` ที่เจนมาจะติดตั้ง Microsoft ODBC Driver 18 และ package ใน `requirements.txt`, copy สำเนา SDK, package ของโรงงาน และ migration เข้าไป แล้วรัน `alembic upgrade head` ไม่ต้องใช้ GitHub token เพราะ SDK อยู่ในโปรเจกต์แล้ว

```bash
podman build -t demo_plant .
podman run --rm --env-file .env demo_plant                          # alembic upgrade head
podman run --rm --env-file .env demo_plant python -m demo_plant.seed
```
