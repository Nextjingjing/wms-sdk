"""Lab QC of pallets. The lab passes or locks each pallet; only passed
pallets may leave the warehouse. A warehouse without a lab sets PASSED
right after WAITING when goods are loaded.
"""

import enum
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from ..events.capture import record_event

if TYPE_CHECKING:
    from .models import PalletBase


class QcStatus(enum.StrEnum):
    WAITING = "waiting"  # awaiting lab result; may not be shipped
    LOCKED = "locked"  # failed lab; may not be shipped
    PASSED = "passed"  # ready to ship


# The only allowed changes. None = pallet just loaded. Unloading a pallet
# clears qc_status together with sku/lot/qty.
QC_TRANSITIONS: dict[QcStatus | None, set[QcStatus]] = {
    None: {QcStatus.WAITING},
    QcStatus.WAITING: {QcStatus.PASSED, QcStatus.LOCKED},
    QcStatus.LOCKED: {QcStatus.PASSED},  # passed on re-test
    QcStatus.PASSED: {QcStatus.LOCKED},  # recalled after a later finding
}


class QcEvent(enum.StrEnum):
    PASSED = "pallet.qc_passed"
    LOCKED = "pallet.qc_locked"


class InvalidQcTransition(Exception):
    pass


class MissingLockReason(Exception):
    pass


class NotShippable(Exception):
    pass


def set_qc_status(
    session: Session, pallet: "PalletBase", new: QcStatus, reason: str | None = None
) -> None:
    """Change a pallet's QC status (WAITING when goods are loaded, then the
    lab's PASSED / LOCKED), refusing changes not in QC_TRANSITIONS.
    LOCKED requires a reason; any other status clears it.
    """
    current = pallet.qc_status
    if new not in QC_TRANSITIONS[current]:
        raise InvalidQcTransition(f"pallet {pallet.code}: {current} -> {new} is not allowed")
    reason = reason.strip() if reason else None
    if new is QcStatus.LOCKED and not reason:
        raise MissingLockReason(f"pallet {pallet.code}: locking needs a reason")
    pallet.qc_status = new
    pallet.qc_lock_reason = reason if new is QcStatus.LOCKED else None
    if new is QcStatus.PASSED:
        record_event(session, QcEvent.PASSED, {"pallet": pallet.code, "from": current})
    elif new is QcStatus.LOCKED:
        record_event(
            session, QcEvent.LOCKED, {"pallet": pallet.code, "from": current, "reason": reason}
        )


def ensure_shippable(pallet: "PalletBase") -> None:
    """Call before a pallet leaves the warehouse."""
    if pallet.qc_status is not QcStatus.PASSED:
        raise NotShippable(f"pallet {pallet.code} is {pallet.qc_status}, not passed")
