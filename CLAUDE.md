# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

An SDK for designing WMS (Warehouse Management System) databases, reused across factories. Database layer only — no API/web layer. The user communicates in Thai; code comments are in English.

## Stack

- **Database:** Microsoft SQL Server
- **ORM:** SQLAlchemy 2.0 (typed `Mapped[...]` / `mapped_column`), sync only
- **Migrations:** Alembic, in each factory project, not in the SDK. Working reference: `examples/reference_factory/alembic.ini` + `migrations/` (URL from `WMS_DATABASE_URL`)
- **Driver:** `pyodbc` + Microsoft ODBC Driver 18 for SQL Server

## Layout

```
wms_sdk/                       # shared core, no factory-specific values
  core/db.py                   # Base (naming_convention), Lookup marker
  core/errors.py               # NotSet, LookupNotSeeded
  core/interface.py            # Interface base for per-factory tables; get_row() raises NotSet
  modules/<module>/models/     # tables owned by one module, one file per entity; __init__ re-exports
  modules/events/              # event_log (audit + business events), messaging inbox/outbox, capture.py (before_flush auto-audit), receive.py (deduped inbox writes)
  shared/models/               # tables used by several modules (plants, roles, users)
  features/                    # optional features (brand, machines, floor_map, routing, tasks, map_file): absent unless the factory imports them
  metadata.py                  # imports every core SDK model (not features); use its `metadata` for Alembic/DDL
  testing/sqlite.py            # SQLite stand-in for MSSQL (shims + engine) for tests, ours and factories'
  checks.py                    # verify_factory(): startup check — interfaces implemented, every imported lookup seeded
  cli.py, __main__.py          # `wms-sdk` / `python -m wms_sdk` command line
  prompt.py                    # arrow-key checkbox menu for the CLI (stdlib: msvcrt / termios)
  scaffold/                    # `wms-sdk init` / `vendor`: new factory project with a copy of the SDK (template/ files + models.py/seed.py built per feature)
dev/mock.py                    # made-up sample data (MOCK-* codes) written through the SDK; tests/test_mock.py keeps it loadable
dev/gen_schema_doc.py          # generates docs/{en,th}/schema.md from the models; tests/test_docs.py fails if stale
dev/mssql/compose.yml          # local SQL Server 2022 (127.0.0.1:14333) for running the tests on the real target
docs/en/, docs/th/             # user documentation, English and Thai, same content; schema.md generated, the rest hand-written
examples/reference_factory/          # reference factory implementation
  models.py                    # implements SDK interfaces, enables features, adds factory-only lookups
  seed.py                      # lookup rows for this factory
  roles.py                     # RoleCode enum: the reference factory's roles, seeded into `roles`
```

## Documentation

`README.md` (English) and `README.th.md` (Thai) link to `docs/en/` and `docs/th/`. The two languages must cover the same content: when you change a page in one, change its counterpart. Never edit `schema.md` by hand. Code in docs should come from `examples/` (runnable, run by `tests/test_examples.py`); outputs shown in docs must be copied from a real run, never written by hand. New recipes go in `examples/cookbook/<name>.py` with a `main()` and an entry in `tests/test_examples.py`.

## Packaging

`pyproject.toml` ships only `wms_sdk/` as the installable package `wms-sdk` (version in `wms_sdk/__init__.py`); `examples/`, `dev/` and `tests/` stay in the repo. So `wms_sdk` must never import from `examples` or `dev`. Factories install the package and write their own project shaped like `examples/reference_factory/` (interfaces, features, seed, Alembic). Optional extras: `[mssql]` (pyodbc), `[routing]` (networkx, for `routing/graph.py`), `[floor_map]` (shapely, for `floor_map/geometry.py`). Modules needing an extra import it at the top and raise an ImportError naming the extra; feature models must never import them, so migrations run without extras. Prefer a well-known library over hand-written algorithms (graphs, geometry); convert Decimal columns to float only at that boundary. Build with `python -m build --wheel`.

