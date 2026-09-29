"""The examples in examples/ are documentation: they must keep running."""

import os
import subprocess
import sys

import pytest

from examples.cookbook import dispatch_tasks, map_and_routing, pallet_lifecycle, share_map


@pytest.mark.parametrize(
    "recipe, expected",
    [
        (pallet_lifecycle, ["P-0001: shipped from tl-w1-1-0101", "P-0002: refused", "outbox waiting to send: ['sap']"]),
        (map_and_routing, ["unreachable vertices: none", "nearest free location: tl-w1-1-0101 (17.80 m"]),
        (dispatch_tasks, ["SO-101: refused", "after task 1 is done", "task 2: P-0002 -> tl-w1-1-0203 L2 (open)"]),
        (share_map, ["imported C221/W1: 6 locations", "dock -> tl-w1-1-0101 17.80 m", "second import refused"]),
    ],
    ids=["pallet_lifecycle", "map_and_routing", "dispatch_tasks", "share_map"],
)
def test_cookbook_recipe_runs(recipe, expected, capsys):
    recipe.main()
    output = capsys.readouterr().out
    for text in expected:
        assert text in output


def test_minimal_factory_runs():
    # Its own process: a process can hold only one implementation per interface.
    result = subprocess.run(
        [sys.executable, "-m", "examples.minimal_factory.main"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, result.stderr
    assert "factory verified" in result.stdout
    assert "stock: A-01 SKU-1 qty=40" in result.stdout
