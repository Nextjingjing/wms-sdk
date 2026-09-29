# WMS SDK documentation

Read in this order the first time: **Overview → Installation → Tutorial**, then whatever you need.

| English | ภาษาไทย | |
|---|---|---|
| [Overview](en/overview.md) | [ภาพรวม](th/overview.md) | what the SDK is, diagrams, where to start |
| [Installation](en/installation.md) | [การติดตั้ง](th/installation.md) | install, sign-in, upgrade, release |
| [Tutorial](en/tutorial.md) | [Tutorial](th/tutorial.md) | build the smallest factory, step by step |
| [Examples](en/examples.md) | [ตัวอย่าง](th/examples.md) | runnable recipes with real output |
| [Design concepts](en/concepts.md) | [แนวคิดการออกแบบ](th/concepts.md) | why the schema looks this way |
| [Glossary](en/glossary.md) | [อภิธานศัพท์](th/glossary.md) | location, row, level, slot, access point ... |
| [Building a factory project](en/factory-guide.md) | [สร้างโปรเจกต์ของโรงงาน](th/factory-guide.md) | interfaces, features, seed, start-up, Alembic |
| [Stock, pallets and QC](en/inventory.md) | [stock, พาเลท และ QC](th/inventory.md) | pallet life cycle, QC, queries |
| [Event log, inbox, outbox](en/events.md) | [event log, inbox, outbox](th/events.md) | history and integration |
| [Optional features](en/features.md) | [feature เสริม](th/features.md) | machines, brand, floor_map, routing, tasks |
| [API reference](en/api.md) | [API reference](th/api.md) | functions, classes, exceptions |
| [Schema reference](en/schema.md) | [Schema reference](th/schema.md) | every table, generated from the code |
| [Troubleshooting](en/troubleshooting.md) | [แก้ปัญหา](th/troubleshooting.md) | errors, causes, fixes |
| [Getting started](en/getting-started.md) | [เริ่มต้น](th/getting-started.md) | working on this repository: tests, sandbox database |

Rules for people (and AI agents) changing this repository are in [CLAUDE.md](../CLAUDE.md).

Both languages cover the same content; `tests/test_docs.py` checks both have the same pages, that every page links to its counterpart, and that every link works. `schema.md` is generated for both by `python -m dev.gen_schema_doc`.
