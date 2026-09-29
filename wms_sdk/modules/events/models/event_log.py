import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Unicode, Uuid, func
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from ....core.db import Base


class EventLog(Base):
    """Everything that happened in the WMS, append-only. Two sources:
    data changes captured automatically (`<table>.inserted/updated/deleted`)
    and business events recorded by code (e.g. `putaway.completed`).

    Surrogate `id`: an event has no natural key.
    """

    __tablename__ = "event_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # The row an event is about; NULL for business events not tied to one row.
    subject_table: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Primary key of that row as JSON with sorted keys, e.g. {"plant_code":"C221","sku":"A001"}.
    subject_key: Mapped[str | None] = mapped_column(Unicode(400), nullable=True)
    # Data changes: {"column": [old, new]}. Business events: free-form.
    payload: Mapped[str] = mapped_column(Unicode(), nullable=False)
    # Groups every event caused by one user action.
    operation_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    # NULL for system jobs.
    actor: Mapped[str | None] = mapped_column(
        String(150), ForeignKey("users.username"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DATETIME2, nullable=False, server_default=func.sysutcdatetime()
    )

    __table_args__ = (
        CheckConstraint("event_type LIKE '%_._%'", name="event_type_format"),
        CheckConstraint(
            "(subject_table IS NULL AND subject_key IS NULL)"
            " OR (subject_table IS NOT NULL AND subject_key IS NOT NULL)",
            name="subject_complete",
        ),
        CheckConstraint("ISJSON(payload) = 1", name="payload_is_json"),
        CheckConstraint("subject_key IS NULL OR ISJSON(subject_key) = 1", name="subject_key_is_json"),
        Index(None, "subject_table", "subject_key", "occurred_at"),
        Index(None, "operation_id"),
        # Reports by event over a period, e.g. pallet.shipped today.
        Index(None, "event_type", "occurred_at"),
        # What one user did; also backs the actor FK.
        Index(None, "actor", "occurred_at"),
    )
