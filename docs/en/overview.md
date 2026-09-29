# Overview

[ภาษาไทย](../th/overview.md) | **English**

The WMS SDK is a shared database design for warehouses. It is a Python package of SQLAlchemy models plus a few helpers. Each factory installs it and builds its own project on top.

## What is in the box

```mermaid
flowchart TB
    subgraph factory["Factory project (e.g. examples/reference_factory)"]
        impl["Interface implementations<br/>ProductProperties · ZoneProperties<br/>LocationProperties · Pallet · Task"]
        own["Factory lookups and seed<br/>(roles, brands, task types ...)"]
    end
    subgraph sdk["wms_sdk"]
        core["Core tables<br/>plants · roles · users · products<br/>warehouses · zones · locations<br/>event_log · inbox · outbox"]
        ifaces["Interfaces<br/>*Base classes"]
        features["Optional features<br/>machines · brand · floor_map<br/>routing · tasks"]
    end
    impl -- subclasses --> ifaces
    ifaces -- key columns FK --> core
    features -- FK --> core
    factory -. imports only what it needs .-> features
```

| Layer | What it is | Who writes it |
|---|---|---|
| **core** | tables every warehouse needs | the SDK |
| **interface** | a table whose key the SDK fixes and whose other columns the factory adds | SDK: key; factory: columns |
| **feature** | optional tables and helpers; absent unless imported | the SDK |
| **factory project** | implementations, lookups, seed, migrations, the application | the factory |

Why it is designed this way: [Design concepts](concepts.md). Unfamiliar words: [Glossary](glossary.md).

## What happens on one user action

```mermaid
sequenceDiagram
    participant App as Application
    participant S as Session
    participant DB as Database
    App->>S: start_operation(session, actor="forklift1")
    App->>S: change rows (e.g. pallet.location_code = ...)
    App->>S: record_event(session, "pallet.putaway", {...}, destinations=["sap"])
    App->>S: commit()
    S->>DB: UPDATE pallets
    S->>DB: INSERT event_log "pallets.updated" (captured automatically)
    S->>DB: INSERT event_log "pallet.putaway"
    S->>DB: INSERT messaging.outbox (sap)
    Note over DB: one transaction: all or nothing
```

- **Current state** lives in the tables (`pallets`, `locations`, `tasks` ...)
- **History** lives in `event_log`, written in the same transaction
- **Messages to other systems** wait in `messaging.outbox` until a worker sends them

Details: [Event log, inbox, outbox](events.md).

## Where to start

| You want to | Read |
|---|---|
| understand the design | this page → [Design concepts](concepts.md) → [Glossary](glossary.md) |
| build a factory project | [Installation](installation.md) → [Tutorial](tutorial.md) → [Building a factory project](factory-guide.md) |
| write application code | [Examples](examples.md) → [Stock, pallets and QC](inventory.md) → [Optional features](features.md) → [API reference](api.md) |
| change the SDK | [Getting started](getting-started.md) → [CLAUDE.md](../../CLAUDE.md) |
| fix an error | [Troubleshooting](troubleshooting.md) |
| look up a table | [Schema reference](schema.md) |
