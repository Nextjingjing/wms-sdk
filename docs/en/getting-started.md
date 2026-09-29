# Getting started

[ภาษาไทย](../th/getting-started.md) | **English**

## Requirements

- Python 3.11 or later
- No SQL Server needed for development: tests and the sandbox database use SQLite

Commands on this page use the Windows path `.venv\Scripts\python`; on Linux / macOS use `.venv/bin/python`.

## Install

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` installs SQLAlchemy, pyodbc, pytest, and networkx / shapely for the optional features.

## Repository layout

```
wms_sdk/                 the SDK, the only part built into the package
  core/                  Base, Lookup, Interface, errors
  shared/models/         plants, roles, users
  modules/master_data/   products, product_properties, plant_products
  modules/storage/       warehouses, zones, locations (+ properties)
  modules/inventory/     pallets, QC, standard event names
  modules/events/        event_log, inbox, outbox, change capture
  features/              optional add-ons: machines, brand, floor_map, routing
  testing/sqlite.py      SQLite stand-in for SQL Server, for tests
  checks.py              verify_factory()
  metadata.py            import to register every core table
examples/minimal_factory/  the smallest factory (see the Tutorial)
examples/reference_factory/    example factory project (reference factory), every feature enabled
examples/cookbook/       runnable recipes on the reference factory example
dev/                     tools for this repo: create_db, mock, gen_schema_doc
tests/                   pytest
docs/                    this documentation (en / th)
```

## Run the tests

```bash
.venv\Scripts\python -m pytest                                    # everything
.venv\Scripts\python -m pytest tests/test_quality.py              # one file
.venv\Scripts\python -m pytest tests/test_routing.py -k publish   # tests whose name contains "publish"
```

Every test runs on in-memory SQLite and gets a fresh database (the `session` fixture in `tests/conftest.py`).

### On SQL Server

The same tests run on a real SQL Server when `WMS_TEST_MSSQL_URL` is set. Each test then gets a freshly created database named `wms_test_<name>` on that server; the helper refuses database names without "test". A local server runs in Docker:

```powershell
$env:MSSQL_SA_PASSWORD = '<pick your own password>'  # required, no default: nothing to commit
docker compose -f dev/mssql/compose.yml up -d        # SQL Server 2022 on 127.0.0.1:14333
$env:WMS_TEST_MSSQL_URL = "mssql+pyodbc://sa:$env:MSSQL_SA_PASSWORD@127.0.0.1,14333/x?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
.venv\Scripts\python -m pytest                       # about 5 minutes: each test recreates its database
```

`tests/test_alembic.py` runs only then: it migrates an empty database with the reference factory's migrations, checks that nothing differs from the models, and downgrades to empty.

| File | Checks |
|---|---|
| `test_constraints.py` | CHECK / UNIQUE rules on locations and pallets |
| `test_quality.py` | QC status changes and lock reasons |
| `test_events.py` | event_log capture, outbox, inbox |
| `test_factory.py` | unimplemented interfaces, features, verify_factory |
| `test_routing.py`, `test_floor_map.py` | optional features |
| `test_schema.py` | constraint names unique and short enough, no NTEXT, every FK indexed, filtered indexes filter on SQLite too |
| `test_map_file.py` | `.wmsmap` export / import |
| `test_alembic.py` | reference factory migrations match the models, on SQL Server only |
| `test_mock.py` | sample data still loads |
| `test_docs.py` | `docs/*/schema.md` matches the code; en / th have the same pages; links work |
| `test_examples.py` | every example in `examples/` still runs |

## Run the examples

```bash
.venv\Scripts\python -m examples.minimal_factory.main
.venv\Scripts\python -m examples.cookbook.pallet_lifecycle
.venv\Scripts\python -m examples.cookbook.map_and_routing
.venv\Scripts\python -m examples.cookbook.dispatch_tasks
.venv\Scripts\python -m examples.cookbook.share_map
```

What each one shows: [Examples](examples.md).

## Sandbox database

```bash
.venv\Scripts\python -m dev.create_db            # dev.sqlite: full schema + reference factory lookups
.venv\Scripts\python -m dev.create_db --mock     # + sample data
```

The file is recreated every time. `*.sqlite` files are not committed.

Sample data (`dev/mock.py`) is made up, uses codes starting with `MOCK-` / `mock.`, and is identical on every run:

- Plant TL (C221), warehouses W1 and W2, 3 zones each
- 60 locations, some closed (`is_enabled = 0`)
- 5 products, 3 machines, 3 users (1 Lab, 2 Forklift)
- 130 pallets: 120 loaded (waiting / locked / passed), 10 empty, some already shipped
- History in `event_log`, outbox rows (to `sap`) and 1 inbox message

Open `dev.sqlite` with DB Browser for SQLite, DBeaver or a VS Code extension and try the queries in [inventory.md](inventory.md#common-queries).

SQLite uses `json_extract` where SQL Server uses `JSON_VALUE`.

## SQL Server DDL

Print the `CREATE TABLE` of every table as SQL Server would create it (no database needed):

```bash
.venv\Scripts\python -c "from sqlalchemy.schema import CreateTable; from sqlalchemy.dialects import mssql; from wms_sdk.metadata import metadata; import examples.reference_factory.seed; [print(CreateTable(t).compile(dialect=mssql.dialect())) for t in metadata.sorted_tables]"
```

## After changing the schema

1. Run the tests
2. `python -m dev.gen_schema_doc` to refresh [schema.md](schema.md) in both languages (`test_docs.py` fails otherwise)
3. If the sample data no longer loads, update `dev/mock.py`

## How SQLite differs from SQL Server

`wms_sdk/testing/sqlite.py` translates the SQL Server specific parts (DATETIME2, `sysutcdatetime()`, `ISJSON`, the `messaging` schema). What SQLite still cannot prove:

- real `ISJSON`: in SQLite it is a stand-in function
- `DATETIME2` precision
- SQL Server collation order (matters for `road_start_code < road_end_code` in routing)

Filtered unique indexes are covered, because each one sets both `mssql_where` and `sqlite_where` (`tests/test_schema.py` checks).

The whole suite also passes on SQL Server 2022, including the reference factory's Alembic migrations; see [On SQL Server](#on-sql-server). Run it there after changing constraints or indexes.
