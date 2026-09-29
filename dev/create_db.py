"""Create a local SQLite database with the full schema (SDK + reference factory example)
and the example's lookup rows, for trying queries by hand:

    python -m dev.create_db                 # writes dev.sqlite
    python -m dev.create_db --mock          # plus made-up sample data (dev/mock.py)
    python -m dev.create_db other.sqlite

Recreates the file from scratch each time.
"""

import argparse
import pathlib

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

import examples.reference_factory.seed as reference_factory
from dev import mock
from wms_sdk.checks import verify_factory
from wms_sdk.metadata import metadata
from wms_sdk.modules.events.capture import install_capture
from wms_sdk.testing.sqlite import create_sqlite_engine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="dev.sqlite")
    parser.add_argument("--mock", action="store_true", help="add made-up sample data")
    args = parser.parse_args()

    path = pathlib.Path(args.path)
    path.unlink(missing_ok=True)
    engine = create_sqlite_engine(f"sqlite:///{path}")
    metadata.create_all(engine)
    factory = sessionmaker(engine)
    install_capture(factory)
    with factory() as session:
        reference_factory.seed(session)
        verify_factory(session)
        if args.mock:
            mock.populate(session)
        print(f"created {path} with {len(metadata.tables)} tables")
        if args.mock:
            _print_counts(session)


def _print_counts(session: Session) -> None:
    for name in ["locations", "pallets", "event_log", "messaging.outbox", "messaging.inbox"]:
        table = metadata.tables[name]
        count = session.scalar(select(func.count()).select_from(table))
        print(f"  {name}: {count}")


if __name__ == "__main__":
    main()
