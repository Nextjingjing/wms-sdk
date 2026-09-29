# ภาพรวม

**ภาษาไทย** | [English](../en/overview.md)

WMS SDK คือแบบฐานข้อมูลคลังสินค้าที่ใช้ร่วมกันได้หลายโรงงาน เป็น Python package ที่มี model ของ SQLAlchemy และฟังก์ชันช่วยอีกเล็กน้อย แต่ละโรงงานติดตั้ง SDK แล้วสร้างโปรเจกต์ของตัวเองต่อจากนั้น

## ในกล่องมีอะไร

```mermaid
flowchart TB
    subgraph factory["โปรเจกต์ของโรงงาน (เช่น examples/reference_factory)"]
        impl["คลาสที่ implement interface<br/>ProductProperties · ZoneProperties<br/>LocationProperties · Pallet · Task"]
        own["lookup และ seed ของโรงงาน<br/>(roles, brands, task types ...)"]
    end
    subgraph sdk["wms_sdk"]
        core["ตาราง core<br/>plants · roles · users · products<br/>warehouses · zones · locations<br/>event_log · inbox · outbox"]
        ifaces["interface<br/>คลาส *Base"]
        features["feature เสริม<br/>machines · brand · floor_map<br/>routing · tasks"]
    end
    impl -- สืบทอด --> ifaces
    ifaces -- FK ของ key --> core
    features -- FK --> core
    factory -. import เฉพาะที่ใช้ .-> features
```

| ชั้น | คืออะไร | ใครเขียน |
|---|---|---|
| **core** | ตารางที่ทุกคลังต้องมี | SDK |
| **interface** | ตารางที่ SDK กำหนด key ส่วนคอลัมน์อื่นโรงงานเพิ่มเอง | SDK: key; โรงงาน: คอลัมน์ |
| **feature** | ตารางและฟังก์ชันเสริม ไม่ import ก็ไม่มี | SDK |
| **โปรเจกต์ของโรงงาน** | คลาสที่ implement, lookup, seed, migration และตัวแอป | โรงงาน |

ทำไมออกแบบแบบนี้: [แนวคิดการออกแบบ](concepts.md) ถ้าเจอศัพท์ที่ไม่คุ้น: [อภิธานศัพท์](glossary.md)

## เกิดอะไรขึ้นเมื่อผู้ใช้กดหนึ่งครั้ง

```mermaid
sequenceDiagram
    participant App as แอป
    participant S as Session
    participant DB as ฐานข้อมูล
    App->>S: start_operation(session, actor="forklift1")
    App->>S: แก้แถว (เช่น pallet.location_code = ...)
    App->>S: record_event(session, "pallet.putaway", {...}, destinations=["sap"])
    App->>S: commit()
    S->>DB: UPDATE pallets
    S->>DB: INSERT event_log "pallets.updated" (จับอัตโนมัติ)
    S->>DB: INSERT event_log "pallet.putaway"
    S->>DB: INSERT messaging.outbox (sap)
    Note over DB: transaction เดียว: สำเร็จทั้งหมดหรือไม่เกิดเลย
```

- **สถานะปัจจุบัน** อยู่ในตาราง (`pallets`, `locations`, `tasks` ...)
- **ประวัติ** อยู่ใน `event_log` เขียนใน transaction เดียวกัน
- **ข้อความถึงระบบอื่น** รออยู่ใน `messaging.outbox` จนกว่า worker จะส่ง

รายละเอียด: [event log, inbox, outbox](events.md)

## เริ่มอ่านจากไหน

| ต้องการ | อ่าน |
|---|---|
| เข้าใจแบบ | หน้านี้ → [แนวคิดการออกแบบ](concepts.md) → [อภิธานศัพท์](glossary.md) |
| สร้างโปรเจกต์ของโรงงาน | [การติดตั้ง](installation.md) → [Tutorial](tutorial.md) → [สร้างโปรเจกต์ของโรงงาน](factory-guide.md) |
| เขียนโค้ดของแอป | [ตัวอย่าง](examples.md) → [stock, พาเลท และ QC](inventory.md) → [feature เสริม](features.md) → [API reference](api.md) |
| แก้ตัว SDK | [เริ่มต้น](getting-started.md) → [CLAUDE.md](../../CLAUDE.md) |
| แก้ error | [แก้ปัญหา](troubleshooting.md) |
| ดูตาราง | [Schema reference](schema.md) |
