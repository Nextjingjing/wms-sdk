from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Integer, String, Unicode, func, text
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, mapped_column

from ....core.db import Base


class Inbox(Base):
    """Messages received from external systems, stored before processing.
    The key is the sender's own message id, so a message delivered twice is
    stored and processed only once.
    """

    __tablename__ = "inbox"

    # e.g. 'sap'
    source: Mapped[str] = mapped_column(String(50), primary_key=True)
    message_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    # Same <subject>.<verb> format as event_log.event_type, e.g. 'sales_order.created'.
    message_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[str] = mapped_column(Unicode(), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DATETIME2, nullable=False, server_default=func.sysutcdatetime()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DATETIME2, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Unicode(), nullable=True)

    __table_args__ = (
        CheckConstraint("message_type LIKE '%_._%'", name="message_type_format"),
        CheckConstraint("ISJSON(payload) = 1", name="payload_is_json"),
        # The worker processes unprocessed rows oldest first; keep that index small.
        Index(
            None,
            "received_at",
            mssql_where=text("processed_at IS NULL"),
            sqlite_where=text("processed_at IS NULL"),
        ),
        # App-layer plumbing, kept apart from warehouse data in dbo.
        {"schema": "messaging"},
    )
