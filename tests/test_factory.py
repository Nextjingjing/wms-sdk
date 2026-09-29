"""Interfaces, optional features and startup checks.

Interface registration is process-wide, so scenarios that need a fresh
registry (SDK without any factory, a second implementation) run in a
subprocess.
"""

import subprocess
import sys
import textwrap

import pytest

from examples.reference_factory.seed import seed
from wms_sdk.checks import verify_factory
from wms_sdk.core.errors import LookupNotSeeded
from wms_sdk.features.brand import Brand


def run_python(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)], capture_output=True, text=True
    )


def test_sdk_alone_has_no_feature_tables_and_every_interface_raises():
    result = run_python(
        """
        from wms_sdk.metadata import metadata
        from wms_sdk.core.interface import Interface
        tables = set(metadata.tables)
        assert not tables & {"machines", "brands", "pallets", "product_properties", "route_maps", "floor_images"}, tables
        for root in Interface.roots:
            try:
                root.implementation()
            except NotImplementedError:
                continue
            raise AssertionError(f"{root.__tablename__} did not raise")
        print(len(Interface.roots))
        """
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "4"


def test_second_implementation_raises():
    result = run_python(
        """
        from wms_sdk.core.db import Base
        from wms_sdk.modules.storage.models import ZonePropertiesBase
        class First(ZonePropertiesBase, Base): pass
        class Second(ZonePropertiesBase, Base): pass
        """
    )
    assert "already implemented by First" in result.stderr


def test_table_args_in_implementation_raises():
    result = run_python(
        """
        from sqlalchemy import CheckConstraint
        from wms_sdk.core.db import Base
        from wms_sdk.modules.storage.models import ZonePropertiesBase
        class Bad(ZonePropertiesBase, Base):
            __table_args__ = (CheckConstraint("1 = 1", name="x"),)
        """
    )
    assert "put constraints in extra_table_args" in result.stderr


def test_verify_factory_requires_seeded_lookups(session):
    with pytest.raises(LookupNotSeeded):
        verify_factory(session)

    seed(session)
    verify_factory(session)
    assert session.get(Brand, "SOLIS").name == "Solis"
