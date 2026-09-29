"""Alembic environment of the reference factory example. A factory project copies this:
import its models (which import the SDK's and enable its features), then
hand `wms_sdk.metadata.metadata` to Alembic.
"""

import os

from alembic import context
from alembic.operations import ops
from sqlalchemy import create_engine

import examples.reference_factory.seed  # noqa: F401  (registers the factory's tables and features)
from wms_sdk.metadata import metadata

config = context.config
URL_VARIABLE = "WMS_DATABASE_URL"


def database_url() -> str:
    url = os.environ.get(URL_VARIABLE)
    if not url:
        raise RuntimeError(f"set {URL_VARIABLE} to the SQLAlchemy URL of the database")
    return url


def options() -> dict:
    return {
        "target_metadata": metadata,
        # inbox / outbox live in schema `messaging`; without this autogenerate
        # does not see them.
        "include_schemas": True,
        "compare_type": True,
        "process_revision_directives": drop_default_schema_fk_noise,
    }


def drop_default_schema_fk_noise(context, revision, directives) -> None:
    """Remove FK changes that change nothing.

    A foreign key from another schema (messaging.outbox -> event_log) is
    reflected as pointing at `dbo.event_log`, while the model says
    `event_log` (the default schema). Alembic then drops and re-adds it on
    every autogenerate, and `alembic check` never passes.
    """
    default = context.dialect.default_schema_name

    def signature(op):
        fk = op.reverse() if isinstance(op, ops.DropConstraintOp) else op
        if not isinstance(fk, ops.CreateForeignKeyOp):
            return None
        # source_schema / referent_schema / ondelete ... are in kw.
        kw = {key: value for key, value in fk.kw.items() if value is not None}
        kw["referent_schema"] = kw.get("referent_schema") or default
        return (
            fk.constraint_name,
            fk.source_table,
            tuple(fk.local_cols),
            fk.referent_table,
            tuple(fk.remote_cols),
            tuple(sorted(kw.items(), key=lambda item: item[0])),
        )

    def clean(container) -> None:
        for op in list(container.ops):
            if isinstance(op, ops.ModifyTableOps):
                clean(op)
                if not op.ops:
                    container.ops.remove(op)
        dropped = {signature(op): op for op in container.ops if isinstance(op, ops.DropConstraintOp)}
        for op in list(container.ops):
            if isinstance(op, ops.CreateForeignKeyOp) and signature(op) in dropped:
                container.ops.remove(op)
                container.ops.remove(dropped.pop(signature(op)))

    for script in directives:
        for container in [*script.upgrade_ops_list, *script.downgrade_ops_list]:
            clean(container)


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL for a DBA to review."""
    context.configure(url=database_url(), literal_binds=True, **options())
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, **options())
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
