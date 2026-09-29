from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Deterministic constraint names. Without them MSSQL generates random names,
# so Alembic cannot drop/alter them later. DEFAULT constraints are not covered
# (SQLAlchemy has no key for them): drop those with
# op.alter_column(..., mssql_drop_default=True), which looks the name up.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Lookup:
    """Marks a lookup table: a small value set each factory seeds itself,
    keyed by a readable `code` that other tables FK to (never a numeric id).
    Adds no columns; `verify_factory` uses it to find tables that must be
    seeded, so every lookup class must declare `code` and `name` itself.
    """
