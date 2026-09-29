"""Static checks on the MSSQL DDL of the full schema (SDK + reference factory example)."""

import re
from collections import Counter

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateIndex, CreateTable

from wms_sdk.core.db import Base, Lookup
from wms_sdk.metadata import metadata

MSSQL = mssql.dialect()
MAX_IDENTIFIER = 128


def ddl_names():
    names = []
    for table in metadata.tables.values():
        names += re.findall(r"CONSTRAINT (\w+)", str(CreateTable(table).compile(dialect=MSSQL)))
        names += [index.name for index in table.indexes]
    return names


def test_constraint_and_index_names_are_unique():
    duplicates = [name for name, count in Counter(ddl_names()).items() if count > 1]
    assert duplicates == []


def test_names_fit_mssql_identifier_limit():
    assert max(map(len, ddl_names())) <= MAX_IDENTIFIER


def test_no_deprecated_ntext():
    for table in metadata.tables.values():
        for index in table.indexes:
            str(CreateIndex(index).compile(dialect=MSSQL))
        assert "NTEXT" not in str(CreateTable(table).compile(dialect=MSSQL)), table.name


# FKs deliberately left without an index. SQL Server does not index FK
# columns, so every other FK must lead some index or key.
UNINDEXED_FKS = {
    # A few dozen vertices per revision: scanning is as fast as seeking.
    ("location_access_points", ("plant_code", "warehouse_code", "revision_no", "road_start_code")),
    ("location_access_points", ("plant_code", "warehouse_code", "revision_no", "road_end_code")),
    ("route_edges", ("plant_code", "warehouse_code", "revision_no", "to_code")),
    # Users and floor images are never hard-deleted, and nobody lists by these.
    ("route_maps", ("published_by",)),
    ("warehouse_maps", ("floor_image_code",)),
}


def _backed(table, fk_columns: set[str]) -> bool:
    """An FK is backed when its columns lead an unfiltered index or key, or
    when a unique key lies within them (a seek then finds at most one row).
    """
    unique = [table.primary_key.columns] + [
        c.columns for c in table.constraints if isinstance(c, UniqueConstraint)
    ]
    indexes = unique + [i.columns for i in table.indexes if i.dialect_options["mssql"]["where"] is None]
    return any({c.name for c in list(key)[: len(fk_columns)]} == fk_columns for key in indexes) or any(
        {c.name for c in key} <= fk_columns for key in unique
    )


def test_every_foreign_key_has_an_index():
    lookups = {m.local_table for m in Base.registry.mappers if issubclass(m.class_, Lookup)}
    missing = [
        (table.fullname, cols)
        for table in metadata.sorted_tables
        for fk in table.foreign_key_constraints
        for cols in [tuple(c.name for c in fk.columns)]
        if not _backed(table, set(cols))
        # Lookup rows are almost never deleted; an index would only slow writes.
        and fk.referred_table not in lookups
        and (table.fullname, cols) not in UNINDEXED_FKS
    ]
    assert missing == []


def test_filtered_indexes_also_filter_on_sqlite():
    # Without sqlite_where the SQLite tests build an unfiltered index and do
    # not exercise the filter that SQL Server applies.
    one_sided = [
        index.name
        for table in metadata.tables.values()
        for index in table.indexes
        if (index.dialect_options["mssql"]["where"] is None) != (index.dialect_options["sqlite"]["where"] is None)
    ]
    assert one_sided == []
