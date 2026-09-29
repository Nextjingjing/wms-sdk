import json

import pytest
from sqlalchemy import select

from wms_sdk.modules.events.capture import record_event, start_operation
from wms_sdk.modules.events.models import EventLog, Inbox, Outbox
from wms_sdk.modules.events.receive import receive_message
from wms_sdk.modules.master_data.models import Product
from wms_sdk.shared.models.plant import Plant
from wms_sdk.shared.models.role import Role
from wms_sdk.shared.models.user import User


def events(session):
    return session.scalars(select(EventLog).order_by(EventLog.id)).all()


def test_flush_without_operation_raises(session):
    session.add(Plant(code="C221", name="TL"))
    with pytest.raises(RuntimeError, match="start_operation"):
        session.flush()


def test_insert_update_delete_are_captured(session):
    start_operation(session, actor=None)
    session.add(Product(sku="A001", name_thai="ปูนเก่า", name_eng="Old"))
    session.commit()

    start_operation(session, actor=None)
    session.get(Product, "A001").name_thai = "ปูนใหม่"
    session.commit()

    start_operation(session, actor=None)
    session.delete(session.get(Product, "A001"))
    session.commit()

    inserted, updated, deleted = events(session)
    assert inserted.event_type == "products.inserted"
    assert json.loads(inserted.subject_key) == {"sku": "A001"}
    assert json.loads(inserted.payload)["name_thai"] == [None, "ปูนเก่า"]
    assert json.loads(updated.payload) == {"name_thai": ["ปูนเก่า", "ปูนใหม่"]}
    assert deleted.event_type == "products.deleted"
    assert json.loads(deleted.payload)["sku"] == ["A001", None]


def test_setting_same_value_is_not_captured(session):
    start_operation(session, actor=None)
    session.add(Plant(code="C221", name="TL"))
    session.commit()

    start_operation(session, actor=None)
    plant = session.get(Plant, "C221")
    plant.name = plant.name
    session.commit()

    assert [e.event_type for e in events(session)] == ["plants.inserted"]


def test_business_event_shares_operation_and_queues_outbox(session):
    start_operation(session, actor=None)
    session.add(Role(code="Forklift", name="Forklift"))
    session.flush()
    session.add(
        User(
            username="somchai",
            employee_id="E1",
            first_name="สมชาย",
            last_name="ใจดี",
            role_code="Forklift",
        )
    )
    session.add(Product(sku="A001", name_thai="ปูน", name_eng="Cement"))
    session.commit()

    operation_id = start_operation(session, actor="somchai")
    session.get(Product, "A001").name_eng = "Mortar"
    record_event(session, "putaway.completed", {"sku": "A001"}, destinations=["sap", "notify"])
    session.commit()

    in_operation = [e for e in events(session) if e.operation_id == operation_id]
    assert {e.event_type for e in in_operation} == {"products.updated", "putaway.completed"}
    assert all(e.actor == "somchai" for e in in_operation)
    outbox = session.scalars(select(Outbox)).all()
    assert {o.destination for o in outbox} == {"sap", "notify"}
    assert all(o.sent_at is None and o.attempts == 0 for o in outbox)


def test_inbox_deduplicates_and_is_not_captured(session):
    assert receive_message(session, "sap", "M-1", "sales_order.created", {"so": "SO1"})
    session.commit()
    assert not receive_message(session, "sap", "M-1", "sales_order.created", {"so": "SO1"})

    assert len(session.scalars(select(Inbox)).all()) == 1
    assert events(session) == []
