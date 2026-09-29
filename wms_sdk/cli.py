"""`wms-sdk` command line (also `python -m wms_sdk`).

    wms-sdk init                                   # asks: name, then a menu of features
    wms-sdk init factory_x --features brand,tasks --container
    wms-sdk vendor [project]                       # replace the project's SDK copy with this version

Missing arguments are asked for when run in a terminal.
"""

import argparse
import sys
from pathlib import Path

from . import __version__
from .prompt import checkbox
from .scaffold import (
    FEATURES,
    TODO,
    ScaffoldError,
    check_package_name,
    create_project,
    requirements,
    resolve_features,
    update_sdk,
)

CONTAINER = "container"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wms-sdk", description="WMS SDK tools")
    parser.add_argument("--version", action="version", version=f"wms-sdk {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser(
        "init",
        help="generate a new factory project",
        description="Generate a new factory project. In a terminal, a menu asks for the features "
        "unless --features is given.",
    )
    init.add_argument("package", nargs="?", help="Python package name of the factory, e.g. factory_x")
    init.add_argument(
        "--features",
        help=f"comma-separated optional features: {', '.join(FEATURES)} (default: none)",
    )
    init.add_argument("--container", action="store_true", help="add a Containerfile (Podman / Docker)")
    init.add_argument("--dir", type=Path, help="where to create the project (default: ./<package>)")
    init.add_argument("--force", action="store_true", help="overwrite the generated files in a non-empty folder")
    init.add_argument("--dry-run", action="store_true", help="list the files without writing them")
    vendor = commands.add_parser(
        "vendor",
        help="replace a project's SDK copy (wms_sdk/) with this version",
        description=f"Replace the project's wms_sdk/ folder with wms-sdk {__version__}, "
        "keeping the project's features. Files outside wms_sdk/ are not touched.",
    )
    vendor.add_argument("project", nargs="?", type=Path, default=Path("."), help="project folder (default: .)")
    vendor.add_argument("--features", default="", help="comma-separated features to add to the copy")
    args = parser.parse_args(argv)

    try:
        return _init(args) if args.command == "init" else _vendor(args)
    except ScaffoldError as error:
        print(f"wms-sdk: {error}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        # Ctrl+D / Ctrl+Z / Ctrl+C at a question: nothing has been written yet.
        print("\nwms-sdk: cancelled", file=sys.stderr)
        return 1


def _init(args: argparse.Namespace) -> int:
    interactive = sys.stdin.isatty()
    package = args.package
    if package is None:
        if not interactive:
            raise ScaffoldError("give the package name, e.g. wms-sdk init factory_x")
        package = _ask("Package name (e.g. factory_x): ", check_package_name)
    check_package_name(package)

    container = args.container
    if args.features is not None:
        features = _split(args.features)
    elif interactive:
        items = [(name, feature.summary) for name, feature in FEATURES.items()]
        items.append((CONTAINER, "Containerfile to build an image (Podman / Docker)"))
        chosen = checkbox("Optional features", items, selected={CONTAINER} if container else set())
        container = CONTAINER in chosen
        features = [name for name in chosen if name != CONTAINER]
    else:
        features = []
    features = resolve_features(features)

    target = args.dir or Path(package)
    written = create_project(
        package, target, features, container=container, force=args.force, dry_run=args.dry_run
    )
    names = [path.relative_to(target).as_posix() for path in written]
    own = [name for name in names if not name.startswith("wms_sdk/")]
    copied = len(names) - len(own)
    if args.dry_run:
        print(f"Would create in {target}:")
        for name in own:
            print(f"  {name}")
        print(f"  wms_sdk/ ({copied} files, copy of wms-sdk {__version__})")
        return 0

    print(
        f"Created {target}: {len(own)} files + wms_sdk/ (copy of wms-sdk {__version__}, {copied} files)"
    )
    print(f"Features: {', '.join(features) or 'none'}. Container: {'yes' if container else 'no'}.")
    print()
    print("Next:")
    print(f"  cd {target}")
    print(f"  1. Fill in every {TODO}: {package}/models.py, roles.py, seed.py")
    print("  2. pip install -r requirements-dev.txt, then python -m pytest")
    print(f"  3. Database{' and container image' if container else ''}: README.md")
    return 0


def _vendor(args: argparse.Namespace) -> int:
    old, features, written = update_sdk(args.project, _split(args.features))
    print(f"wms_sdk/ in {args.project}: {old} -> {__version__} ({len(written)} files)")
    print(f"Features: {', '.join(features) or 'none'}")
    if args.features:
        print("New features: enable them in models.py and seed their lookups (see the factory guide).")
    print()
    print("requirements.txt must include:")
    for line in requirements(features):
        print(f"  {line}")
    print()
    print("Then read the release notes and create a migration (README.md, section 3).")
    return 0


def _split(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def _ask(prompt: str, check) -> str:
    """Ask until `check(answer)` does not raise ScaffoldError."""
    while True:
        answer = input(prompt).strip()
        try:
            check(answer)
        except ScaffoldError as error:
            print(f"  {error}")
            continue
        return answer
