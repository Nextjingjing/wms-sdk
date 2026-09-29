# WMS SDK

[English](README.md) | **ภาษาไทย**

SDK สำหรับออกแบบฐานข้อมูล WMS (Warehouse Management System) ที่ใช้ร่วมกันได้หลายโรงงาน
Python + SQLAlchemy 2.0 เป้าหมายคือ Microsoft SQL Server

- **core** — ตารางที่ทุกคลังต้องมี: โรงงาน, ผู้ใช้, สินค้า, คลัง / โซน / ตำแหน่ง, พาเลท, QC, event log
- **interface** — ตารางที่ทุกโรงมีแต่คอลัมน์ต่างกัน: SDK กำหนด key, โรงงานเพิ่มคอลัมน์
- **feature** — ส่วนเสริมที่เลือกเปิด: machines, brand, floor_map (แผนที่ + ตัวช่วยสร้างแมพ), routing (เส้นทาง forklift), tasks (งาน + การจอง location)
- ติดตั้งเป็น package ได้ แต่ละโรงงานมีโปรเจกต์ของตัวเอง เจนได้ด้วย `wms-sdk init` (ดู[สร้างโปรเจกต์ของโรงงาน](docs/th/factory-guide.md#เริ่มเร็ว-เจนโปรเจกต์)) — ตัวอย่างเต็มอยู่ที่ `examples/reference_factory/`

## ติดตั้ง

```bash
pip install "wms-sdk[mssql] @ git+https://github.com/Nextjingjing/wms-sdk.git@v0.1.2"
```

repo เป็น private ดูวิธี login ที่ [การติดตั้ง](docs/th/installation.md)

## พัฒนา

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt   # Linux / macOS: .venv/bin/python
.venv\Scripts\python -m pytest                                # test ทั้งหมด (SQLite)
.venv\Scripts\python -m dev.create_db --mock                  # dev.sqlite พร้อมข้อมูลตัวอย่าง
```

## เอกสาร

| หน้า | |
|---|---|
| [ภาพรวม](docs/th/overview.md) | SDK คืออะไร แผนภาพ เริ่มอ่านจากไหน |
| [การติดตั้ง](docs/th/installation.md) | ติดตั้งจาก GitHub (private), login, ระบุเวอร์ชัน, อัปเกรด, ออกเวอร์ชัน |
| [Tutorial](docs/th/tutorial.md) | สร้างโรงงานที่เล็กที่สุดทีละขั้น |
| [ตัวอย่าง](docs/th/examples.md) | สูตรที่รันได้: วงจรพาเลท, แมพและเส้นทาง, งานจ่าย |
| [แนวคิดการออกแบบ](docs/th/concepts.md) | core / interface / feature, key ธรรมชาติ, lookup vs enum, soft delete |
| [อภิธานศัพท์](docs/th/glossary.md) | location, row, level, slot, access point ... |
| [สร้างโปรเจกต์ของโรงงาน](docs/th/factory-guide.md) | `wms-sdk init`, interface, feature, seed, เริ่มระบบ, Alembic, test, container image |
| [stock, พาเลท และ QC](docs/th/inventory.md) | วงจรพาเลท, สถานะ, QC, query ที่ใช้บ่อย |
| [event log, inbox, outbox](docs/th/events.md) | ประวัติ, ส่งและรับข้อมูลกับระบบอื่น |
| [feature เสริม](docs/th/features.md) | machines, brand, floor_map, routing, tasks |
| [API reference](docs/th/api.md) | ฟังก์ชัน คลาส exception |
| [Schema reference](docs/th/schema.md) | ทุกตาราง คอลัมน์ และกฎ — สร้างอัตโนมัติจากโค้ด |
| [แก้ปัญหา](docs/th/troubleshooting.md) | error สาเหตุ และวิธีแก้ |
| [เริ่มต้น](docs/th/getting-started.md) | พัฒนา repo นี้ |

## สถานะ

- เวอร์ชัน 0.1.2 — test รันบน SQLite และทั้งชุดผ่านบน SQL Server 2022 (Docker) ด้วย รวมถึง Alembic migration ของตัวอย่างอ้างอิง
- ยังไม่ได้ใช้งานจริงใน production

กฎสำหรับคนแก้โค้ดใน repo นี้ (รวมถึง AI agent) อยู่ใน [CLAUDE.md](CLAUDE.md)
