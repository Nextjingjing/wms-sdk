"""Writes `event_log` rows. Usage per user action:

    start_operation(session, actor="somchai")
    ... change rows ...                       # captured automatically on flush
    record_event(session, "putaway.completed", {...}, destinations=["sap"])
    session.commit()

Call `install_capture(SessionFactory)` once at startup.
"""

import json
import uuid

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session, sessionmaker

from .models import EventLog, Outbox

_OPERATION_ID = "wms_operation_id"
_ACTOR = "wms_actor"


def start_operation(session: Session, actor: str | None) -> uuid.UUID:
    """Start a user action; every event until the next call shares its id.
    `actor` is a username, or None for system jobs.
    """
    operation_id = uuid.uuid4()
    session.info[_OPERATION_ID] = operation_id
    session.info[_ACTOR] = actor
    return operation_id


def record_event(
    session: Session, event_type: str, payload: dict, destinations: list[str] = ()
) -> EventLog:
    """Record a business event; each destination gets an outbox row."""
    entry = EventLog(
        event_type=event_type,
        payload=_to_json(payload),
        operation_id=_current_operation(session),
        actor=session.info[_ACTOR],
    )
    session.add(entry)
    for destination in destinations:
        session.add(Outbox(event=entry, destination=destination))
    return entry


def install_capture(session_factory: sessionmaker) -> None:
    event.listen(session_factory, "before_flush", _capture_changes)


def _capture_changes(session: Session, flush_context, instances) -> None:
    changes = [
        *(("inserted", obj) for obj in session.new),
        *(("updated", obj) for obj in session.dirty),
        *(("deleted", obj) for obj in session.deleted),
    ]
    for verb, obj in changes:
        # The log itself and messaging plumbing (inbox/outbox) are not warehouse data.
        if isinstance(obj, EventLog) or obj.__table__.schema == "messaging":
            continue
        payload = _changed_columns(obj, verb)
        if not payload:
            continue  # marked dirty but no column actually changed
        table = obj.__table__.name
        session.add(
            EventLog(
                event_type=f"{table}.{verb}",
                subject_table=table,
                subject_key=_to_json(_primary_key(obj)),
                payload=_to_json(payload),
                operation_id=_current_operation(session),
                actor=session.info[_ACTOR],
            )
        )


def _changed_columns(obj, verb: str) -> dict:
    """{"column": [old, new]}; old is None on insert, new is None on delete."""
    state = inspect(obj)
    result = {}
    for attr in state.mapper.column_attrs:
        history = state.attrs[attr.key].history
        if verb == "inserted":
            new = history.added[0] if history.added else None
            if new is not None:
                result[attr.key] = [None, new]
        elif verb == "updated":
            if history.has_changes():
                old = history.deleted[0] if history.deleted else None
                new = history.added[0] if history.added else None
                result[attr.key] = [old, new]
        else:
            old = (history.unchanged or history.deleted or [None])[0]
            if old is not None:
                result[attr.key] = [old, None]
    return result


def _primary_key(obj) -> dict:
    mapper = inspect(obj).mapper
    return {col.key: getattr(obj, mapper.get_property_by_column(col).key) for col in mapper.primary_key}


def _current_operation(session: Session) -> uuid.UUID:
    operation_id = session.info.get(_OPERATION_ID)
    if operation_id is None:
        raise RuntimeError("no operation started; call start_operation(session, actor) first")
    return operation_id


def _to_json(value: dict) -> str:
    # sort_keys: the same row key always serializes identically, so it can be searched.
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
