from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Unicode, text
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ....core.db import Base
from .event_log import EventLog


class Outbox(Base):
    """Events waiting to be sent to an external system, one row per
    destination. Written in the same transaction as the event, so nothing is
    lost if sending fails; a worker sends rows where `sent_at` is NULL.
    """

    __tablename__ = "outbox"

    event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("event_log.id"), primary_key=True
    )
    # e.g. 'sap', 'notify'
    destination: Mapped[str] = mapped_column(String(50), primary_key=True)
    sent_at: Mapped[datetime | None] = mapped_column(DATETIME2, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Unicode(), nullable=True)

    event: Mapped[EventLog] = relationship()

    __table_args__ = (
        # The worker only ever reads unsent rows; keep that index small.
        Index(
            None,
            "event_id",
            mssql_where=text("sent_at IS NULL"),
            sqlite_where=text("sent_at IS NULL"),
        ),
        # App-layer plumbing, kept apart from warehouse data in dbo.
        {"schema": "messaging"},
    )
