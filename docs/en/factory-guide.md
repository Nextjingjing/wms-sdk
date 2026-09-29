# Building a factory project

[ภาษาไทย](../th/factory-guide.md) | **English**

Each factory has its own project and installs the SDK as a package. New to the SDK? Do the [Tutorial](tutorial.md) first: it builds the smallest factory, [`examples/minimal_factory/`](../../examples/minimal_factory). The most complete example is [`examples/reference_factory/`](../../examples/reference_factory).

```
my_factory/
  models.py      interface implementations, enabled features, factory lookups
  seed.py        lookup rows
  roles.py       role enum (optional)
  alembic/       the factory's migrations
tests/
```

## Quick start: generate the project

`wms-sdk init` writes the whole project: the sections below already done, with `TODO(wms)` where the factory must decide. The project also gets **a copy of the SDK** in `wms_sdk/` (only the chosen features), so the factory's team, its CI and its images install nothing from the private repository and need no GitHub access. Only whoever runs `wms-sdk` needs the SDK installed:

```bash
pip install "wms-sdk[mssql] @ git+https://github.com/Nextjingjing/wms-sdk.git@v0.1.2"
wms-sdk init                                    # or: python -m wms_sdk init
```

It asks for the package name, then shows a menu: up / down move, space ticks, Enter confirms.

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

Or give everything on the command line (no questions, for scripts):

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

| Option | |
|---|---|
| `--features a,b` | brand, machines, floor_map, routing, tasks, map_file (map_file adds floor_map and routing). Left out: the menu in a terminal, none otherwise |
| `--container` | add `Containerfile`, `.containerignore`, `.env.example` (default: none) |
| `--dir PATH` | where to write (default `./<package>`) |
| `--dry-run` | list the files, write nothing |
| `--force` | overwrite the generated files in a non-empty folder; other files are kept |

What you get:

