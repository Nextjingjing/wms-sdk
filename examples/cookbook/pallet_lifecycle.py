"""A pallet from production to the customer:

    python -m examples.cookbook.pallet_lifecycle

load → putaway task (reserves a position) → lab result → ship → history.
A second pallet is locked by the lab and cannot be shipped.
"""

from datetime import UTC, datetime

from sqlalchemy import select

from examples.cookbook.site import open_site
from examples.reference_factory.models import Pallet, Task
from wms_sdk.features.tasks.repository import set_task_status
from wms_sdk.modules.events.capture import record_event, start_operation
from wms_sdk.modules.events.models import EventLog, Outbox
from wms_sdk.modules.inventory.events import PalletEvent
from wms_sdk.modules.inventory.qc import NotShippable, QcStatus, ensure_shippable, set_qc_status


def load(session, code: str, sku: str, lot_no: str, qty: int) -> Pallet:
    """Goods from production are put on a pallet; QC starts at waiting."""
    start_operation(session, actor="forklift1")
    pallet = Pallet(code=code, sku=sku, lot_no=lot_no, qty=qty)
    set_qc_status(session, pallet, QcStatus.WAITING)
    session.add(pallet)
    record_event(session, PalletEvent.LOADED, {"pallet": code, "sku": sku, "lot_no": lot_no})
    session.commit()
    return pallet


def put_away(session, pallet: Pallet, location_code: str, level_no: int, slot_no: int) -> None:
    # The planner creates a task; its destination is reserved while it is open.
    start_operation(session, actor="planner1")
    task = Task(
        task_type_code="putaway",
        assigned_role_code="Forklift",
        pallet_code=pallet.code,
        to_location_code=location_code,
        to_level_no=level_no,
        to_slot_no=slot_no,
    )
    set_task_status(session, task, "open")
    session.commit()

    # A forklift driver takes it and moves the pallet.
    start_operation(session, actor="forklift1")
    set_task_status(session, task, "in_progress")
    pallet.location_code, pallet.level_no, pallet.slot_no = location_code, level_no, slot_no
    record_event(session, PalletEvent.PUTAWAY, {"pallet": pallet.code, "to": location_code})
    set_task_status(session, task, "done")
    session.commit()
    print(f"{pallet.code}: put away at {location_code} level {level_no} slot {slot_no} (task {task.id})")


def ship(session, pallet: Pallet) -> None:
    start_operation(session, actor="forklift1")
    ensure_shippable(pallet)  # raises NotShippable unless QC passed
    origin = pallet.location_code
    pallet.location_code = pallet.level_no = pallet.slot_no = None
    pallet.left_at = datetime.now(UTC).replace(tzinfo=None)
    record_event(
        session, PalletEvent.SHIPPED, {"pallet": pallet.code, "from": origin}, destinations=["sap"]
    )
    session.commit()
    print(f"{pallet.code}: shipped from {origin}")


def history(session, pallet_code: str) -> list[str]:
    """Events about one pallet: its own row changes and business events naming it."""
    key = '{"code": "%s"}' % pallet_code
    lines = []
    for event in session.scalars(select(EventLog).order_by(EventLog.id)):
        if event.subject_key == key or f'"pallet": "{pallet_code}"' in event.payload:
            lines.append(f"  {event.event_type:<18} by {event.actor or 'system'}")
    return lines


def main() -> None:
    session = open_site()

    good = load(session, "P-0001", "A001", "L2026-001", 40)
    bad = load(session, "P-0002", "A002", "L2026-002", 30)
    put_away(session, good, "tl-w1-1-0101", 1, 1)
    put_away(session, bad, "tl-w1-1-0102", 1, 1)

    start_operation(session, actor="lab1")
    set_qc_status(session, good, QcStatus.PASSED)
    set_qc_status(session, bad, QcStatus.LOCKED, reason="moisture above limit")
    session.commit()
    print(f"{bad.code}: locked, reason: {bad.qc_lock_reason}")

    ship(session, good)
    try:
        ship(session, bad)
    except NotShippable as error:
        session.rollback()
        print(f"{bad.code}: refused: {error}")

    print(f"history of {good.code}:")
    print("\n".join(history(session, good.code)))
    unsent = session.scalars(select(Outbox.destination).where(Outbox.sent_at.is_(None))).all()
    print(f"outbox waiting to send: {unsent}")


if __name__ == "__main__":
    main()
