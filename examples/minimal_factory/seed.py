"""Lookup rows for the minimal factory. With no feature enabled, `roles` is
the only lookup table the SDK requires.
"""

from sqlalchemy.orm import Session

from wms_sdk.modules.events.capture import start_operation
from wms_sdk.shared.models.role import Role

ROLES = {"Operator": "Operator", "Supervisor": "Supervisor"}


def seed(session: Session) -> None:
    """Idempotent: re-running updates names instead of failing on duplicates."""
    start_operation(session, actor=None)
    for code, name in ROLES.items():
        session.merge(Role(code=code, name=name))
    session.commit()
