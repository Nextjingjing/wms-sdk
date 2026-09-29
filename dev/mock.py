"""Made-up sample data for the reference factory example, for trying queries by hand.
Every name and code here is invented (sku MOCK-*, users mock.*). Data is
written through the SDK (set_qc_status, record_event) so event_log holds a
realistic history. Deterministic: the same seed gives the same data.
"""

import random
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from examples.reference_factory.models import (
    LocationProperties,
    Pallet,
    ProductProperties,
    ZoneProperties,
)
from examples.reference_factory.roles import RoleCode
from wms_sdk.features.machines import Machine, ProductSourceMachine
from wms_sdk.modules.events.capture import record_event, start_operation
from wms_sdk.modules.events.receive import receive_message
from wms_sdk.modules.inventory.events import PalletEvent
from wms_sdk.modules.inventory.qc import QcStatus, set_qc_status
from wms_sdk.modules.master_data.models import PlantProduct, Product
from wms_sdk.modules.storage.models import Location, Warehouse, Zone
from wms_sdk.shared.models.plant import Plant
from wms_sdk.shared.models.user import User

PLANT = ("C221", "TL")
WAREHOUSES = ["W1", "W2"]
# zone code -> (column numbers, traffic flow, pallet fill, ABC class)
ZONES = {
    "1": ([1, 2], "twoway", "full", "A"),
    "2": ([3, 4], "oneway", "full", "B"),
    "3": ([5, 6], "oneway", "fraction", "C"),
}
ROWS_PER_COLUMN = 5
MAX_LEVEL = 3
SUB_COLUMN = 2
USERS = [
    ("mock.lab", "M-LAB-01", "แล็บ", "ตัวอย่าง", RoleCode.LAB),
    ("mock.forklift1", "M-FL-01", "โฟล์คลิฟท์", "หนึ่ง", RoleCode.FORKLIFT),
    ("mock.forklift2", "M-FL-02", "โฟล์คลิฟท์", "สอง", RoleCode.FORKLIFT),
]
# sku, Thai name, English name, brand, pallet length (cm)
PRODUCTS = [
    ("MOCK-0001", "ปูนฉาบตัวอย่าง 50 กก.", "Mock plaster 50 kg", "NORD", 120),
    ("MOCK-0002", "ปูนก่อตัวอย่าง 50 กก.", "Mock mortar 50 kg", "NORD", 120),
    ("MOCK-0003", "แผ่นบอร์ดตัวอย่าง 120x240", "Mock board 120x240", "TERRA", 240),
    ("MOCK-0004", "ไม้ฝาตัวอย่าง", "Mock siding", "TERRA", 240),
    ("MOCK-0005", "กาวซีเมนต์ตัวอย่าง", "Mock tile adhesive", "SOLIS", 120),
]
MACHINES = [("MIX1", "MIX"), ("MIX2", "MIX"), ("PACK1", "PACK")]
LOCK_REASONS = ["ความชื้นเกินเกณฑ์", "กำลังอัดต่ำกว่าสเปก", "สีไม่สม่ำเสมอ"]
LOADED_PALLETS = 120
EMPTY_PALLETS = 10


def location_code(warehouse: str, zone: str, column: int, row: int) -> str:
    return f"{PLANT[1].lower()}-{warehouse.lower()}-{zone}-{column:02}{row:02}"


def _add_all(session: Session, rows: list) -> None:
    # No ORM relationships, so rows are flushed in FK order by the caller.
    session.add_all(rows)
    session.flush()


