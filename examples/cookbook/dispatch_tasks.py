"""Dispatch work and location reservations with the tasks feature:

    python -m examples.cookbook.dispatch_tasks

One sales order → one dispatch task per pallet, sharing a reference. Each
task reserves its staging position while it is open; a second task for the
same position is refused by the database until the first one is finished.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from examples.cookbook.site import open_site
from examples.reference_factory.models import Pallet, Task
from wms_sdk.features.tasks.repository import set_task_status
from wms_sdk.modules.events.capture import start_operation
from wms_sdk.modules.inventory.qc import QcStatus

STAGING = "tl-w1-1-0203"  # last row of column 1 is the loading lane


def dispatch_task(session, pallet_code: str, level_no: int, order: str) -> Task:
    task = Task(
        task_type_code="dispatch",
        assigned_role_code="Forklift",
        pallet_code=pallet_code,
        to_location_code=STAGING,
        to_level_no=level_no,
        to_slot_no=1,
        reference=order,
    )
    set_task_status(session, task, "open")
    return task


def main() -> None:
    session = open_site()

    start_operation(session, actor="forklift1")
    for n, location in enumerate(["tl-w1-1-0101", "tl-w1-1-0102", "tl-w1-1-0201"], start=1):
        session.add(Pallet(code=f"P-{n:04}", sku="A001", lot_no="L1", qty=40, qc_status=QcStatus.PASSED,
                           location_code=location, level_no=1, slot_no=1))  # fmt: skip
    session.commit()

    start_operation(session, actor="planner1")
    first = dispatch_task(session, "P-0001", level_no=1, order="SO-100")
    second = dispatch_task(session, "P-0002", level_no=2, order="SO-100")
    session.commit()
    print(f"SO-100: tasks {first.id} and {second.id} reserve {STAGING} levels 1 and 2")

    # Another order wants the same staging position: refused while task 1 is open.
    start_operation(session, actor="planner1")
    try:
        dispatch_task(session, "P-0003", level_no=1, order="SO-101")
    except IntegrityError:
        session.rollback()
        print(f"SO-101: refused, {STAGING} level 1 is already reserved")

    # QC checks have no destination, so they never collide.
    start_operation(session, actor="planner1")
    for pallet_code in ["P-0001", "P-0002"]:
        set_task_status(session, Task(task_type_code="qc_check", assigned_role_code="Lab", pallet_code=pallet_code), "open")
    session.commit()
    print("qc_check tasks: 2 open, no reservation")

    # Finishing task 1 frees its position; SO-101 can now reserve it.
    start_operation(session, actor="forklift1")
    set_task_status(session, first, "in_progress")
    set_task_status(session, first, "done")
    session.commit()
    start_operation(session, actor="planner1")
    retry = dispatch_task(session, "P-0003", level_no=1, order="SO-101")
    session.commit()
    print(f"SO-101: task {retry.id} reserves {STAGING} level 1 after task {first.id} is done")

    print("tasks of SO-100:")
    for task in session.scalars(select(Task).where(Task.reference == "SO-100").order_by(Task.id)):
        print(f"  task {task.id}: {task.pallet_code} -> {task.to_location_code} L{task.to_level_no} ({task.status_code})")


if __name__ == "__main__":
    main()
