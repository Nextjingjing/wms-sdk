"""Testing helpers for factory projects built on the SDK."""

import os

from sqlalchemy import Engine
from sqlalchemy.engine import make_url

from .sqlite import create_sqlite_engine

MSSQL_URL_VARIABLE = "WMS_TEST_MSSQL_URL"


def create_test_engine(name: str = "wms") -> Engine:
    """Engine for one test database, without tables.

    In-memory SQLite by default. When the environment variable
    WMS_TEST_MSSQL_URL is set (an SQLAlchemy URL to a SQL Server), a fresh
    SQL Server database `wms_test_<name>` on that server instead: the same
    tests then run on the real target database.
    """
    url = os.environ.get(MSSQL_URL_VARIABLE)
    if not url:
        return create_sqlite_engine()
    from .mssql import create_mssql_test_engine

    return create_mssql_test_engine(make_url(url).set(database=f"wms_test_{name}"))
