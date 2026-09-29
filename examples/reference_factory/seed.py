"""Lookup rows for the reference factory. Run once per database, then call
`verify_factory(session)` at startup.
"""

from sqlalchemy.orm import Session

from wms_sdk.features.brand import Brand
from wms_sdk.modules.events.capture import start_operation
from wms_sdk.shared.models.role import Role
from wms_sdk.features.machines import MachineGroup
from wms_sdk.features.tasks.models import TaskStatus, TaskType

from .models import AbcClass, PalletFill, TicketFormat, TrafficFlow
from .roles import RoleCode

# code -> display name
ROLES = {role.value: role.value for role in RoleCode}
MACHINE_GROUPS = {
    "MIX": "Mixing",
    "PACK": "Packing",
    "YARD": "ลานจ่าย",  # dispatch yard, visible to every plant
}
BRANDS = {"NORD": "Nord", "TERRA": "Terra", "SOLIS": "Solis"}
TICKET_FORMATS = {
    "STD": "Standard",
    "EXPORT": "Export",
    "LOGO": "LOGO (ตัว L)",
}

TRAFFIC_FLOWS = {"oneway": "One-way", "twoway": "Two-way"}
PALLET_FILLS = {"full": "Full pallet", "fraction": "Fraction pallet"}
ABC_CLASSES = {"A": "A", "B": "B", "C": "C"}
TASK_TYPES = {
    "putaway": "Put away",
    "move": "Move",
    "pick": "Pick",
    "dispatch": "Dispatch",
    "qc_check": "QC check",
}
TASK_STATUSES = {
    "open": "Open",
    "in_progress": "In progress",
    "done": "Done",
    "cancelled": "Cancelled",
}


def seed(session: Session) -> None:
    """Idempotent: re-running updates names instead of failing on duplicates."""
    start_operation(session, actor=None)
    lookups = [
        (Role, ROLES),
        (MachineGroup, MACHINE_GROUPS),
        (Brand, BRANDS),
        (TicketFormat, TICKET_FORMATS),
        (TrafficFlow, TRAFFIC_FLOWS),
        (PalletFill, PALLET_FILLS),
        (AbcClass, ABC_CLASSES),
        (TaskType, TASK_TYPES),
        (TaskStatus, TASK_STATUSES),
    ]
    for model, rows in lookups:
        for code, name in rows.items():
            session.merge(model(code=code, name=name))
    session.commit()
