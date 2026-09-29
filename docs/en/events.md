# Event log, inbox, outbox

[ภาษาไทย](../th/events.md) | **English**

```
a user action
  │ start_operation(session, actor)
  ├─ change data ────────► event_log   (automatic: <table>.inserted / updated / deleted)
  ├─ record_event(...) ──► event_log   (business event, e.g. pallet.putaway)
  │                        └─► messaging.outbox  (when destinations are given)
  └─ commit

external system ──► receive_message(...) ──► messaging.inbox ──► worker processes it
```

## event_log

One table for everything that happens in the WMS, append-only.

| Column | Meaning |
|---|---|
| `id` | sequence (the only table with an id: events have no natural key) |
| `event_type` | `<subject>.<verb>`, e.g. `products.updated`, `pallet.putaway` |
| `subject_table`, `subject_key` | the changed row, e.g. `products`, `{"sku": "A001"}` (NULL for business events) |
| `payload` | JSON: data changes = `{"column": [old, new]}`; business events = anything |
| `operation_id` | groups every event caused by one action |
| `actor` | username (FK → users), or NULL = system |
| `occurred_at` | UTC time |

### Set up once

```python
from wms_sdk.modules.events.capture import install_capture
install_capture(Session)       # Session = sessionmaker(...)
```

### Every action

```python
from wms_sdk.modules.events.capture import record_event, start_operation

operation_id = start_operation(session, actor="somchai")
product.name_thai = "new name"                         # → products.updated, automatically
record_event(session, "putaway.completed", {"sku": "A001"}, destinations=["sap"])
session.commit()
```

- Flushing without `start_operation` → `RuntimeError`
- Setting a column to its current value is not recorded
- Tables in `messaging.*` are never captured
- `updated_at` is not in the payload (the database sets it on flush); use `occurred_at`

### Good to know

- event_log is **history**, not a source of truth: stock comes from `pallets`
- It is the only record of pallet history: never purge rows still needed for traceability
- `subject_key` is JSON with sorted keys and a space after `:` (`{"code": "P1"}`); match it exactly in queries
- `actor` stores the username, not the role: if a user's role changes, past reports show the current role

### Queries

```sql
-- history of one row (indexed)
SELECT occurred_at, actor, event_type, payload FROM event_log
WHERE subject_table = 'pallets' AND subject_key = '{"code": "P-000123"}'
ORDER BY occurred_at;

-- everything one button press caused (indexed)
SELECT event_type, subject_key, payload FROM event_log WHERE operation_id = @op;

-- who locked which pallet (SQL Server)
SELECT occurred_at, actor, JSON_VALUE(payload, '$.pallet') AS pallet,
       JSON_VALUE(payload, '$.reason') AS reason
FROM event_log WHERE event_type = 'pallet.qc_locked';
```

## outbox: sending data out

`record_event(..., destinations=["sap", "notify"])` adds one row per destination to `messaging.outbox`, in the same transaction as the event, so nothing is lost if sending fails.

| Column | Meaning |
|---|---|
| `event_id`, `destination` | PK |
| `sent_at` | NULL = not sent yet |
| `attempts`, `last_error` | for retries |

A worker (part of the application, not the SDK) reads unsent rows:

```sql
SELECT o.event_id, o.destination, e.event_type, e.payload
FROM messaging.outbox o JOIN event_log e ON e.id = o.event_id
WHERE o.sent_at IS NULL;          -- a filtered index covers exactly these rows
```

On success set `sent_at`; on failure increment `attempts` and store `last_error`.

## inbox: receiving data

```python
from wms_sdk.modules.events.receive import receive_message

if receive_message(session, "sap", "MSG-001", "sales_order.created", {"order": "SO1"}):
    session.commit()      # first delivery
# the same message again → returns False, not stored twice
```

- The PK is `(source, message_id)`, the sender's own id, so duplicates are refused by the database
- A worker processes rows with `processed_at IS NULL` in `received_at` order, then sets `processed_at`
- Receiving needs no `start_operation`; processing (creating an order, etc.) calls `start_operation(session, actor=None)` like any other job

## Schema

`inbox` and `outbox` live in schema `messaging`, apart from warehouse data in `dbo`, so permissions can differ, e.g. the worker only accesses `messaging`.
