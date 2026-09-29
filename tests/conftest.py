"""Tests run on in-memory SQLite (see wms_sdk/testing/sqlite.py) with the reference
factory example loaded; on SQL Server when WMS_TEST_MSSQL_URL is set (see wms_sdk/testing).
"""

import pytest
from sqlalchemy.orm import sessionmaker

import examples.reference_factory.seed  # noqa: F401  (registers the example's tables)
from wms_sdk.metadata import metadata
from wms_sdk.modules.events.capture import install_capture
from wms_sdk.testing import create_test_engine


@pytest.fixture
def engine():
    engine = create_test_engine("pytest")
    metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    factory = sessionmaker(engine)
    install_capture(factory)
    with factory() as session:
        yield session
