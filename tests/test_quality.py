import json

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from examples.reference_factory.models import Pallet
from wms_sdk.modules.inventory.qc import (
    InvalidQcTransition,
    MissingLockReason,
    NotShippable,
    QcStatus,
    ensure_shippable,
    set_qc_status,
)
from wms_sdk.modules.events.capture import start_operation
from wms_sdk.modules.events.models import EventLog
from wms_sdk.modules.master_data.models import Product


def load(session, code, lot_no="L1"):
    pallet = Pallet(code=code, sku="A001", lot_no=lot_no, qty=10)
    set_qc_status(session, pallet, QcStatus.WAITING)
    session.add(pallet)
    return pallet


@pytest.fixture
def pallets(session):
    """Three loaded pallets, all waiting for the lab."""
    start_operation(session, actor=None)
    session.add(Product(sku="A001", name_thai="ปูน", name_eng="Cement"))
    session.flush()
    rows = [load(session, "P1"), load(session, "P2"), load(session, "P3", lot_no="L2")]
    session.commit()
    return rows


def event_types(session):
    return session.scalars(select(EventLog.event_type)).all()


def test_lab_result_is_per_pallet(session, pallets):
    p1, p2, _ = pallets
    start_operation(session, actor=None)
    set_qc_status(session, p1, QcStatus.PASSED)
    set_qc_status(session, p2, QcStatus.LOCKED, reason="ความชื้นเกิน")
    session.commit()

    ensure_shippable(p1)
    with pytest.raises(NotShippable):
        ensure_shippable(p2)
    assert {"pallet.qc_passed", "pallet.qc_locked"} <= set(event_types(session))


def test_lock_keeps_reason_until_released(session, pallets):
    p1 = pallets[0]
    start_operation(session, actor=None)
    set_qc_status(session, p1, QcStatus.LOCKED, reason="  ความชื้นเกิน  ")
    session.commit()
    assert p1.qc_lock_reason == "ความชื้นเกิน"
    locked = session.scalars(select(EventLog).where(EventLog.event_type == "pallet.qc_locked")).one()
    assert json.loads(locked.payload)["reason"] == "ความชื้นเกิน"

    start_operation(session, actor=None)
    set_qc_status(session, p1, QcStatus.PASSED)  # re-test
    session.commit()
    assert p1.qc_lock_reason is None


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_lock_without_reason_raises(session, pallets, reason):
    start_operation(session, actor=None)
    with pytest.raises(MissingLockReason):
        set_qc_status(session, pallets[0], QcStatus.LOCKED, reason=reason)
    assert pallets[0].qc_status is QcStatus.WAITING


def test_waiting_pallet_is_not_shippable(pallets):
    with pytest.raises(NotShippable):
        ensure_shippable(pallets[0])


@pytest.mark.parametrize(
    "path",
    [
        [QcStatus.PASSED],
        [QcStatus.LOCKED],
        [QcStatus.LOCKED, QcStatus.PASSED],  # re-test
        [QcStatus.PASSED, QcStatus.LOCKED],  # recall
    ],
)
def test_allowed_transitions(session, pallets, path):
    start_operation(session, actor=None)
    for status in path:
        set_qc_status(session, pallets[0], status, reason="test")
    assert pallets[0].qc_status is path[-1]


@pytest.mark.parametrize(
    "path",
    [
        [QcStatus.WAITING],  # already waiting
        [QcStatus.PASSED, QcStatus.WAITING],  # back to waiting
        [QcStatus.LOCKED, QcStatus.WAITING],
    ],
)
def test_disallowed_transitions_raise(session, pallets, path):
    start_operation(session, actor=None)
    with pytest.raises(InvalidQcTransition):
        for status in path:
            set_qc_status(session, pallets[0], status, reason="test")


@pytest.mark.parametrize(
    "row",
    [
        Pallet(code="X", sku="A001", lot_no="L1", qty=1),  # loaded without status
        Pallet(code="X", qc_status="passed"),  # empty with status
        Pallet(code="X", sku="A001", lot_no="L1", qty=1, qc_status="ok"),  # unknown value
        Pallet(code="X", sku="A001", lot_no="L1", qty=1, qc_status="locked"),  # no reason
        Pallet(code="X", sku="A001", lot_no="L1", qty=1, qc_status="locked", qc_lock_reason=""),
        Pallet(code="X", sku="A001", lot_no="L1", qty=1, qc_status="passed", qc_lock_reason="x"),
    ],
    ids=[
        "loaded-without-status",
        "empty-with-status",
        "unknown-value",
        "locked-without-reason",
        "locked-blank-reason",
        "reason-while-not-locked",
    ],
)
def test_invalid_qc_rows_are_rejected(session, pallets, row):
    start_operation(session, actor=None)
    session.add(row)
    with pytest.raises((IntegrityError, LookupError)):
        session.flush()
    session.rollback()
