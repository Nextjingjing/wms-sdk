import subprocess
import sys
import textwrap

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from examples.reference_factory.models import Task
from examples.reference_factory.seed import seed
from wms_sdk.features.tasks.repository import InvalidTaskStatus, set_task_status
from wms_sdk.modules.events.capture import start_operation
from wms_sdk.modules.events.models import EventLog
from wms_sdk.modules.storage.models import Location, Warehouse, Zone
from wms_sdk.shared.models.plant import Plant

SPOT = {"to_location_code": "w1-0101", "to_level_no": 1, "to_slot_no": 1}


@pytest.fixture
def site(session):
    seed(session)
    start_operation(session, actor=None)
    for row in [
        Plant(code="C221", name="TL"),
        Warehouse(plant_code="C221", code="W1"),
        Zone(plant_code="C221", warehouse_code="W1", code="1"),
        Location(code="w1-0101", plant_code="C221", warehouse_code="W1", zone_code="1"),
    ]:
        session.add(row)
        session.flush()
    session.commit()
    return session


def new_task(session, **fields):
    task = Task(task_type_code="putaway", assigned_role_code="Forklift", **fields)
    set_task_status(session, task, "open")
    return task


def test_new_task_is_logged_with_its_id(site):
    start_operation(site, actor=None)
    task = new_task(site, **SPOT)
    site.commit()

    event = site.scalars(select(EventLog).where(EventLog.event_type == "task.status_changed")).one()
    assert f'"task": {task.id}' in event.payload


def test_two_active_tasks_cannot_reserve_the_same_position(site):
    start_operation(site, actor=None)
    new_task(site, **SPOT)
    site.commit()

    start_operation(site, actor=None)
    with pytest.raises(IntegrityError):
        new_task(site, **SPOT)


def test_finished_task_frees_its_reservation(site):
    start_operation(site, actor=None)
    first = new_task(site, **SPOT)
    set_task_status(site, first, "in_progress")
    set_task_status(site, first, "done")
    site.commit()

    start_operation(site, actor=None)
    new_task(site, **SPOT)  # same position, allowed again
    site.commit()


def test_tasks_without_a_destination_do_not_collide(site):
    start_operation(site, actor=None)
    new_task(site)  # e.g. a QC check
    new_task(site)
    site.commit()


@pytest.mark.parametrize("path", [["done"], ["in_progress", "open"], ["cancelled", "open"]])
def test_disallowed_status_changes_raise(site, path):
    start_operation(site, actor=None)
    task = new_task(site)
    with pytest.raises(InvalidTaskStatus):
        for status in path:
            set_task_status(site, task, status)


def test_new_task_must_start_in_an_allowed_status(site):
    start_operation(site, actor=None)
    task = Task(task_type_code="pick", assigned_role_code="Forklift")
    with pytest.raises(InvalidTaskStatus):
        set_task_status(site, task, "done")


def test_reservation_without_active_statuses_is_refused():
    code = textwrap.dedent(
        """
        from wms_sdk.core.db import Base
        from wms_sdk.features.tasks.models import TaskBase
        class Task(TaskBase, Base):
            reservation_columns = ("task_type_code",)
        """
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert "needs active_statuses" in result.stderr
