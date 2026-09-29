# Design concepts

[ภาษาไทย](../th/concepts.md) | **English**

This page explains **why** the schema looks the way it does. Follow these principles when adding or changing tables.

## 1. One SDK, many factories

The schema has three kinds of table, depending on whether every factory needs them.

| Kind | Examples | If the factory does nothing |
|---|---|---|
| **core** | `plants`, `products`, `locations`, `event_log` | the table always exists |
| **interface** | `product_properties`, `zone_properties`, `location_properties`, `pallets`; `tasks` once the tasks feature is imported | `verify_factory` raises: must be implemented |
| **feature** | `machines`, `brands`, `floor_map`, `routing`, `tasks` | no tables, no error |

- Needed by **every** WMS → core
- Every factory has it, but **with different columns** → interface: the SDK fixes the table name and key, the factory adds columns
- **Many** factories have it, not all → feature
- **One** factory has it → that factory's own table (e.g. the reference factory's `ticket_formats`)

Dependency direction: features may depend on core; core must never depend on a feature (the feature would then exist in every factory).

## 2. Natural keys, no meaningless ids

Every table's primary key is the value people actually use:

| Table | PK |
|---|---|
| `plants` | `code` (e.g. `C221`) |
| `products` | `sku` |
| `users` | `username` |
| `warehouses` | `(plant_code, code)` |
| `locations` | `code` (e.g. `tl-w3-1-0102`) |
| `pallets` | `code` (printed on the QR label) |

Queries read naturally, without joins:

```sql
SELECT * FROM machines WHERE plant_code = 'C221';          -- no join to plants
SELECT * FROM pallets WHERE location_code = 'tl-w3-1-0102'; -- no join to locations
```

An auto-increment `id` is used only where no natural key exists. There is exactly one: `event_log` (events have no name).

Multi-column foreign keys let the database enforce rules across tables. `product_source_machines` uses the same `plant_code` in its FK to `plant_products` and in its FK to `machines`, so the machine is guaranteed to be in the plant that makes the product.

## 3. Value sets: lookup table or enum

| Use | When | Examples |
|---|---|---|
| **Lookup table** (`code` is the PK) | each factory has a different set | `roles`, `machine_groups`, `brands` |
| **StrEnum + CHECK** | SDK code must know what a value means | `QcStatus` (`passed` = may ship), `RouteStatus` |

No numbers (`role_id = 5`): values in the database must be readable without opening the code.

Every lookup table subclasses `Lookup` (no columns of its own; it only marks the table as a lookup) and declares `code` and `name` itself. `verify_factory` finds every imported lookup table and checks that it has been seeded.

Allowed changes of an enum live in one table in the code, e.g. `QC_TRANSITIONS`, not scattered around.

## 4. No fake defaults

- No `0` or `''` just to make an insert pass: a value not known yet is absent
- NOT NULL = required; NULL = **genuinely does not apply**, never "unknown"
- Data that may be unknown when a row is created lives in a properties table: no row = not set, and `get_row()` raises `NotSet`
- Defaults that are real values are fine, e.g. `is_enabled = 1` (a new location is open) or `clearance_m = 3.00`

## 5. Columns written out in every class

No mixins that hide columns: opening a model file must show every column of its table, even though `created_at` / `updated_at` repeat across files. The exception is a feature mixin (`HasBrand`) whose purpose is to add a column to a factory's table.

Tables whose rows are never updated (link tables such as `plant_products`) have `created_at` only.

## 6. Soft delete

Tables that other tables reference (plants, users, products, locations, pallets …) use `deleted_at`:

- `NULL` = in use; a value = retired at that time
- Restore = set it back to NULL
- The natural key of a retired row stays taken (you cannot create the same `sku` again; restore it instead)

Link tables and route map drafts delete rows for real; the history is in `event_log`.

## 7. Nothing without a reason

Every table and column must be needed by the warehouse data itself, not by a screen:

- login, passwords, landing pages, display order → the application
- change history → `event_log`, no history table per table
- stock balance → computed from `pallets`, no balance table

## 8. Let the database enforce rules

If a rule can be a CHECK / FK / UNIQUE, the database enforces it, not only the application, because data may also arrive from scripts or other systems.

Beware: **a CHECK passes when its result is UNKNOWN**. `qty > 0` with `qty` NULL is UNKNOWN, so the row is accepted. In a CHECK over nullable columns, state `IS NOT NULL` explicitly:

```sql
-- wrong: a row with sku set and qty NULL passes
CHECK ((sku IS NULL AND qty IS NULL) OR (sku IS NOT NULL AND qty > 0))
-- right
CHECK ((sku IS NULL AND qty IS NULL) OR (sku IS NOT NULL AND qty IS NOT NULL AND qty > 0))
```

Rules the database cannot enforce (across tables, or tied to an action) have SDK functions, e.g. `ensure_shippable()`, and the application must always call them.

## 9. SQL Server conventions

- Thai text: `NVARCHAR` (`Unicode`); codes: `VARCHAR` (`String`)
- Unbounded text: `Unicode()` → `NVARCHAR(max)`, never `UnicodeText` (→ `NTEXT`, which `ISJSON` rejects)
- Time: `DATETIME2`, UTC from `sysutcdatetime()`
- Constraint names come from the naming convention in `core/db.py` (SQL Server invents random names otherwise, which Alembic then cannot alter), except DEFAULT constraints, which are dropped with `op.alter_column(..., mssql_drop_default=True)`
- Filtered unique indexes set both `mssql_where` and `sqlite_where`
- SQL Server does not index foreign key columns: every FK leads an index or key, except FKs to lookup tables (rows almost never deleted; an index would only slow writes) and a few tiny tables. `tests/test_schema.py` enforces it, and lists the exceptions with their reasons
- Warehouse data lives in schema `dbo`; `inbox` / `outbox` live in schema `messaging`
