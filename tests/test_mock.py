"""The mock data must keep loading as the schema changes."""

from sqlalchemy import func, select

from dev import mock
from examples.reference_factory.models import Pallet
from examples.reference_factory.seed import seed
from wms_sdk.checks import verify_factory
from wms_sdk.modules.events.models import EventLog
from wms_sdk.modules.inventory.qc import QcStatus


def test_mock_data_loads_with_every_qc_state(session):
    seed(session)
    mock.populate(session)
    verify_factory(session)

    loaded = mock.LOADED_PALLETS
    assert session.scalar(select(func.count()).select_from(Pallet)) == loaded + mock.EMPTY_PALLETS
    statuses = set(session.scalars(select(Pallet.qc_status).where(Pallet.sku.is_not(None))))
    assert statuses == {QcStatus.WAITING, QcStatus.LOCKED, QcStatus.PASSED}
    assert session.scalar(select(func.count()).select_from(EventLog)) > loaded
