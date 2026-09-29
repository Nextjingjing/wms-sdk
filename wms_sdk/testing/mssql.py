"""SQL Server for tests: the real target database, for what SQLite can only
imitate (ISJSON, DATETIME2, filtered indexes, constraint errors).

Start one with `docker compose -f dev/mssql/compose.yml up -d` in the SDK
repository, or point at any server you may wipe test databases on.
"""

from collections.abc import Iterable

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url


def create_mssql_test_engine(url: str | URL, schemas: Iterable[str] = ("messaging",)) -> Engine:
    """Engine on an empty database: the database named in `url` is dropped
    and recreated, then `schemas` are created in it (the SDK puts inbox /
    outbox in `messaging`). The caller creates the tables.

    Destroys data, so it refuses a database whose name does not contain
    "test".
    """
    url = make_url(url)
    name = url.database
    if not name or "test" not in name.lower():
        raise ValueError(f"refusing to recreate database {name!r}: its name must contain 'test'")
    quoted = name.replace("]", "]]")

    admin = create_engine(url.set(database="master"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.exec_driver_sql(
            f"IF DB_ID(N'{name.replace(chr(39), chr(39) * 2)}') IS NOT NULL BEGIN"
            f" ALTER DATABASE [{quoted}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;"
            f" DROP DATABASE [{quoted}] END"
        )
        connection.exec_driver_sql(f"CREATE DATABASE [{quoted}]")
    admin.dispose()

    # pre_ping: dropping a database kills its sessions, and the ODBC driver
    # may still hold pooled connections to the old one.
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as connection:
        for schema in schemas:
            connection.exec_driver_sql(f"CREATE SCHEMA [{schema.replace(']', ']]')}]")
    return engine
