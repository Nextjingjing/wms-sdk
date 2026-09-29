# Tutorial: โรงงานแรกของคุณ

**ภาษาไทย** | [English](../en/tutorial.md)

หน้านี้พาอ่าน [`examples/minimal_factory/`](../../examples/minimal_factory) ซึ่งเป็นโปรเจกต์ของโรงงานที่เล็กที่สุดแต่ครบ รันบน SQLite ในหน่วยความจำ จึงต้องมีแค่ Python

```bash
python -m examples.minimal_factory.main
```

```
factory verified
stock: A-01 SKU-1 qty=40
events: roles.inserted, roles.inserted, plants.inserted, warehouses.inserted, zones.inserted, locations.inserted, products.inserted, pallet.putaway, pallets.inserted
```

## ขั้นที่ 1: implement interface

ทุกโรงงานต้อง implement interface ของ core ทั้ง 4 ตัว ตัวละครั้งเดียว ไม่เพิ่มคอลัมน์ก็ได้ [`models.py`](../../examples/minimal_factory/models.py):

```python
from wms_sdk.core.db import Base
from wms_sdk.modules.inventory.models import PalletBase
from wms_sdk.modules.master_data.models import ProductPropertiesBase
from wms_sdk.modules.storage.models import LocationPropertiesBase, ZonePropertiesBase


class ProductProperties(ProductPropertiesBase, Base):
    pass


class ZoneProperties(ZonePropertiesBase, Base):
    pass


class LocationProperties(LocationPropertiesBase, Base):
    pass


class Pallet(PalletBase, Base):
    pass
```

โรงงานจริงเพิ่มคอลัมน์ของตัวเองตรงนี้ เช่น ชั้น / ช่องของพาเลท หรือขนาดสินค้า ดูตัวอย่างอ้างอิงที่ [`examples/reference_factory/models.py`](../../examples/reference_factory/models.py)

## ขั้นที่ 2: seed ตาราง lookup

ตาราง lookup เก็บชุดค่าที่แต่ละโรงงานเลือกเอง ถ้าไม่เปิด feature ใดเลย ต้องมีแค่ `roles` [`seed.py`](../../examples/minimal_factory/seed.py):

```python
ROLES = {"Operator": "Operator", "Supervisor": "Supervisor"}


def seed(session: Session) -> None:
    start_operation(session, actor=None)
    for code, name in ROLES.items():
        session.merge(Role(code=code, name=name))
    session.commit()
```

การเขียนทุกครั้งต้องอยู่ใน operation (`start_operation`) เพราะทุกการเปลี่ยนแปลงถูกบันทึกลง `event_log` ส่วน `merge` ทำให้รัน seed ซ้ำได้

## ขั้นที่ 3: เริ่มระบบ

[`main.py`](../../examples/minimal_factory/main.py):

```python
engine = create_sqlite_engine()          # ใช้งานจริงใช้ SQL Server
Base.metadata.create_all(engine)         # ใช้งานจริงใช้ Alembic migration
Session = sessionmaker(engine)
install_capture(Session)                 # บันทึกทุกการแก้ข้อมูลลง event_log

with Session() as session:
    seed(session)
    verify_factory(session)              # implement interface ครบไหม seed lookup แล้วหรือยัง
```

`verify_factory` ล้มทันทีถ้า interface ไหนยังไม่ได้ implement หรือ lookup ไหนยังว่าง ก่อนที่ WMS จะเริ่มทำงาน

## ขั้นที่ 4: ข้อมูลหลัก

```python
start_operation(session, actor=None)
for row in [
    Plant(code="P1", name="Main plant"),
    Warehouse(plant_code="P1", code="WH1"),
    Zone(plant_code="P1", warehouse_code="WH1", code="A"),
    Location(code="A-01", plant_code="P1", warehouse_code="WH1", zone_code="A"),
    Product(sku="SKU-1", name_thai="สินค้าตัวอย่าง", name_eng="Sample product"),
]:
    session.add(row)
    session.flush()
session.commit()
```

key คือรหัสที่คนใช้เรียก (`P1`, `WH1`, `A-01`, `SKU-1`) ไม่ใช่เลข id model ไม่มี relationship ของ ORM จึงต้อง flush ทีละแถวตามลำดับ FK

## ขั้นที่ 5: พาเลทใบแรก

```python
start_operation(session, actor=None)
pallet = Pallet(code="PAL-1", sku="SKU-1", lot_no="LOT-1", qty=40, location_code="A-01")
set_qc_status(session, pallet, QcStatus.WAITING)      # พาเลทที่มีของต้องมีสถานะ QC เสมอ
session.add(pallet)
record_event(session, PalletEvent.PUTAWAY, {"pallet": pallet.code, "to": "A-01"})
session.commit()
```

- การเพิ่มแถวถูกบันทึกอัตโนมัติเป็น `pallets.inserted`
- `record_event` บอกว่าการกระทำนั้นคืออะไร: `pallet.putaway`

## ขั้นที่ 6: อ่านยอด stock

```python
select(Pallet.location_code, Pallet.sku, func.sum(Pallet.qty))
    .where(Pallet.location_code.is_not(None))
    .group_by(Pallet.location_code, Pallet.sku)
```

ไม่มีตาราง balance ยอดคงเหลือคือผลรวมของพาเลท

## ขั้นต่อไป

| ต้องการ | ทำ | อ่าน |
|---|---|---|
| ใช้ SQL Server | ติดตั้ง `wms-sdk[mssql]` สร้าง engine ด้วย URL `mssql+pyodbc://` แล้วเพิ่ม Alembic | [สร้างโปรเจกต์ของโรงงาน](factory-guide.md#6-เริ่มระบบ) |
| เพิ่มคอลัมน์ของตัวเอง | เพิ่มในคลาส interface; constraint ใส่ใน `extra_table_args` | [สร้างโปรเจกต์ของโรงงาน](factory-guide.md#2-implement-interface) |
| เปิด feature | `import wms_sdk.features.tasks.models` แล้ว implement `TaskBase` และ seed `task_types` / `task_statuses` | [feature เสริม](features.md#tasks--งานและการจอง) |
| ดูโปรเจกต์เต็ม | ตัวอย่างอ้างอิงเปิดทุก feature | [ตัวอย่าง](examples.md) |
