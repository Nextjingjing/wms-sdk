"""`wms-sdk init` / `vendor`: the generated project works once its TODOs are
filled, on its own copy of the SDK.

The generated project runs in its own process (one implementation per
interface per process), without this checkout on the path.
"""

import io
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.engine import make_url

from wms_sdk import __version__
from wms_sdk.cli import main
from wms_sdk.prompt import DOWN, ENTER, SPACE, UP, checkbox
from wms_sdk.scaffold import CONTAINER_FILES, DEPENDENCIES, FEATURES, create_project
from wms_sdk.testing import MSSQL_URL_VARIABLE

SDK_ROOT = Path(__file__).resolve().parents[1]


def run(project: Path, *args: str, **env: str) -> subprocess.CompletedProcess:
    # No PYTHONPATH: `import wms_sdk` must find the project's own copy.
    base = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    return subprocess.run(
        [sys.executable, *args],
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**base, "PYTHONIOENCODING": "utf-8", **env},
    )


def own_files(project: Path) -> dict[str, str]:
    """The project's files, without its SDK copy."""
    return {
        path.relative_to(project).as_posix(): path.read_text(encoding="utf-8")
        for path in project.rglob("*")
        if path.is_file() and path.relative_to(project).parts[0] != "wms_sdk"
    }


def fill_todos(project: Path, package: str) -> None:
    """What a factory does after init: at least one role and one row per lookup."""
    roles = project / package / "roles.py"
    roles.write_text(roles.read_text(encoding="utf-8") + '    FORKLIFT = "Forklift"\n', encoding="utf-8")
    seed = project / package / "seed.py"
    text = re.sub(r"(\w+): dict\[str, str\] = \{\}", r'\1: dict[str, str] = {"X": "X"}', seed.read_text(encoding="utf-8"))
    seed.write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    "features, empty",
    [([], "roles"), (list(FEATURES), "roles, brands, machine_groups, task_types, task_statuses")],
    ids=["no-features", "all-features"],
)
def test_generated_project_passes_once_todos_are_filled(tmp_path, features, empty):
    project = tmp_path / "factory_x"
    create_project("factory_x", project, features)

    result = run(project, "-m", "pytest", "-q", "-p", "no:cacheprovider")
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"no rows for {empty}: fill them in factory_x.seed" in result.stdout

    fill_todos(project, "factory_x")
    result = run(project, "-m", "pytest", "-q", "-p", "no:cacheprovider")
    assert result.returncode == 0, result.stdout + result.stderr

    result = run(project, "-c", "import wms_sdk; print(wms_sdk.__file__)")
    assert Path(result.stdout.strip()) == project / "wms_sdk" / "__init__.py"


