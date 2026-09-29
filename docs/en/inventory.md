# Stock, pallets and QC

[ภาษาไทย](../th/inventory.md) | **English**

## Ideas

- Stock is tracked **per pallet**: one row in `pallets` per physical pallet, for its whole life
- Pallets are **reusable**: the goods on them (1 sku, 1 lot) come and go, the pallet code stays
- **On-hand** = `SUM(qty)` over pallets; there is no balance table
- **Movement history** lives in `event_log`; there is no movements table (see [events.md](events.md))

## `pallets` columns

| Column | Meaning |
|---|---|
| `code` | QR / LPN code, stays with the pallet |
| `sku`, `lot_no`, `qty` | current load; all three NULL = empty pallet |
| `qc_status` | `waiting` / `locked` / `passed`; NULL when empty |
| `qc_lock_reason` | why it is locked; set only while `locked` |
| `location_code` | storage location; NULL = not in a location |
| `left_at` | set while the pallet is outside the warehouse, cleared when it returns |
| `deleted_at` | retired (broken / lost) |

Factories may add columns. The reference factory adds `level_no` and `slot_no` (height and side-by-side position inside a location) with a unique index so each position holds one pallet.

## Pallet state

There is no status column. State is derived from the real columns, so it cannot contradict them.

| State | Condition |
|---|---|
| empty | no `sku`, no `location_code`, no `left_at` |
| loaded, awaiting putaway | `sku`, no `location_code`, no `left_at` |
| stored | `sku` and `location_code` |
| outside | `left_at` |
| retired | `deleted_at` |

```sql
SELECT code,
  CASE
    WHEN deleted_at    IS NOT NULL THEN 'retired'
    WHEN left_at       IS NOT NULL THEN 'out'
    WHEN location_code IS NOT NULL THEN 'stored'
    WHEN sku           IS NOT NULL THEN 'loaded'
    ELSE 'empty'
  END AS status
FROM pallets;
```

Rules the database enforces:

- `sku`, `lot_no`, `qty` are all set (`qty > 0`) or all NULL: there is never a pallet with `qty = 0`
- A pallet in a location has a load (empty pallets are not stored in locations)
- `left_at` set → no `location_code`
- `deleted_at` set → empty and no location
- loaded ↔ `qc_status` set; `locked` ↔ `qc_lock_reason` set

## Pallet life cycle

A runnable version of this life cycle, with tasks and a QC lock, is [`examples/cookbook/pallet_lifecycle.py`](../../examples/cookbook/pallet_lifecycle.py) (walked through in [Examples](examples.md#pallet-life-cycle)).

Every step changes `pallets` **and** records an event in the same transaction. The change to `pallets` is captured automatically as `pallets.updated`; `record_event` says what the action was.

```python
from datetime import UTC, datetime

from wms_sdk.modules.events.capture import record_event, start_operation
from wms_sdk.modules.inventory.events import PalletEvent
from wms_sdk.modules.inventory.qc import QcStatus, ensure_shippable, set_qc_status

# load
start_operation(session, actor="forklift1")
pallet.sku, pallet.lot_no, pallet.qty = "A001", "L1", 40
set_qc_status(session, pallet, QcStatus.WAITING)
record_event(session, PalletEvent.LOADED, {"pallet": pallet.code, "sku": "A001", "lot_no": "L1"})
session.commit()

# put away
start_operation(session, actor="forklift1")
pallet.location_code = "tl-w3-1-0102"
record_event(session, PalletEvent.PUTAWAY, {"pallet": pallet.code, "to": "tl-w3-1-0102"})
session.commit()

# partial pick
pallet.qty -= 10
record_event(session, PalletEvent.PICKED, {"pallet": pallet.code, "qty": 10})

# ship: QC must have passed
ensure_shippable(pallet)
origin = pallet.location_code
pallet.location_code = None
pallet.left_at = datetime.now(UTC).replace(tzinfo=None)
record_event(session, PalletEvent.SHIPPED, {"pallet": pallet.code, "from": origin}, destinations=["sap"])

# pallet comes back empty
pallet.sku = pallet.lot_no = pallet.qty = None
pallet.qc_status = pallet.qc_lock_reason = None   # an empty pallet has no QC status
pallet.left_at = None
record_event(session, PalletEvent.RETURNED, {"pallet": pallet.code})
```

Standard event names (`PalletEvent`):

| Value | When |
|---|---|
| `pallet.loaded` | goods put on an empty pallet |
| `pallet.putaway` | placed into a storage location |
| `pallet.moved` | moved to another location or position |
| `pallet.picked` | part of the load taken off |
| `pallet.adjusted` | quantity corrected, e.g. after a stock count |
| `pallet.shipped` | left the warehouse with its load |
| `pallet.returned` | came back |
| `pallet.retired` | retired (`deleted_at` set) |

For steps not covered, use your own `pallet.<verb>`.

## QC

The lab decides **per pallet**. Only `passed` pallets may leave the warehouse.

```
(loaded) → waiting → passed
                   → locked → passed   (passed on re-test)
           passed  → locked            (recall)
```

Any other change raises `InvalidQcTransition` (defined once, in `QC_TRANSITIONS`).

```python
set_qc_status(session, pallet, QcStatus.PASSED)
set_qc_status(session, pallet, QcStatus.LOCKED, reason="moisture above limit")  # reason required
ensure_shippable(pallet)   # raises NotShippable unless passed
```

- Locking without a reason (or with only spaces) → `MissingLockReason`
- The current reason is in `pallets.qc_lock_reason`; every past reason is in the `pallet.qc_locked` events
- A warehouse without a lab sets `WAITING` then `PASSED` right after loading
- The database cannot enforce that shipped pallets passed QC: call `ensure_shippable` before every shipment

## Locations

```
plant → warehouse → zone → location
```

- `locations.code` is the code people in the warehouse use, e.g. `tl-w3-1-0102`
- `is_enabled = 0` = temporarily closed (nothing may be put there), unlike `deleted_at`, which retires it for good
- Addressing and capacity (column / row / level / slot / pallet length) live in the factory's `location_properties`
- Zone attributes (traffic flow, full / fraction, ABC class) live in the factory's `zone_properties`

The database cannot check `level_no ≤ max_level`, because they are in different tables; the application must.

## Common queries

```sql
-- QC summary
SELECT qc_status, COUNT(*) AS pallets, SUM(qty) AS qty
FROM pallets WHERE sku IS NOT NULL AND deleted_at IS NULL
GROUP BY qc_status;

-- locked pallets
SELECT code, sku, lot_no, location_code, qc_lock_reason
FROM pallets WHERE qc_status = 'locked';

-- shippable stock by warehouse and product
SELECT l.warehouse_code, p.sku, COUNT(*) AS pallets, SUM(p.qty) AS qty
FROM pallets p JOIN locations l ON l.code = p.location_code
WHERE p.qc_status = 'passed'
GROUP BY l.warehouse_code, p.sku;

-- what is in one location
SELECT code, sku, lot_no, qty, qc_status FROM pallets WHERE location_code = 'tl-w3-1-0102';

-- empty locations
SELECT l.code FROM locations l
WHERE l.is_enabled = 1 AND l.deleted_at IS NULL
  AND NOT EXISTS (SELECT 1 FROM pallets p WHERE p.location_code = l.code);

-- pallets outside the warehouse
SELECT code, sku, left_at FROM pallets WHERE left_at IS NOT NULL;
```