`wms-sdk init` generates a factory project once (the factory owns its files afterwards; no regeneration) with a copy of `wms_sdk/` (chosen features only, without `scaffold/`, `cli.py`, `prompt.py`, `__main__.py`), so factories need no access to the private repo; `wms-sdk vendor` replaces that copy. So every module the copy keeps must work without the generator, and `DEPENDENCIES` must match `pyproject.toml` (tested). The project mirrors `examples/reference_factory/` (keep `migrations/env.py` in both in step) and the generator uses only the stdlib. When an interface, a feature or a lookup is added, update `FEATURES` / the builders in `wms_sdk/scaffold/__init__.py`. `tests/test_scaffold.py` generates projects, fills their TODOs and runs their tests on their own copy (and their Alembic migrations on SQL Server).

## Design rules

- **Columns are written out in every class.** No column mixins (`created_at`/`updated_at` repeated on purpose), so each model file shows its full table. Tables whose rows are never updated (link tables) have `created_at` only.
- **Only what is justified.** Every table/column must be needed by the warehouse data itself. App concerns (login, passwords, landing pages, display order) stay out of the schema. `users` records who did what; each user has exactly one `role_code` (FK → `roles`, a per-factory lookup; the reference factory's seed fills it from the `RoleCode` enum in `examples/reference_factory/roles.py`).
- **Natural keys as PK.** No surrogate `id` when a stable business key exists (`users.username`, `plants.code`, `products.sku`, `machines(plant_code, code)`). FK columns carry the readable key.
- **SDK-owned workflow values are StrEnum + CHECK, not lookups.** When SDK code must know what a value means (e.g. `QcStatus.PASSED` = shippable, `PalletEvent`), the set is fixed in the SDK; allowed changes live in one transition table (`QC_TRANSITIONS`).
- **Per-factory value sets are lookup tables, not enums.** Lookup tables (subclass the `Lookup` marker; e.g. `machine_groups`, `brands`) declare `code` (string PK) and `name` themselves; other tables FK to it via `<name>_code`. Same schema for every factory; factories differ only in seeded rows. `verify_factory` checks every `Lookup` table that was imported, so enabling a feature makes its lookups required automatically.
- **Interfaces for per-factory tables.** Declared as `class XPropertiesBase(Interface, root=True)` (`product_properties`, `zone_properties`, `location_properties`, `pallets`); they fix the table name, key columns and key constraints (`base_table_args`), plus columns every factory has (e.g. `product_properties.pcs_per_pallet` / `kg_per_pcs`, confirmed with all factories). Each factory subclasses once with `Base` and adds columns; its own constraints go in `extra_table_args` — defining `__table_args__` raises `TypeError` because it would drop the key FK. No implementation → `implementation()` / `verify_factory` raise `NotImplementedError`; a second implementation raises `TypeError`. Read rows with `get_row()`, which raises `NotSet` when missing.
- **Fail fast, no fake defaults.** Properties unknown at creation live outside `products`, in `product_properties` keyed by `sku`. A missing row means "not set" and is read through a getter that raises `NotSet`. NOT NULL = required; nullable = genuinely optional, never "unknown". Adding a NOT NULL column to a table with data: add nullable → backfill → alter to NOT NULL.
- **Stock = `pallets`.** One row per physical, reusable pallet; its current load is `sku` + `lot_no` + `qty` (all NULL = empty pallet, 1 sku and 1 lot per load). Empty pallets are never in a location; broken/lost pallets get `deleted_at`. Location state (empty / loaded / stored / out / retired) is derived from columns, never a status column. QC is core and per pallet (the lab passes or locks each pallet; every warehouse needs "may this pallet ship?"): `pallets.qc_status` (waiting / locked / passed; NULL only when empty), changed only via `set_qc_status` in `modules/inventory/qc.py` (WAITING on load). LOCKED requires a reason, kept in `pallets.qc_lock_reason` while locked (DB CHECK) and in the `pallet.qc_locked` event. Ship only after `ensure_shippable(pallet)`. There is no `lots` table: a lot has no data of its own yet. On-hand is `SUM(qty)` over pallets, no balance table. `left_at` is set while the pallet is outside the warehouse and cleared when it returns. There is no `stock_movements` table: every change in position or load must `record_event(session, PalletEvent.X, ...)` (standard names in `modules/inventory/events.py`) in the same transaction, and `event_log` is the movement history — so never purge `event_log` rows still needed for traceability.
- **Soft delete via `deleted_at`** (`DATETIME2 NULL`; NULL = live), not `is_active`. Rows are soft-deleted because other tables FK to them; restoring = set back to NULL.
- **One event log.** Every data change is captured into `event_log` automatically by `capture.py` (install once with `install_capture`); business events (e.g. `putaway.completed`) are added with `record_event`, which also queues `outbox` rows for external systems. Incoming messages go through `receive_message` into `inbox`, deduplicated by the sender's `(source, message_id)`. Messaging tables are never captured into `event_log`. Each user action must call `start_operation(session, actor)` first — flushing without it raises. `event_log` is history, never a source of truth: stock quantities belong in typed tables.
- **Three kinds of SDK table.** Core (always present), interface (`*Base`, must be implemented or it raises), optional feature (`wms_sdk/features/`, exists only if imported; column add-ons are mixins like `HasBrand`). A concept most but not all warehouses have is a feature; one factory's concept (e.g. a factory's own ticket formats) stays in that factory's package. Dependency direction: features may import/FK core; core must never import or FK a feature (that would make it always present).
- **floor_map / routing features.** `floor_map` stores drawing positions only (site images, warehouse outlines, location boxes; geometry helpers in `geometry.py`), plus an optional map builder: `builder.py` (pure column layout, ported from a factory's original map editor) and `repository.save_column` / `retire_locations`, which refuse to retire a location that still holds a pallet. `routing` stores the forklift road network as revisions (one draft + one published per warehouse, `repository.publish` archives the old one); `graph.py` is pure (Dijkstra, lane-mouth layout) and `repository.load_graph` feeds it the published revision. Roads are identified by their two vertex codes (start = smaller code); keep vertex codes in one letter case.
- **tasks feature.** One `tasks` table for all work (forklift, QC, dispatch). `TaskBase` fixes only `id`, `task_type_code`, `status_code` (both lookups); factories add every other column and set `active_statuses`, `reservation_columns` (SDK builds a filtered unique index over active tasks) and `transitions` (checked by `set_task_status`). No task history table: `event_log`.
- **map_file feature.** `.wmsmap` = ZIP of `manifest.json` (with `FORMAT_VERSION`), `map.json` (rows per table, generic column copy minus `created_at`/`updated_at`, Decimals as strings) and `images/<stored path>`. Structure only (no pallets/tasks/history), published route map only. Import refuses an existing warehouse or taken location codes, checks properties columns, and never writes images outside `image_root`. A new table in floor_map/routing/storage must be added to both `export_map` and the ordered steps in `import_map`; bump `FORMAT_VERSION` when the file content changes incompatibly.
- **Core vs factory.** Only what every WMS needs goes in `wms_sdk`; factory-specific columns go in the factory's interface implementation or its own tables.

## MSSQL + Alembic conventions

- `Base.metadata` defines a `naming_convention` (pk, fk, uq, ix, ck). It does **not** cover DEFAULT constraints — drop those with `op.alter_column(..., mssql_drop_default=True)`.
- **Filtered (partial) indexes:** give both `mssql_where=` and `sqlite_where=` with the same condition, so the SQLite tests exercise them.
- **Schemas:** warehouse data lives in the default schema (`dbo`); app-layer plumbing (`outbox`, `inbox`) lives in `messaging` via `__table_args__ = {"schema": "messaging"}`. Alembic does not create schemas — the first migration needs `op.execute("CREATE SCHEMA messaging")` — and `env.py` needs `include_schemas=True` or autogenerate won't see them. In `metadata.tables` the key is `"messaging.outbox"`.
- **Index every FK.** SQL Server does not index FK columns. Each FK must lead an unfiltered index or key (or contain a unique key); `tests/test_schema.py` fails otherwise. Exempt: FKs to `Lookup` tables, and the few listed with a reason in `UNINDEXED_FKS`. Add indexes for common report queries too (e.g. `event_log (event_type, occurred_at)`).
- **CHECK passes on UNKNOWN.** `qty > 0` with `qty` NULL is UNKNOWN, so the row is accepted. In any CHECK over nullable columns, state `col IS NOT NULL` explicitly.
- **Autogenerate on MSSQL:** handles filtered indexes, enum CHECKs and `messaging` tables, but not the schema: add `op.execute("CREATE SCHEMA messaging")` / `DROP SCHEMA` by hand. `env.py` must keep `drop_default_schema_fk_noise` (the cross-schema FK outbox → event_log reflects as `dbo.event_log`, so `alembic check` would never pass). Enum value changes are not detected: edit the CHECK by hand.
- Always review autogenerated migrations before applying — altering a column that has an index, default, or FK usually needs manual edits on MSSQL.
- `NVARCHAR` (`Unicode`) for text that may contain Thai; `VARCHAR` (`String`) for codes. For unbounded text use `Unicode()` (→ `NVARCHAR(max)`), never `UnicodeText` (→ deprecated `NTEXT`, which `ISJSON` rejects).
- `mssql.DATETIME2` for timestamps, not generic `DateTime`.

## Commands

```
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # Windows path; bin/ on Linux/macOS
.venv/Scripts/python -m pytest                                # all tests (in-memory SQLite)
.venv/Scripts/python -m pytest tests/test_events.py -k outbox # one test
.venv/Scripts/python -m dev.create_db                         # rebuild dev.sqlite: full schema + reference factory seed
.venv/Scripts/python -m dev.create_db --mock                  # ...plus sample plants/locations/pallets/events
.venv/Scripts/python -m dev.gen_schema_doc                    # regenerate docs/{en,th}/schema.md after any schema change
.venv/Scripts/python -m dev.demo_map [--site X --background Y] # .wmsmap trial with real pictures → demo_map/ (git-ignored)
MSSQL_SA_PASSWORD=<pick-your-own-password> docker compose -f dev/mssql/compose.yml up -d  # SQL Server for the next line
WMS_TEST_MSSQL_URL="mssql+pyodbc://sa:<same-password>@127.0.0.1,14333/x?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes" .venv/Scripts/python -m pytest   # all tests on SQL Server (~5 min), incl. tests/test_alembic.py
```

`*.sqlite` / `*.db` files are git-ignored. Tests and `dev.sqlite` run on SQLite with MSSQL-only SQL translated in `wms_sdk/testing/sqlite.py`; real `ISJSON`, DATETIME2 and collation are not proven there, so after changing constraints, indexes or migrations run the suite on SQL Server too (`WMS_TEST_MSSQL_URL`; `wms_sdk.testing.create_test_engine` gives each test a fresh `wms_test_<name>` database). The whole suite passes on SQL Server 2022. Tests that need a fresh interface registry run in a subprocess (`tests/test_factory.py`).

Render the full schema as MSSQL DDL (no database needed):

```
python -c "from sqlalchemy.schema import CreateTable; from sqlalchemy.dialects import mssql; from wms_sdk.metadata import metadata; import examples.reference_factory.seed; [print(CreateTable(t).compile(dialect=mssql.dialect())) for t in metadata.sorted_tables]"
```
