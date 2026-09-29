"""Generate a new factory project: `wms-sdk init <name>`.

The project gets a copy of the SDK in `wms_sdk/` (only the chosen features),
so it installs nothing from the private repository; `wms-sdk vendor`
replaces that copy with a newer SDK. The factory's own files are generated
once and then belong to the factory. Static files are templates in `template/` (`{{key}}` is
replaced, `__package__` in a path becomes the package name, `dot-` becomes
`.`, `.tmpl` is dropped); `models.py` and `seed.py` depend on the chosen
features, so they are built here. Container files are optional: the files in
CONTAINER_FILES and the text between `<!-- container -->` and
`<!-- /container -->` are left out without `container=True`.
"""

import keyword
import re
import shutil
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from .. import __version__

REPOSITORY = "https://github.com/nextpruek/wms-database-sdk.git"
TODO = "TODO(wms)"
CONTAINER_FILES = {"Containerfile", ".containerignore", ".env.example"}
# The SDK's dependencies per extra, as in pyproject.toml ("" = always).
DEPENDENCIES = {
    "": ["sqlalchemy>=2.0.43,<2.1"],
    "mssql": ["pyodbc>=5.2"],
    "routing": ["networkx>=3.2"],
    "floor_map": ["shapely>=2.0"],
}
# Parts of wms_sdk that only generate projects: not copied into one.
_NOT_COPIED = {"scaffold", "cli.py", "prompt.py", "__main__.py"}
_CONTAINER_BLOCK = re.compile(r"<!-- container -->\n(.*?)<!-- /container -->\n", re.DOTALL)


@dataclass(frozen=True)
class Feature:
    # One line shown in the `wms-sdk init` menu.
    summary: str
    # Import that creates the feature's tables; empty when a class does it.
    enable: str = ""
    # (module, lookup class, seed constant)
    lookups: tuple[tuple[str, str, str], ...] = ()
    # pip extra its helpers need
    extra: str = ""
    # other features it cannot work without
    needs: tuple[str, ...] = ()


FEATURES = {
    "brand": Feature(
        summary="brands, and brand_code on product properties",
        lookups=(("wms_sdk.features.brand", "Brand", "BRANDS"),),
    ),
    "machines": Feature(
        summary="production machines and machine groups",
        enable="import wms_sdk.features.machines  # noqa: F401  (enables the machines feature)",
        lookups=(("wms_sdk.features.machines", "MachineGroup", "MACHINE_GROUPS"),),
    ),
    "floor_map": Feature(
        summary="warehouse drawings and the map builder",
        enable="import wms_sdk.features.floor_map.models  # noqa: F401  (enables floor maps)",
        extra="floor_map",
    ),
    "routing": Feature(
        summary="forklift road network and shortest routes",
        enable="import wms_sdk.features.routing.models  # noqa: F401  (enables forklift routing)",
        extra="routing",
    ),
    "tasks": Feature(
        summary="work orders (forklift, QC, dispatch) and location reservations",
        lookups=(
            ("wms_sdk.features.tasks.models", "TaskType", "TASK_TYPES"),
            ("wms_sdk.features.tasks.models", "TaskStatus", "TASK_STATUSES"),
        ),
    ),
    "map_file": Feature(
        summary="export / import a warehouse as .wmsmap (adds floor_map, routing)",
        needs=("floor_map", "routing"),
    ),
}


class ScaffoldError(Exception):
    """The project cannot be generated as asked (bad name, target not empty...)."""


def resolve_features(names: list[str]) -> list[str]:
    """Validated features plus the ones they need, in FEATURES order."""
    unknown = sorted(set(names) - FEATURES.keys())
    if unknown:
        raise ScaffoldError(f"unknown feature {', '.join(unknown)}; choose from {', '.join(FEATURES)}")
    chosen = set(names)
    for name in names:
        chosen.update(FEATURES[name].needs)
    return [name for name in FEATURES if name in chosen]