- `wms_sdk/`: the SDK itself, imported as usual (`import wms_sdk...`) when Python runs from the project folder. Never edit it (see below)
- `models.py`: one class per interface (plus `Task` with tasks), features enabled
- `seed.py`: one empty dict per lookup; `seed()` raises `LookupNotSeeded` naming the empty ones, and `python -m <package>.seed` seeds the database at `WMS_DATABASE_URL`
- `tests/test_factory.py`: `verify_factory` on SQLite; fails until every lookup has rows
- Alembic set up as in [section 7](#7-alembic), with migration `0001` creating schema `messaging`
- `requirements.txt`: only public packages from PyPI, the SDK's dependencies for the chosen features (e.g. `shapely` for floor_map) plus Alembic
- `README.md` with these steps for the factory's team; with `--container` also a `Containerfile` (see [section 9](#9-container-image))

### Upgrading the SDK copy

`wms-sdk vendor` replaces the project's `wms_sdk/` with the installed SDK version, keeping the project's features. Files outside `wms_sdk/` are not touched, and edits inside it are lost, which is why it must never be edited. Run it in the project folder (or give the folder):

```
wms_sdk/ in .: 0.1.2 -> 0.1.2 (46 files)
Features: tasks

requirements.txt must include:
  sqlalchemy>=2.0.43,<2.1
  pyodbc>=5.2

Then read the release notes and create a migration (README.md, section 3).
```

Then commit the new `wms_sdk/` with a migration ([section 7](#7-alembic)).

To add a feature later: `wms-sdk vendor --features routing` adds it to the copy; then enable it in `models.py` and seed its lookups ([section 3](#3-choose-features)).

## 1. Install

```bash
pip install "wms-sdk[mssql] @ git+https://github.com/Nextjingjing/wms-sdk.git@v0.1.2"
```

The repository is private: you need access and a signed-in git. Sign-in options, pinning, upgrades and installing from a wheel are in [Installation](installation.md).

## 2. Implement the interfaces

Every factory implements the four core interfaces below, plus `TaskBase` if it enables the tasks feature. It has exactly one class per interface, subclassing the interface together with `Base`. Adding no columns is fine, but the class must exist.

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

| Interface | Key fixed by the SDK | Other SDK columns |
|---|---|---|
| `ProductPropertiesBase` → `product_properties` | `sku` | `pcs_per_pallet`, `kg_per_pcs` (NOT NULL, > 0): every factory has them |
| `ZonePropertiesBase` → `zone_properties` | `(plant_code, warehouse_code, zone_code)` | none |
| `LocationPropertiesBase` → `location_properties` | `location_code` | none |
| `PalletBase` → `pallets` | `code` | yes: load, position, QC (see [inventory.md](inventory.md)) |
| `TaskBase` → `tasks` (tasks feature only) | `id` | `task_type_code`, `status_code`; plus `active_statuses`, `reservation_columns`, `transitions` (see [features.md](features.md#tasks-work-and-reservations)) |

Rules:

- Factory constraints go in **`extra_table_args`**. Defining `__table_args__` raises `TypeError`, because it would drop the key's FK
- Implementing the same interface twice → `TypeError`
- Not implementing one → `verify_factory` raises `NotImplementedError`
- A multi-column FK whose generated name would clash with an SDK FK needs an explicit `name=` (see the reference factory's `LocationProperties`)

Example of a back-reference FK used to enforce uniqueness across tables: the reference factory copies `plant_code` and `warehouse_code` into `location_properties` and FKs `(location_code, plant_code, warehouse_code)` to `locations`, which makes `UNIQUE (plant_code, warehouse_code, column_no, row_no)` possible.

## 3. Choose features

```python
import wms_sdk.features.machines             # noqa: F401
import wms_sdk.features.floor_map.models      # noqa: F401
import wms_sdk.features.routing.models        # noqa: F401
from wms_sdk.features.brand import HasBrand

class ProductProperties(ProductPropertiesBase, HasBrand, Base): ...
```

Not imported = no tables. Details in [features.md](features.md).

## 4. Factory-only lookup tables

```python
from sqlalchemy import String, Unicode
from sqlalchemy.orm import Mapped, mapped_column

from wms_sdk.core.db import Base, Lookup

class TicketFormat(Lookup, Base):
    __tablename__ = "ticket_formats"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False)
```

Subclassing `Lookup` makes `verify_factory` require it to be seeded.

## 5. Seed

Every imported lookup table must be seeded: at least `roles`, plus those of enabled features.

```python
from wms_sdk.modules.events.capture import start_operation
from wms_sdk.shared.models.role import Role

def seed(session):
    start_operation(session, actor=None)       # every write happens in an operation
    for code, name in {"Forklift": "Forklift", "Lab": "Lab"}.items():
        session.merge(Role(code=code, name=name))
    session.commit()
```

`session.merge` makes it safe to re-run. Full example: `examples/reference_factory/seed.py`.

## 6. Start-up

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import wms_sdk.metadata                    # register core tables
import my_factory.models                   # register the factory's tables
from wms_sdk.checks import verify_factory
from wms_sdk.modules.events.capture import install_capture

engine = create_engine(
    "mssql+pyodbc://user:password@host/wms?driver=ODBC+Driver+18+for+SQL+Server"
)
Session = sessionmaker(engine)
install_capture(Session)                   # record every data change in event_log

with Session() as session:
    verify_factory(session)                # raises if an interface is missing or a lookup is empty
```

Every user action:

```python
with Session() as session:
    start_operation(session, actor="somchai")   # username, or None for system jobs
    ...                                          # change data
    session.commit()
```

Flushing without `start_operation` → `RuntimeError`.

## 7. Alembic

Migrations live in the factory project, not in the SDK, because each factory's final schema differs.

A working setup, tested on SQL Server 2022, is in the reference factory example: [`examples/reference_factory/alembic.ini`](../../examples/reference_factory/alembic.ini) and [`migrations/env.py`](../../examples/reference_factory/migrations/env.py). Copy both. `env.py`:

- imports your models (which import the SDK's and enable your features), then hands `wms_sdk.metadata.metadata` to Alembic
- reads the database URL from `WMS_DATABASE_URL`, never from `alembic.ini`
- sets `include_schemas=True`, otherwise tables in schema `messaging` are invisible
- filters out a false difference Alembic reports on every run: the FK `messaging.outbox → event_log` is reflected as pointing at `dbo.event_log`. Without the filter, `alembic check` never passes

```bash
set WMS_DATABASE_URL=mssql+pyodbc://user:password@host,1433/wms?driver=ODBC+Driver+18+for+SQL+Server
alembic -c examples/reference_factory/alembic.ini revision --autogenerate -m "initial schema"
alembic -c examples/reference_factory/alembic.ini upgrade head
alembic -c examples/reference_factory/alembic.ini check        # models and database match
```

Autogenerate gets the filtered indexes, enum CHECKs and the `messaging` tables right, but not the schema itself. Add it by hand at the start of the first migration, and drop it at the end of its downgrade:

```python
def upgrade():
    op.execute("CREATE SCHEMA messaging")
    ...

def downgrade():
    ...
    op.execute("DROP SCHEMA messaging")
```

Watch out for:

- Review every autogenerated migration before running it: altering a column that has an index / default / FK on SQL Server often needs manual edits
- **Alembic does not detect enum value changes** (e.g. a new `QcStatus`); edit the CHECK in a hand-written migration
- Adding a NOT NULL column to a table with data: add it nullable → fill it → make it NOT NULL (no fake default)

## 8. Factory tests

```python
import pytest
from sqlalchemy.orm import sessionmaker

import my_factory.models  # noqa: F401
from wms_sdk.metadata import metadata
from wms_sdk.modules.events.capture import install_capture
from wms_sdk.testing.sqlite import create_sqlite_engine


@pytest.fixture
def session():
    engine = create_sqlite_engine()        # in-memory SQLite with SQL Server specifics translated
    metadata.create_all(engine)
    factory = sessionmaker(engine)
    install_capture(factory)
    with factory() as session:
        yield session
```

See the SDK repo's `tests/conftest.py` for a working example.

Interface registration is per process. To test several factories in one test run, run them in separate processes (see `tests/test_factory.py`).

## 9. Container image

Only with `wms-sdk init --container` (or `container` ticked in the menu). The generated `Containerfile` installs Microsoft ODBC Driver 18 and the packages in `requirements.txt`, copies the SDK copy, the factory package and the migrations, and runs `alembic upgrade head`. No GitHub token is needed: the SDK is already in the project.

```bash
podman build -t demo_plant .
podman run --rm --env-file .env demo_plant                          # alembic upgrade head
podman run --rm --env-file .env demo_plant python -m demo_plant.seed
```
