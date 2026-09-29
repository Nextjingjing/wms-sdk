"""The reference factory example's migrations build exactly the models' schema on SQL Server,
and tear it down again. Needs WMS_TEST_MSSQL_URL (see wms_sdk/testing).
"""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import make_url

from wms_sdk.testing import MSSQL_URL_VARIABLE
from wms_sdk.testing.mssql import create_mssql_test_engine

pytestmark = pytest.mark.skipif(
    not os.environ.get(MSSQL_URL_VARIABLE), reason=f"needs SQL Server: set {MSSQL_URL_VARIABLE}"
)


def test_migrations_match_the_models_and_downgrade_cleanly(monkeypatch):
    url = make_url(os.environ[MSSQL_URL_VARIABLE]).set(database="wms_test_alembic")
    # Empty, without the messaging schema: the first migration must create it.
    engine = create_mssql_test_engine(url, schemas=())
    monkeypatch.setenv("WMS_DATABASE_URL", url.render_as_string(hide_password=False))
    config = Config("examples/reference_factory/alembic.ini")

    command.upgrade(config, "head")
    command.check(config)  # raises if the models differ from the migrated database

    command.downgrade(config, "base")
    inspector = inspect(engine)
    assert inspector.get_table_names() == ["alembic_version"]
    assert "messaging" not in inspector.get_schema_names()
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()