def check_package_name(name: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or keyword.iskeyword(name):
        raise ScaffoldError(
            f"{name!r} is not a valid package name: use lowercase letters, digits and _, e.g. factory_x"
        )
    if name in {"wms_sdk", "tests", "migrations"}:
        raise ScaffoldError(f"{name!r} is taken; choose another package name")


def requirements(features: list[str]) -> list[str]:
    """What the copied SDK needs from PyPI for these features."""
    extras = ["", "mssql", *(FEATURES[f].extra for f in features if FEATURES[f].extra)]
    return [line for extra in extras for line in DEPENDENCIES[extra]]


def sdk_files(features: list[str]) -> dict[str, bytes]:
    """Relative path -> bytes of the SDK copy (`wms_sdk/...`) for these
    features: everything but the project generator and unchosen features.
    """
    files = {}
    for source, relative in _walk(resources.files("wms_sdk"), ""):
        parts = relative.split("/")
        if parts[0] in _NOT_COPIED or relative.endswith(".pyc"):
            continue
        if parts[0] == "features" and len(parts) > 1 and parts[1] != "__init__.py":
            if parts[1].removesuffix(".py") not in features:
                continue
        files[f"wms_sdk/{relative}"] = source.read_bytes()
    return files


def render(package: str, features: list[str], container: bool = False) -> dict[str, str]:
    """Relative path -> file content of the project, without the SDK copy."""
    values = {
        "package": package,
        "version": __version__,
        "repository": REPOSITORY.removesuffix(".git"),
        "requirements": "\n".join(requirements(features)),
        "features": ", ".join(features) or "none",
    }
    files = {}
    root = resources.files(__package__) / "template"
    for source, relative in _walk(root, ""):
        parts = [part.replace("__package__", package) for part in relative.split("/")]
        parts = ["." + part.removeprefix("dot-") if part.startswith("dot-") else part for part in parts]
        path = "/".join(parts).removesuffix(".tmpl")
        if path in CONTAINER_FILES and not container:
            continue
        text = _CONTAINER_BLOCK.sub(r"\1" if container else "", source.read_text(encoding="utf-8"))
        files[path] = _fill(text, values, path)
    files[f"{package}/models.py"] = _models_py(package, features)
    files[f"{package}/seed.py"] = _seed_py(package, features)
    return dict(sorted(files.items()))


def create_project(
    package: str,
    target: Path,
    features: list[str],
    *,
    container: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> list[Path]:
    """Write the project, with its copy of the SDK in `wms_sdk/`, into
    `target` and return the files written.

    `container` adds a Containerfile. Refuses a non-empty `target` unless
    `force`, which overwrites the generated files and leaves any other file
    alone. `dry_run` writes nothing.
    """
    check_package_name(package)
    features = resolve_features(features)
    if target.exists() and not target.is_dir():
        raise ScaffoldError(f"{target} is a file")
    if target.is_dir() and any(target.iterdir()) and not force:
        raise ScaffoldError(f"{target} is not empty; use --force to overwrite the generated files")
    written = []
    for relative, content in render(package, features, container).items():
        path = target / relative
        written.append(path)
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            # newline="\n": the same bytes on every OS (the Containerfile runs on Linux).
            path.write_text(content, encoding="utf-8", newline="\n")
    written += _write_sdk(target, features, dry_run)
    return written


def update_sdk(target: Path, add: list[str] = ()) -> tuple[str, list[str], list[Path]]:
    """Replace the project's `wms_sdk/` with this SDK version, keeping the
    project's features and adding `add`. Returns the version replaced, the
    features and the files written.
    """
    old = _copied_version(target)
    kept = [
        name
        for name in FEATURES
        if (target / "wms_sdk" / "features" / name).is_dir()
        or (target / "wms_sdk" / "features" / f"{name}.py").is_file()
    ]
    features = resolve_features([*kept, *add])
    return old, features, _write_sdk(target, features, dry_run=False)


def _copied_version(target: Path) -> str:
    init = target / "wms_sdk" / "__init__.py"
    match = init.is_file() and re.search(r'__version__ = "([^"]+)"', init.read_text(encoding="utf-8"))
    if not match:
        raise ScaffoldError(f"{target} has no copy of the SDK (wms_sdk/__init__.py with __version__)")
    return match.group(1)


def _write_sdk(target: Path, features: list[str], dry_run: bool) -> list[Path]:
    files = sdk_files(features)
    if not dry_run:
        copy = target / "wms_sdk"
        if copy.exists():
            _copied_version(target)  # never delete a folder that is not an SDK copy
            shutil.rmtree(copy)  # drops files the new version no longer has
        for relative, content in files.items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    return [target / relative for relative in files]


def _walk(directory, prefix: str):
    for entry in sorted(directory.iterdir(), key=lambda e: e.name):
        relative = f"{prefix}{entry.name}"
        if entry.is_dir():
            if entry.name != "__pycache__":
                yield from _walk(entry, f"{relative}/")
        else:
            yield entry, relative


def _fill(text: str, values: dict[str, str], path: str) -> str:
    def replace(match: re.Match) -> str:
        key = match.group(1)
        if key not in values:
            raise KeyError(f"{path}: unknown template key {{{{{key}}}}}")
        return values[key]

    return re.sub(r"\{\{(\w+)\}\}", replace, text)


def _models_py(package: str, features: list[str]) -> str:
    enables = [
        "import wms_sdk.metadata  # noqa: F401  (registers the SDK's core tables)",
        *(FEATURES[name].enable for name in features if FEATURES[name].enable),
    ]
    imports = ["from wms_sdk.core.db import Base"]
    if "brand" in features:
        imports.append("from wms_sdk.features.brand import HasBrand")
    if "tasks" in features:
        imports.append("from wms_sdk.features.tasks.models import TaskBase")
    imports += [
        "from wms_sdk.modules.inventory.models import PalletBase",
        "from wms_sdk.modules.master_data.models import ProductPropertiesBase",
        "from wms_sdk.modules.storage.models import LocationPropertiesBase, ZonePropertiesBase",
    ]
    product_bases = "ProductPropertiesBase, HasBrand, Base" if "brand" in features else "ProductPropertiesBase, Base"
    brand_column = " + brand_code" if "brand" in features else ""
    classes = [
        f'''class ProductProperties({product_bases}):
    """One optional row per sku. SDK columns: sku, pcs_per_pallet, kg_per_pcs{brand_column}."""

    # {TODO}: the factory's product properties, e.g.
    #   pcs_per_box: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # and their constraints in extra_table_args (never __table_args__).''',
        f'''class ZoneProperties(ZonePropertiesBase, Base):
    """One optional row per zone. SDK key: (plant_code, warehouse_code, zone_code)."""

    # {TODO}: the factory's zone properties, or leave the class empty.''',
        f'''class LocationProperties(LocationPropertiesBase, Base):
    """One optional row per location. SDK key: location_code."""

    # {TODO}: the factory's location properties (capacity, address ...), or leave it empty.''',
        f'''class Pallet(PalletBase, Base):
    """One row per physical pallet. The SDK fixes its load, location and QC."""

    # {TODO}: the position inside a location, if the factory has one (level, slot ...).''',
    ]
    if "tasks" in features:
        classes.append(
            f'''class Task(TaskBase, Base):
    """All work (forklift, QC, dispatch). The SDK fixes id, task_type_code, status_code."""

    # {TODO}: statuses from TASK_STATUSES in seed.py, e.g.
    #   active_statuses = ("open", "in_progress")
    #   transitions = {{None: {{"open"}}, "open": {{"in_progress", "cancelled"}}, "in_progress": {{"done", "cancelled"}}}}
    # {TODO}: the task's columns (pallet, from / to location ...), and optionally
    #   reservation_columns = ("to_location_code",)'''
        )
    header = f'''"""{package}'s implementation of the SDK interfaces and its enabled features
({", ".join(features) or "none"}).

Factory-only lookups go here too: subclass `Lookup` and `Base`, declare
`code` and `name`, and add the rows in seed.py.
"""
'''
    body = "\n\n\n".join(classes)
    top = "\n".join([*enables, "", *imports])
    return f"{header}\n{top}\n\n\n{body}\n"


def _seed_py(package: str, features: list[str]) -> str:
    lookups = [lookup for name in features for lookup in FEATURES[name].lookups]
    names: dict[str, list[str]] = {
        "wms_sdk.checks": ["verify_factory"],
        "wms_sdk.core.errors": ["LookupNotSeeded"],
        "wms_sdk.modules.events.capture": ["install_capture", "start_operation"],
        "wms_sdk.shared.models.role": ["Role"],
    }
    for module, cls, _ in lookups:
        names.setdefault(module, []).append(cls)
    imports = [f"from {module} import {', '.join(sorted(names[module]))}" for module in sorted(names)]
    constants = "".join(
        f"# {TODO}: rows of {cls}\n{constant}: dict[str, str] = {{}}\n" for _, cls, constant in lookups
    )
    mapping = "".join(
        f"\n    {cls}: {constant}," for cls, constant in [("Role", "ROLES"), *((c, k) for _, c, k in lookups)]
    )
    return f'''"""Lookup rows for {package}. Run once per database, and again after
changing them (`python -m {package}.seed`); call `verify_factory(session)`
at startup.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

{chr(10).join(imports)}

from . import models  # noqa: F401  (registers the factory's tables)
from .roles import RoleCode

# code -> display name
ROLES = {{role.value: role.value for role in RoleCode}}
{constants}
LOOKUPS = {{{mapping}
}}


def seed(session: Session) -> None:
    """Idempotent: re-running updates names instead of failing on duplicates."""
    empty = [model.__tablename__ for model, rows in LOOKUPS.items() if not rows]
    if empty:
        raise LookupNotSeeded(f"no rows for {{', '.join(empty)}}: fill them in {{__name__}}")
    start_operation(session, actor=None)
    for model, rows in LOOKUPS.items():
        for code, name in rows.items():
            session.merge(model(code=code, name=name))
    session.commit()


def main() -> None:
    """Seed the database at WMS_DATABASE_URL, then run the startup check."""
    url = os.environ.get("WMS_DATABASE_URL")
    if not url:
        raise SystemExit("set WMS_DATABASE_URL to the SQLAlchemy URL of the database")
    factory = sessionmaker(create_engine(url))
    install_capture(factory)
    with factory() as session:
        seed(session)
        verify_factory(session)
    print("seeded and verified")


if __name__ == "__main__":
    main()
'''
