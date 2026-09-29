# Troubleshooting

[ภาษาไทย](../th/troubleshooting.md) | **English**

Errors are shown with the message the SDK raises.

## Start-up

### `RuntimeError: no operation started; call start_operation(session, actor) first`

A session flushed a change without an operation. Every write, including seeds and scripts, must start one:

```python
start_operation(session, actor="somchai")   # or actor=None for system jobs
...
session.commit()
```

### `NotImplementedError: no factory implements <table>; subclass <XBase> together with Base`

An interface has no implementation, usually because the factory's models module was not imported before `verify_factory`. Import it at start-up (`import my_factory.models`), or add the missing class `class Pallet(PalletBase, Base): ...`. Feature interfaces (`TaskBase`) are required only when that feature is imported.

### `LookupNotSeeded: table 'roles' is empty; seed it first`

Every imported lookup table needs rows, including those of enabled features (`machine_groups`, `brands`, `task_types`, `task_statuses` ...). Run the factory's seed before `verify_factory`.

### `TypeError: <table> already implemented by <A>; <B> cannot implement it again`

Two classes implement the same interface in one process. Keep one per interface. In tests that need several factories, run each in its own process (see `tests/test_factory.py`).

### `TypeError: <Class>: put constraints in extra_table_args`

An interface implementation defined `__table_args__`, which would drop the interface's key constraints. Use `extra_table_args = (...)` instead.

### `TypeError: <Class>: reservation_columns needs active_statuses`

A `TaskBase` implementation set `reservation_columns` without saying which statuses are unfinished. Add `active_statuses = (...)`.

### `ImportError: routing needs networkx: pip install "wms-sdk[routing]"`

Also `floor_map geometry needs shapely: pip install "wms-sdk[floor_map]"`. The helper modules need an extra; the feature tables do not. Install the extra named in the message.

## Data rules

### `IntegrityError` on insert or update

The database refused a row. Common causes:

| Situation | Rule that refused it |
|---|---|
| pallet with a sku but no qty, or `qty = 0` | `ck_pallets_load_complete` |
| empty pallet placed in a location | `ck_pallets_stored_pallet_has_load` |
| two pallets in one position (reference factory) | `uq_pallets_position` |
| two active tasks for the same place | `uq_tasks_reservation` |
| locked pallet without a reason | `ck_pallets_qc_lock_reason_when_locked` |
| a code that does not exist in a lookup | the FK to that lookup |
| rows inserted in the wrong order | an FK: flush parents first (no ORM relationships) |

The constraint name in the error message says which rule; all rules are listed in the [Schema reference](schema.md).

### `InvalidQcTransition: pallet P-0001: waiting -> waiting is not allowed`

Only the changes in `QC_TRANSITIONS` are allowed: waiting → passed / locked, locked → passed, passed → locked. A new load starts with `WAITING`.

### `MissingLockReason: pallet P-0001: locking needs a reason`

`set_qc_status(session, pallet, QcStatus.LOCKED, reason="...")` needs a non-blank reason.

### `NotShippable: pallet P-0002 is locked, not passed`

`ensure_shippable` refuses pallets whose QC status is not `passed`. Call it before every shipment.

### `InvalidTaskStatus: task 1: open -> done is not allowed`

The change is not in the factory's `transitions`. A new task must start in a status allowed from `None`.

### `LocationInUse: locations still hold pallets: [...]`

Saving a shorter column or deleting a column would retire locations that still hold pallets. Move the pallets first. Nothing was changed.

### `ValueError: column 2 is in zone ['1']; delete it before adding it to zone 2`

reference factory example: moving a column to another zone changes its location codes. Call `delete_column` first, then save it in the new zone.

### `NotSet: product_properties has no row for 'A001'`

Also `warehouse C221/W1 has no published route map`. The row has not been set yet; that is a real state, not a default. Create the row (or publish a route map) first.

### A CHECK lets a NULL through

A CHECK passes when its result is UNKNOWN. When writing a CHECK over nullable columns, add `col IS NOT NULL` explicitly. See [Design concepts](concepts.md#8-let-the-database-enforce-rules).

## Map files (`.wmsmap`)

### `WarehouseExists: warehouse C221/W1 already exists`

Import only creates new warehouses; it never overwrites one. To replace a warehouse, import into a database that does not have it yet.

### `LocationCodeTaken: location codes already in use: [...]`

Location codes are unique across all warehouses, and another warehouse here already uses some of the file's codes. Nothing was written. Rename one side's locations, or import into another database.

### `PropertiesMismatch: location_properties: file has columns [...], this factory has [...]`

The file was exported by a factory whose `zone_properties` / `location_properties` have different columns. Import with `import_map(..., properties=False)` to bring everything except the properties, then fill them in yourself.

### `UnsupportedMapFile: ...`

- `manifest.json is missing`: the file is not a `.wmsmap` file
- `expected wmsmap version 1, got ...`: the file was written by an SDK with another file format; use the same SDK version on both sides
- `image path must be relative, inside image_root`: an image path in the file points outside `image_root` (`..` or an absolute path). The file was edited by hand or is not trustworthy; nothing was written
- `pictures missing from the file`: the ZIP was edited and lost an image

### `ValueError: the warehouse has pictures [...]: pass image_root`

On import: `the file has pictures [...]: pass image_root`. Export and import need `image_root`, the folder the stored image paths are relative to, whenever the warehouse has a floor image or background picture.

## Installation and tooling

### `pip install ... git+https://github.com/...` fails with "Repository not found" or asks for a password

The repository is private. Ask for access, then sign in: see [Installation](installation.md#signing-in-to-a-private-repository).

### `tests/test_docs.py` fails: `docs/en/schema.md is stale`

The schema changed. Run `python -m dev.gen_schema_doc` and commit the regenerated files.

### `tests/test_mock.py` or `tests/test_examples.py` fails after a schema change

Update `dev/mock.py` or the example in `examples/` to the new schema; they are documentation and must keep running.

### SQL Server behaves differently from the tests

Tests run on SQLite by default. Run them on SQL Server with `WMS_TEST_MSSQL_URL` (see [Getting started](getting-started.md#on-sql-server)); collation order and `DATETIME2` precision can differ. See [How SQLite differs](getting-started.md#how-sqlite-differs-from-sql-server).

### `alembic check` always reports `remove_fk` / `add_fk` for `fk_outbox_event_id_event_log`

The FK from `messaging.outbox` to `event_log` is reflected as pointing at `dbo.event_log`. Copy `drop_default_schema_fk_noise` from the reference factory's [`migrations/env.py`](../../examples/reference_factory/migrations/env.py) into your `env.py`.
