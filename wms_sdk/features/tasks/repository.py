from sqlalchemy.orm import Session

from ...modules.events.capture import record_event
from .models import TaskBase


class InvalidTaskStatus(Exception):
    pass


def set_task_status(session: Session, task: TaskBase, new: str) -> None:
    """Change a task's status, refusing changes not in the factory's
    `transitions`, and record a `task.status_changed` event. For a new task
    (status not set yet), `new` must be allowed from None. Flushes, so the
    event can carry the task id.
    """
    current = task.status_code
    allowed = type(task).transitions.get(current, set())
    if new not in allowed:
        raise InvalidTaskStatus(f"task {task.id}: {current} -> {new} is not allowed")
    task.status_code = new
    if task not in session:
        session.add(task)
    session.flush()
    record_event(
        session,
        "task.status_changed",
        {"task": task.id, "type": task.task_type_code, "from": current, "to": new},
    )
