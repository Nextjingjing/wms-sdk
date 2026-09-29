# Tutorial: your first factory

[ภาษาไทย](../th/tutorial.md) | **English**

This walks through [`examples/minimal_factory/`](../../examples/minimal_factory), the smallest complete factory project. It runs on in-memory SQLite, so you need nothing but Python.

```bash
python -m examples.minimal_factory.main
```

```
factory verified
stock: A-01 SKU-1 qty=40
events: roles.inserted, roles.inserted, plants.inserted, warehouses.inserted, zones.inserted, locations.inserted, products.inserted, pallet.putaway, pallets.inserted
```

## Step 1: implement the interfaces

Every factory implements the four core interfaces exactly once. Adding no columns is fine. [`models.py`](../../examples/minimal_factory/models.py):

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

A real factory adds its own columns here, e.g. pallet level / slot or product size. See the reference factory example in [`examples/reference_factory/models.py`](../../examples/reference_factory/models.py).

## Step 2: seed the lookups

Lookup tables hold value sets each factory chooses. With no feature enabled, only `roles` is required. [`seed.py`](../../examples/minimal_factory/seed.py):

```python
ROLES = {"Operator": "Operator", "Supervisor": "Supervisor"}


def seed(session: Session) -> None:
    start_operation(session, actor=None)
    for code, name in ROLES.items():
        session.merge(Role(code=code, name=name))
    session.commit()
```

Every write happens inside an operation (`start_operation`), because every change is recorded in `event_log`. `merge` makes the seed safe to run again.

## Step 3: start up

[`main.py`](../../examples/minimal_factory/main.py):

```python
engine = create_sqlite_engine()          # SQL Server in production
Base.metadata.create_all(engine)         # Alembic migrations in production
Session = sessionmaker(engine)
install_capture(Session)                 # record every data change in event_log

with Session() as session:
    seed(session)
    verify_factory(session)              # interfaces implemented? lookups seeded?
```

`verify_factory` fails fast: if an interface is not implemented or a lookup is empty, it raises before the WMS runs.

## Step 4: master data

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

Keys are the codes people use (`P1`, `WH1`, `A-01`, `SKU-1`), not numeric ids. The models have no ORM relationships, so rows are flushed one by one in foreign-key order.

## Step 5: the first pallet

```python
start_operation(session, actor=None)
pallet = Pallet(code="PAL-1", sku="SKU-1", lot_no="LOT-1", qty=40, location_code="A-01")
set_qc_status(session, pallet, QcStatus.WAITING)      # a loaded pallet always has a QC status
session.add(pallet)
record_event(session, PalletEvent.PUTAWAY, {"pallet": pallet.code, "to": "A-01"})
session.commit()
```

- The row change is logged automatically as `pallets.inserted`
- `record_event` adds what the action was: `pallet.putaway`

## Step 6: read stock

```python
select(Pallet.location_code, Pallet.sku, func.sum(Pallet.qty))
    .where(Pallet.location_code.is_not(None))
    .group_by(Pallet.location_code, Pallet.sku)
```

There is no balance table: stock on hand is the sum over pallets.

## Next steps

| To | Do | Read |
|---|---|---|
| use SQL Server | install `wms-sdk[mssql]`, create the engine with a `mssql+pyodbc://` URL, add Alembic | [Building a factory project](factory-guide.md#6-start-up) |
| add your own columns | add them to your interface classes; constraints go in `extra_table_args` | [Building a factory project](factory-guide.md#2-implement-the-interfaces) |
| enable a feature | `import wms_sdk.features.tasks.models`, implement `TaskBase`, seed `task_types` / `task_statuses` | [Optional features](features.md#tasks-work-and-reservations) |
| see a full project | the reference factory example enables every feature | [Examples](examples.md) |
