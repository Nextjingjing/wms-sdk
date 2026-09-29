from datetime import datetime
from typing import ClassVar

from sqlalchemy import BigInteger, ForeignKey, Index, String, Unicode, func, text
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from ...core.db import Base, Lookup
from ...core.interface import Interface


class TaskType(Lookup, Base):
    """Kinds of work, seeded by each factory (e.g. putaway, pick, qc_check)."""

    __tablename__ = "task_types"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False)


class TaskStatus(Lookup, Base):
    """Task statuses, seeded by each factory (e.g. open, done, cancelled)."""

    __tablename__ = "task_statuses"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(100), nullable=False)


class TaskBase(Interface, root=True):
    """Interface for the `tasks` table: one row per piece of work. The SDK
    fixes only the id, type and status; the factory adds everything else
    (who it is for, pallet, from / to, vehicle ...) and configures:

    - `active_statuses`: statuses that mean "not finished yet"
    - `reservation_columns`: columns that, on an active task, reserve a
      place, e.g. ("to_location_code",) or with level / slot. The SDK adds
      a unique index so two active tasks cannot reserve the same place.
    - `transitions`: allowed status changes for `set_task_status`
      (None = the status a new task may start in)
    """

    __tablename__ = "tasks"

    active_statuses: ClassVar[tuple[str, ...]] = ()
    reservation_columns: ClassVar[tuple[str, ...]] = ()
    transitions: ClassVar[dict[str | None, set[str]]] = {}

    # sort_order: mixin columns are otherwise placed after the factory's.
    # Surrogate id: work has no natural key; this is the task number people quote.
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, sort_order=-3
    )
    task_type_code: Mapped[str] = mapped_column(
        String(30), ForeignKey("task_types.code"), nullable=False, sort_order=-2
    )
    status_code: Mapped[str] = mapped_column(
        String(30), ForeignKey("task_statuses.code"), nullable=False, sort_order=-1
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2, nullable=False, server_default=func.sysutcdatetime()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME2,
        nullable=False,
        server_default=func.sysutcdatetime(),
        onupdate=func.sysutcdatetime(),
    )

    # Work lists ("open putaway tasks") filter on status, then type.
    base_table_args = (Index(None, "status_code", "task_type_code"),)

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return (*cls.base_table_args, *_reservation_index(cls), *cls.extra_table_args)


def _reservation_index(cls) -> tuple:
    if not cls.reservation_columns:
        return ()
    if not cls.active_statuses:
        raise TypeError(f"{cls.__qualname__}: reservation_columns needs active_statuses")
    statuses = ", ".join("'" + status.replace("'", "''") + "'" for status in cls.active_statuses)
    # Only active tasks that name a place reserve it. The NOT NULL terms also
    # keep tasks without a place from colliding: a SQL Server unique index
    # treats NULLs as equal.
    not_null = " AND ".join(f"{column} IS NOT NULL" for column in cls.reservation_columns)
    where = text(f"status_code IN ({statuses}) AND {not_null}")
    return (
        Index(
            "uq_tasks_reservation",
            *cls.reservation_columns,
            unique=True,
            mssql_where=where,
            sqlite_where=where,
        ),
    )
