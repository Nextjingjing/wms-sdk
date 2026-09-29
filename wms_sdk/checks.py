from sqlalchemy import select
from sqlalchemy.orm import Session

from .core.db import Base, Lookup
from .core.errors import LookupNotSeeded
from .core.interface import Interface


def verify_factory(session: Session) -> None:
    """Call at startup, after importing the factory's models. Raises if any
    SDK interface is not implemented or any lookup table in use (core,
    enabled features, or the factory's own) has not been seeded.
    """
    for interface in Interface.roots:
        interface.implementation()
    for mapper in Base.registry.mappers:
        model = mapper.class_
        if not issubclass(model, Lookup):
            continue
        if session.scalar(select(model.code).limit(1)) is None:
            raise LookupNotSeeded(f"table {model.__tablename__!r} is empty; seed it first")
