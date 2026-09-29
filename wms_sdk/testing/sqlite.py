"""SQLite stand-in for MSSQL, for local development and tests only:

    engine = create_sqlite_engine()          # in memory
    metadata.create_all(engine)

Translates the few MSSQL-only pieces of the schema. What SQLite cannot
prove — filtered indexes (`mssql_where`), real ISJSON, DATETIME2
precision — still needs a run against MSSQL.
"""

import json

from sqlalchemy import BigInteger, Engine, create_engine, event
from sqlalchemy.dialects.mssql import DATETIME2
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import functions


@compiles(DATETIME2, "sqlite")
def _datetime2(type_, compiler, **kw):
    return "DATETIME"


@compiles(BigInteger, "sqlite")
def _bigint(type_, compiler, **kw):
    # SQLite only auto-increments an INTEGER PRIMARY KEY.
    return "INTEGER"


@compiles(functions.Function, "sqlite")
def _function(element, compiler, **kw):
    if element.name == "sysutcdatetime":
        return "CURRENT_TIMESTAMP"
    return compiler.visit_function(element, **kw)


def _isjson(value):
    try:
        json.loads(value)
        return 1
    except (TypeError, ValueError):
        return 0


def create_sqlite_engine(url: str = "sqlite://") -> Engine:
    """Engine with FKs enforced, ISJSON available and the `messaging`
    schema folded into the main database (SQLite has no schemas).
    """
    engine = create_engine(url, execution_options={"schema_translate_map": {"messaging": None}})

    @event.listens_for(engine, "connect")
    def _on_connect(connection, record):
        connection.create_function("ISJSON", 1, _isjson)
        connection.execute("PRAGMA foreign_keys=ON")

    return engine