def test_project_has_the_sdk_copy_and_its_dependencies(tmp_path):
    create_project("factory_x", tmp_path, ["map_file"])
    requirements = (tmp_path / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert requirements[1:5] == ["sqlalchemy>=2.0.43,<2.1", "pyodbc>=5.2", "shapely>=2.0", "networkx>=3.2"]
    assert not any("git+" in line for line in requirements)

    copy = tmp_path / "wms_sdk"
    assert f'__version__ = "{__version__}"' in (copy / "__init__.py").read_text(encoding="utf-8")
    assert (copy / "features" / "floor_map").is_dir() and (copy / "features" / "map_file.py").is_file()
    assert not (copy / "features" / "tasks").exists() and not (copy / "features" / "brand.py").exists()
    assert not (copy / "scaffold").exists() and not (copy / "cli.py").exists()
    assert not list(copy.rglob("__pycache__"))

    models = (tmp_path / "factory_x" / "models.py").read_text(encoding="utf-8")
    assert "import wms_sdk.features.floor_map.models" in models
    assert "TaskBase" not in models and "HasBrand" not in models
    assert "{{" not in "".join(own_files(tmp_path).values())


def test_dependencies_match_pyproject():
    project = tomllib.loads((SDK_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert DEPENDENCIES == {"": project["dependencies"], **project["optional-dependencies"]}


def test_vendor_replaces_the_copy_and_keeps_features(tmp_path, capsys):
    create_project("factory_x", tmp_path, ["tasks"])
    init = tmp_path / "wms_sdk" / "__init__.py"
    init.write_text(init.read_text(encoding="utf-8").replace(__version__, "0.0.1"), encoding="utf-8")
    (tmp_path / "wms_sdk" / "gone.py").write_text("# removed in the new version\n")
    (tmp_path / "factory_x" / "mine.py").write_text("# the factory's code\n")

    assert main(["vendor", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert f"0.0.1 -> {__version__}" in output and "Features: tasks" in output
    assert f'__version__ = "{__version__}"' in init.read_text(encoding="utf-8")
    assert not (tmp_path / "wms_sdk" / "gone.py").exists()
    assert (tmp_path / "wms_sdk" / "features" / "tasks").is_dir()
    assert (tmp_path / "factory_x" / "mine.py").exists()

    assert main(["vendor", str(tmp_path), "--features", "map_file"]) == 0
    assert "Features: floor_map, routing, tasks, map_file" in capsys.readouterr().out
    assert (tmp_path / "wms_sdk" / "features" / "map_file.py").is_file()


def test_vendor_refuses_a_folder_without_a_copy(tmp_path, capsys):
    (tmp_path / "wms_sdk").mkdir()
    (tmp_path / "wms_sdk" / "notes.txt").write_text("not the SDK")
    assert main(["vendor", str(tmp_path)]) == 1
    assert "has no copy of the SDK" in capsys.readouterr().err
    assert (tmp_path / "wms_sdk" / "notes.txt").exists()


def test_alembic_env_matches_the_reference_factory(tmp_path):
    create_project("factory_x", tmp_path, [])
    generated = (tmp_path / "migrations" / "env.py").read_text(encoding="utf-8")
    example = (SDK_ROOT / "examples" / "reference_factory" / "migrations" / "env.py").read_text(encoding="utf-8")
    start = "config = context.config"
    assert generated[generated.index(start):] == example[example.index(start):]


def test_container_files_only_when_asked(tmp_path):
    create_project("factory_x", tmp_path / "plain", [])
    create_project("factory_x", tmp_path / "boxed", [], container=True)
    for name in CONTAINER_FILES:
        assert not (tmp_path / "plain" / name).exists()
        assert (tmp_path / "boxed" / name).exists()
    plain = "".join(own_files(tmp_path / "plain").values())
    boxed = (tmp_path / "boxed" / "README.md").read_text(encoding="utf-8")
    assert "Containerfile" not in plain and "podman" not in plain
    assert "## 4. Container image" in boxed
    assert "<!--" not in plain + boxed


def test_cli_dry_run_writes_nothing(tmp_path, capsys):
    assert main(["init", "factory_x", "--dir", str(tmp_path / "x"), "--dry-run", "--container"]) == 0
    assert not (tmp_path / "x").exists()
    output = capsys.readouterr().out
    assert "Containerfile" in output and "factory_x/seed.py" in output


def keys(*sequence):
    pressed = iter(sequence)
    return lambda: next(pressed)


def test_checkbox_moves_ticks_and_wraps():
    items = [("a", "first"), ("b", "second"), ("c", "third")]
    out = io.StringIO()
    # down, tick b; up twice wraps to c, tick c; tick c again = untick; tick again.
    chosen = checkbox(
        "Pick", items, read_key=keys(DOWN, SPACE, UP, UP, SPACE, SPACE, SPACE, ENTER), out=out
    )
    assert chosen == ["b", "c"]
    assert checkbox("Pick", items, selected={"a"}, read_key=keys(ENTER), out=out) == ["a"]
    assert "> [x] b  second" in out.getvalue()


def test_cli_menu_in_a_terminal(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "factory_x")
    # Menu order: brand, machines, floor_map, routing, tasks, map_file, container.
    monkeypatch.setattr("wms_sdk.prompt._read_key", keys(SPACE, UP, SPACE, UP, UP, SPACE, ENTER))
    assert main(["init", "--dir", str(tmp_path)]) == 0
    assert "Features: brand, tasks. Container: yes." in capsys.readouterr().out
    assert "class Task(TaskBase, Base)" in (tmp_path / "factory_x" / "models.py").read_text(encoding="utf-8")
    assert (tmp_path / "Containerfile").exists()


@pytest.mark.parametrize("where", ["name", "menu"])
def test_cli_cancelled_question_writes_nothing(tmp_path, monkeypatch, capsys, where):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def cancel(*args):
        raise EOFError if where == "name" else KeyboardInterrupt

    monkeypatch.setattr("builtins.input", cancel)
    monkeypatch.setattr("wms_sdk.prompt._read_key", cancel)
    args = ["init"] if where == "name" else ["init", "factory_x"]
    assert main([*args, "--dir", str(tmp_path / "x")]) == 1
    assert "cancelled" in capsys.readouterr().err
    assert not (tmp_path / "x").exists()


def test_cli_refuses_a_non_empty_folder_unless_forced(tmp_path, capsys):
    (tmp_path / "notes.txt").write_text("keep me")
    assert main(["init", "factory_x", "--dir", str(tmp_path)]) == 1
    assert "is not empty" in capsys.readouterr().err

    assert main(["init", "factory_x", "--dir", str(tmp_path), "--force"]) == 0
    assert (tmp_path / "notes.txt").read_text() == "keep me"
    assert (tmp_path / "factory_x" / "models.py").exists()


@pytest.mark.parametrize(
    "args, message",
    [
        (["init", "Factory-X"], "not a valid package name"),
        (["init", "wms_sdk"], "is taken"),
        (["init", "factory_x", "--features", "brand,forklifts"], "unknown feature forklifts"),
    ],
)
def test_cli_rejects_bad_input(tmp_path, capsys, args, message):
    assert main([*args, "--dir", str(tmp_path / "x")]) == 1
    assert message in capsys.readouterr().err
    assert not (tmp_path / "x").exists()


@pytest.mark.skipif(
    not os.environ.get(MSSQL_URL_VARIABLE), reason=f"needs SQL Server: set {MSSQL_URL_VARIABLE}"
)
def test_generated_migrations_build_the_schema_on_sql_server(tmp_path):
    from wms_sdk.testing.mssql import create_mssql_test_engine

    project = tmp_path / "factory_x"
    create_project("factory_x", project, list(FEATURES))
    fill_todos(project, "factory_x")
    url = make_url(os.environ[MSSQL_URL_VARIABLE]).set(database="wms_test_scaffold")
    # Empty, without the messaging schema: migration 0001 must create it.
    engine = create_mssql_test_engine(url, schemas=())
    database = url.render_as_string(hide_password=False)

    for args in [
        ["-m", "alembic", "upgrade", "head"],
        ["-m", "alembic", "revision", "--autogenerate", "-m", "initial schema"],
        ["-m", "alembic", "upgrade", "head"],
        ["-m", "alembic", "check"],
        ["-m", "factory_x.seed"],
        ["-m", "alembic", "downgrade", "base"],
    ]:
        result = run(project, *args, WMS_DATABASE_URL=database)
        assert result.returncode == 0, f"{args}: {result.stdout}{result.stderr}"

    inspector = inspect(engine)
    assert inspector.get_table_names() == ["alembic_version"]
    assert "messaging" not in inspector.get_schema_names()
    engine.dispose()
