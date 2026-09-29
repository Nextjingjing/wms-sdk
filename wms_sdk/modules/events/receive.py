import json

from sqlalchemy.orm import Session

from .models import Inbox


def receive_message(
    session: Session, source: str, message_id: str, message_type: str, payload: dict
) -> bool:
    """Store an incoming message. Returns False if it was already received.
    The (source, message_id) primary key is the final guard against two
    concurrent deliveries; this check only avoids the common duplicate.
    """
    if session.get(Inbox, (source, message_id)) is not None:
        return False
    session.add(
        Inbox(
            source=source,
            message_id=message_id,
            message_type=message_type,
            payload=json.dumps(payload, ensure_ascii=False, default=str),
        )
    )
    return True
