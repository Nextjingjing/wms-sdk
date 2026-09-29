# การติดตั้ง

**ภาษาไทย** | [English](../en/installation.md)

SDK อยู่ใน GitHub repository แบบ **private**:

```
https://github.com/Nextjingjing/wms-sdk
```

| ต้องการ | อ่าน |
|---|---|
| ใช้ SDK ในโปรเจกต์ของโรงงาน | [ติดตั้งเป็น package](#ติดตั้งเป็น-package) |
| แก้ตัว SDK | [พัฒนา SDK](#พัฒนา-sdk) |
| ออกเวอร์ชันใหม่ | [ออกเวอร์ชัน](#ออกเวอร์ชัน) |

## ก่อนเริ่ม

- **Python 3.11** ขึ้นไป
- **Git** (pip ติดตั้งจาก GitHub ผ่าน git)
- **สิทธิ์เข้า repository** — repo เป็น private ให้เจ้าของเพิ่มบัญชี GitHub ของคุณก่อน
- **Microsoft ODBC Driver 18 for SQL Server** เฉพาะถ้าจะต่อ SQL Server ([ดาวน์โหลด](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)) ถ้า test บน SQLite อย่างเดียวไม่ต้องมี

## ติดตั้งเป็น package

ระบุ tag ของเวอร์ชันเสมอ ทุกคนจะได้โค้ดชุดเดียวกัน

```bash
pip install "wms-sdk[mssql] @ git+https://github.com/Nextjingjing/wms-sdk.git@v0.1.2"
```

- `[mssql]` ติดตั้ง `pyodbc` สำหรับ SQL Server ด้วย ถ้าใช้แค่ SQLite ไม่ต้องใส่
- ตัวเลือกสำหรับ feature เสริม ใส่หลายตัวคั่นด้วยจุลภาค เช่น `wms-sdk[mssql,routing,floor_map]`:

  | ตัวเลือก | ติดตั้ง | ใช้กับ |
  |---|---|---|
  | `mssql` | pyodbc | ต่อ SQL Server |
  | `routing` | networkx | `features.routing.graph` / `repository` (หาเส้นทางสั้นสุด) |
  | `floor_map` | shapely | `features.floor_map.geometry` (ตรวจรูปทรงคลัง) |

  ตารางของ feature ไม่ต้องใช้ตัวเลือกเหล่านี้ migration จึงรันได้โดยไม่ต้องติดตั้ง
- `@v0.1.2` คือ tag ของเวอร์ชัน ดูเวอร์ชันที่มีได้จาก tags / releases ของ repo

### เข้าสู่ระบบสำหรับ repo private

pip เรียก git และ git ต้องใช้บัญชี GitHub ของคุณ

| วิธี | ทำยังไง |
|---|---|
| **Windows: Git Credential Manager** (ง่ายที่สุด) | มากับ Git for Windows ติดตั้งครั้งแรกจะเปิดเบราว์เซอร์ให้ login GitHub |
| **GitHub CLI** | `gh auth login` แล้ว `gh auth setup-git` |
| **SSH key** | เพิ่ม key ใน GitHub แล้วใช้ URL แบบ SSH ด้านล่าง |
| **Personal access token** (CI, server) | fine-grained token ที่มีสิทธิ์ *Contents: Read* เฉพาะ repo นี้ |

URL แบบ SSH:

```bash
pip install "wms-sdk[mssql] @ git+ssh://git@github.com/Nextjingjing/wms-sdk.git@v0.1.2"
```

ถ้าใช้ token ให้อ่านจาก environment variable **ห้ามเขียน token ลงไฟล์ที่ถูก commit**

```bash
pip install "wms-sdk[mssql] @ git+https://${GITHUB_TOKEN}@github.com/Nextjingjing/wms-sdk.git@v0.1.2"
```

### ใส่ในโปรเจกต์

`requirements.txt`:

```
wms-sdk[mssql] @ git+https://github.com/Nextjingjing/wms-sdk.git@v0.1.2
```

หรือ `pyproject.toml`:

```toml
[project]
dependencies = [
    "wms-sdk[mssql] @ git+https://github.com/Nextjingjing/wms-sdk.git@v0.1.2",
]
```

### ตรวจว่าติดตั้งได้

```bash
python -c "import wms_sdk; print(wms_sdk.__version__)"
```

ได้ `0.1.2` แล้วไปต่อที่ [สร้างโปรเจกต์ของโรงงาน](factory-guide.md)

### ระบุอย่างอื่นแทน tag

| ระบุ | ตัวอย่าง | ใช้เมื่อ |
|---|---|---|
| tag | `@v0.1.2` | ใช้งานปกติ (แนะนำ) |
| commit | `@6997a3f` | ลองการแก้ที่ยังไม่ออกเวอร์ชัน |
| branch | `@main` | ห้ามใช้ใน production — โค้ดเปลี่ยนได้ตลอด |

### อัปเกรด

แก้ tag ใน `requirements.txt` / `pyproject.toml` แล้ว:

```bash
pip install --upgrade -r requirements.txt
```

ถ้าระบุเป็น branch pip จะไม่รู้ว่ามี commit ใหม่ ให้เพิ่ม `--force-reinstall --no-deps` สำหรับ `wms-sdk`

การอัปเกรดอาจเปลี่ยน schema อ่าน release notes แล้วสร้าง Alembic migration ในโปรเจกต์ของโรงงาน (ดู [factory-guide.md](factory-guide.md#7-alembic))

### ไม่มีสิทธิ์เข้า GitHub

ให้คนที่มีสิทธิ์ build wheel แล้วส่งไฟล์ให้:

```bash
python -m pip install build
python -m build --wheel          # ได้ dist/wms_sdk-0.1.2-py3-none-any.whl
```

```bash
pip install "wms_sdk-0.1.2-py3-none-any.whl[mssql]"
```

### ถอนการติดตั้ง

```bash
pip uninstall wms-sdk
```

## พัฒนา SDK

```bash
git clone https://github.com/Nextjingjing/wms-sdk.git
cd wms-sdk
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt   # Linux / macOS: .venv/bin/python
.venv\Scripts\python -m pytest
```

อ่านต่อที่ [เริ่มต้น](getting-started.md) กฎการแก้โค้ดอยู่ใน [CLAUDE.md](../../CLAUDE.md)

## ออกเวอร์ชัน

สำหรับผู้ดูแล เวอร์ชันเป็นแบบ `MAJOR.MINOR.PATCH` การเปลี่ยนที่ทำให้โปรเจกต์ของโรงงานพัง (เปลี่ยนชื่อคอลัมน์, ลบตาราง, เพิ่ม interface ที่บังคับ) ต้องขึ้น MAJOR

1. แก้ `__version__` ใน `wms_sdk/__init__.py`
2. `python -m pytest` ผ่าน
3. `python -m dev.gen_schema_doc` ถ้า schema เปลี่ยน
4. commit แล้วสร้าง tag และ push:

   ```bash
   git tag v0.2.0
   git push origin main
   git push origin v0.2.0
   ```

5. ไม่บังคับ: สร้าง GitHub release ของ tag นั้น แนบ wheel จาก `python -m build --wheel` และเขียนรายการ schema ที่เปลี่ยนซึ่งโรงงานต้องทำ migration
