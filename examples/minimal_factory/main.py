"""Run the minimal factory end to end on in-memory SQLite:

    python -m examples.minimal_factory.main
"""

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

import wms_sdk.metadata  # noqa: F401  (registers the SDK's core tables)
from wms_sdk.checks import verify_factory
from wms_sdk.core.db import Base
from wms_sdk.modules.events.capture import install_capture, record_event, start_operation
from wms_sdk.modules.events.models import EventLog
from wms_sdk.modules.inventory.events import PalletEvent
from wms_sdk.modules.inventory.qc import QcStatus, set_qc_status
from wms_sdk.modules.master_data.models import Product
from wms_sdk.modules.storage.models import Location, Warehouse, Zone
from wms_sdk.shared.models.plant import Plant
from wms_sdk.testing.sqlite import create_sqlite_engine

from .models import Pallet
from .seed import seed


def main() -> None:
    # 1. Database and sessions: every data change is recorded in event_log.
    engine = create_sqlite_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(engine)
    install_capture(Session)

    with Session() as session:
        # 2. Seed lookups, then check the factory is complete.
        seed(session)
        verify_factory(session)
        print("factory verified")

        # 3. Master data: one plant, warehouse, zone, location and product.
        #    No ORM relationships, so rows are flushed in foreign-key order.
        start_operation(session, actor=None)
        for row in [
            Plant(code="P1", name="Main plant"),
            Warehouse(plant_code="P1", code="WH1"),
            Zone(plant_code="P1", warehouse_code="WH1", code="A"),
            Location(code="A-01", plant_code="P1", warehouse_code="WH1", zone_code="A"),
            Product(sku="SKU-1", name_thai="สินค้าตัวอย่าง", name_eng="Sample product"),
        ]:
            session.add(row)
            session.flush()
        session.commit()

        # 4. A pallet arrives and is put away.
        start_operation(session, actor=None)
        pallet = Pallet(code="PAL-1", sku="SKU-1", lot_no="LOT-1", qty=40, location_code="A-01")
        set_qc_status(session, pallet, QcStatus.WAITING)
        session.add(pallet)
        record_event(session, PalletEvent.PUTAWAY, {"pallet": pallet.code, "to": "A-01"})
        session.commit()

        # 5. Stock on hand is the sum of qty over pallets.
        stock = session.execute(
            select(Pallet.location_code, Pallet.sku, func.sum(Pallet.qty))
            .where(Pallet.location_code.is_not(None))
            .group_by(Pallet.location_code, Pallet.sku)
        ).all()
        for location_code, sku, qty in stock:
            print(f"stock: {location_code} {sku} qty={qty}")

        events = session.scalars(select(EventLog.event_type).order_by(EventLog.id)).all()
        print(f"events: {', '.join(events)}")


if __name__ == "__main__":
    main()
