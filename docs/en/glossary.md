# Glossary

[ภาษาไทย](../th/glossary.md) | **English**

## Places

```
plant C221 (TL)
 └─ warehouse W1
     └─ zone 1
         └─ location tl-w1-1-0101   ← a place pallets are stored, with a code
```

| Term | Thai | Meaning | Table |
|---|---|---|---|
| **plant** | โรงงาน | a factory site; code e.g. `C221` | `plants` |
| **warehouse** | คลัง | a storage building or area in a plant; code unique per plant | `warehouses` |
| **zone** | โซน | an area inside a warehouse; flat, zones do not nest | `zones` |
| **location** | ตำแหน่ง | one place pallets are stored, with a code people use (e.g. `tl-w1-1-0101`) | `locations` |
| **enabled / retired** | เปิดใช้ / เลิกใช้ | `is_enabled = 0` closes a location for now; `deleted_at` retires it for good | `locations` |

### How the reference factory stores pallets (floor stacking)

The reference factory stacks pallets on the floor in lanes. These words belong to that example (its `location_properties`), not to the SDK:

```
        column 1 (seen from above)            one row, seen from the side
      ┌──────────────┐
row 1 │ [ ][ ]       │  ← location tl-w1-1-0101        level 2  [ ][ ]
row 2 │ [ ][ ]       │  ← location tl-w1-1-0102        level 1  [ ][ ]
row 3 │ [ ][ ]       │  ← location tl-w1-1-0103                 slot 1 2
      └──────────────┘
        ▲ lane mouth: the forklift enters here
```

| Term | Thai | Meaning |
|---|---|---|
| **column** | แนว / ล็อก | a lane of rows |
| **row** | แถว | one position along a column; **one row = one location** |
| **level** | ชั้น | how high a pallet is stacked in a row (`max_level` = capacity) |
| **slot** | ช่อง | side-by-side position in a row (`sub_column` = capacity) |
| **position** | ตำแหน่งพาเลท | location + level + slot: where exactly one pallet sits |

## Goods

| Term | Thai | Meaning | Table |
|---|---|---|---|
| **product / sku** | สินค้า | an item, identified by `sku` | `products` |
| **pallet** | พาเลท | a physical, reusable pallet with a QR / LPN code | `pallets` |
| **load** | ของบนพาเลท | the goods on a pallet now: one sku, one lot, a qty (all NULL = empty) | `pallets` |
| **lot** | ล็อตผลิต | a production batch, stored as `lot_no` on the pallet | `pallets` |
| **QC status** | สถานะ QC | `waiting` / `locked` / `passed`; only passed pallets may ship | `pallets` |
| **on-hand stock** | ยอดคงเหลือ | `SUM(qty)` over pallets; there is no balance table | |

## Building blocks of the SDK

| Term | Thai | Meaning |
|---|---|---|
| **core** | แกนกลาง | tables every warehouse has |
| **interface** | interface | an SDK table with a fixed key; each factory subclasses it once and adds columns (`*Base`) |
| **feature** | feature เสริม | optional tables and helpers; present only when imported |
| **lookup** | ตาราง lookup | a small value set each factory seeds (`roles`, `brands` ...), keyed by a readable `code` |
| **seed** | ข้อมูลตั้งต้น | the lookup rows a factory loads before use |
| **operation** | การกระทำ | one user action; `start_operation` gives all its events one `operation_id` |
| **event** | event | a row in `event_log`: a data change or a business event such as `pallet.putaway` |
| **outbox / inbox** | กล่องขาออก / ขาเข้า | messages waiting to be sent to / received from other systems |

## Routing (optional feature)

```
    A ───────────────── B ──────── D (dock)
         ▲        ▲                        vertices: A, B, D
      mouth of  mouth of                   roads: A-B, B-D (one edge per direction)
      0101      0201                       access points: where each location meets a road
```

| Term | Thai | Meaning | Table |
|---|---|---|---|
| **route map** | แผนที่ถนน | a revision of a warehouse's road network; one draft and one published at a time | `route_maps` |
| **vertex** | จุด | a corner, junction, gate or dock | `route_vertices` |
| **road / edge** | ถนน | the connection between two vertices; one edge per allowed direction | `route_edges` |
| **lane mouth / access point** | ปากช่อง | where a location meets a road: which road, how far along (`offset_ratio`), which side | `location_access_points` |

## Tasks (optional feature)

| Term | Thai | Meaning | Table |
|---|---|---|---|
| **task** | งาน | one piece of work: put away, pick, dispatch, QC check ... | `tasks` |
| **active status** | สถานะที่ยังไม่เสร็จ | statuses the factory counts as unfinished (`active_statuses`) | |
| **reservation** | การจอง | an active task's destination; no other active task may hold the same place | `tasks` (unique index) |
| **reference** | เลขอ้างอิง | an external document such as a sales order, shared by its tasks | `tasks` (factory column) |