def populate(session: Session, seed: int = 7) -> None:
    rng = random.Random(seed)

    start_operation(session, actor=None)
    _add_all(session, [Plant(code=PLANT[0], name=PLANT[1])])
    _add_all(
        session,
        [
            User(username=u, employee_id=e, first_name=f, last_name=l, role_code=r)
            for u, e, f, l, r in USERS
        ],
    )
    _add_all(session, [Machine(plant_code=PLANT[0], code=c, machine_group_code=g) for c, g in MACHINES])
    _add_all(
        session,
        [Product(sku=sku, name_thai=th, name_eng=en) for sku, th, en, _, _ in PRODUCTS],
    )
    _add_all(
        session,
        [
            ProductProperties(
                sku=sku,
                brand_code=brand,
                pcs_per_pallet=40,
                kg_per_pcs=Decimal("50.0000"),
                size="มาตรฐาน",
                size_mm="-",
                tis=True,
                ticket_format_code="STD",
            )
            for sku, _, _, brand, _ in PRODUCTS
        ],
    )
    _add_all(session, [PlantProduct(plant_code=PLANT[0], sku=p[0]) for p in PRODUCTS])
    _add_all(
        session,
        [
            ProductSourceMachine(plant_code=PLANT[0], sku=p[0], machine_code=rng.choice(MACHINES)[0])
            for p in PRODUCTS
        ],
    )

    positions = []  # (location_code, level, slot, pallet_length_cm)
    for warehouse in WAREHOUSES:
        _add_all(session, [Warehouse(plant_code=PLANT[0], code=warehouse)])
        _add_all(
            session,
            [Zone(plant_code=PLANT[0], warehouse_code=warehouse, code=z) for z in ZONES],
        )
        _add_all(
            session,
            [
                ZoneProperties(
                    plant_code=PLANT[0],
                    warehouse_code=warehouse,
                    zone_code=z,
                    traffic_flow_code=flow,
                    pallet_fill_code=fill,
                    abc_class_code=abc,
                )
                for z, (_, flow, fill, abc) in ZONES.items()
            ],
        )
        locations, properties = [], []
        for zone, (columns, *_) in ZONES.items():
            for column in columns:
                length = 120 if column % 2 else 240
                for row in range(1, ROWS_PER_COLUMN + 1):
                    code = location_code(warehouse, zone, column, row)
                    locations.append(
                        Location(
                            code=code,
                            plant_code=PLANT[0],
                            warehouse_code=warehouse,
                            zone_code=zone,
                            # One closed location per column, to try is_enabled filters.
                            is_enabled=row != ROWS_PER_COLUMN,
                        )
                    )
                    properties.append(
                        LocationProperties(
                            location_code=code,
                            plant_code=PLANT[0],
                            warehouse_code=warehouse,
                            column_no=column,
                            row_no=row,
                            max_level=MAX_LEVEL,
                            sub_column=SUB_COLUMN,
                            pallet_length_cm=length,
                        )
                    )
                    if row != ROWS_PER_COLUMN:
                        positions += [
                            (code, level, slot, length)
                            for level in range(1, MAX_LEVEL + 1)
                            for slot in range(1, SUB_COLUMN + 1)
                        ]
        _add_all(session, locations)
        _add_all(session, properties)
    session.commit()

    _load_pallets(session, rng, positions)
    _messages(session)


def _load_pallets(session: Session, rng: random.Random, positions: list) -> None:
    lengths = {sku: length for sku, _, _, _, length in PRODUCTS}
    free = positions[:]
    rng.shuffle(free)
    for n in range(1, LOADED_PALLETS + 1):
        sku = rng.choice(PRODUCTS)[0]
        lot_no = f"MOCK-LOT-{rng.randint(1, 12):03}"
        forklift = rng.choice(["mock.forklift1", "mock.forklift2"])

        start_operation(session, actor=forklift)
        pallet = Pallet(code=f"MOCK-P{n:05}", sku=sku, lot_no=lot_no, qty=rng.choice([20, 30, 40]))
        set_qc_status(session, pallet, QcStatus.WAITING)
        session.add(pallet)
        session.flush()
        record_event(session, PalletEvent.LOADED, {"pallet": pallet.code, "sku": sku, "lot_no": lot_no})

        spot = next((p for p in free if p[3] == lengths[sku]), None)
        if spot is not None:
            free.remove(spot)
            pallet.location_code, pallet.level_no, pallet.slot_no = spot[0], spot[1], spot[2]
            record_event(session, PalletEvent.PUTAWAY, {"pallet": pallet.code, "to": spot[0]})
        session.commit()

        outcome = rng.random()
        if outcome < 0.2:
            continue  # stays waiting for the lab
        start_operation(session, actor="mock.lab")
        if outcome < 0.3:
            set_qc_status(session, pallet, QcStatus.LOCKED, reason=rng.choice(LOCK_REASONS))
        else:
            set_qc_status(session, pallet, QcStatus.PASSED)
        session.commit()

        if outcome > 0.9 and pallet.location_code is not None:
            start_operation(session, actor=forklift)
            origin = pallet.location_code
            pallet.location_code = pallet.level_no = pallet.slot_no = None
            pallet.left_at = datetime.now(UTC).replace(tzinfo=None)
            record_event(
                session,
                PalletEvent.SHIPPED,
                {"pallet": pallet.code, "from": origin},
                destinations=["sap"],
            )
            session.commit()

    start_operation(session, actor=None)
    session.add_all(Pallet(code=f"MOCK-E{n:03}") for n in range(1, EMPTY_PALLETS + 1))
    session.commit()


def _messages(session: Session) -> None:
    receive_message(
        session,
        "sap",
        "MOCK-MSG-0001",
        "sales_order.created",
        {"order": "MOCK-SO-0001", "lines": [{"sku": "MOCK-0001", "qty": 80}]},
    )
    session.commit()
