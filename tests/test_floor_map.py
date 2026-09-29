from decimal import Decimal

import pytest

from wms_sdk.features.floor_map.geometry import polygon_error, to_clip_path

D = Decimal
SQUARE = [(D(0), D(0)), (D(1), D(0)), (D(1), D(1)), (D(0), D(1))]


def test_valid_outlines():
    assert polygon_error([]) is None  # full rectangle
    assert polygon_error(SQUARE) is None
    assert polygon_error([(D(0), D(0)), (D("0.8"), D("0.1")), (D(1), D(1)), (D("0.1"), D("0.9"))]) is None


@pytest.mark.parametrize(
    "points",
    [
        SQUARE[:3],
        [SQUARE[0], SQUARE[0], SQUARE[2], SQUARE[3]],
        [SQUARE[0], SQUARE[2], SQUARE[1], SQUARE[3]],  # bow tie: edges cross
        [(D(0), D(0)), (D("0.5"), D(0)), (D(1), D(0)), (D("0.2"), D(0))],  # all on one line
        [(D(0), D(0)), (D(1), D(0)), (D("0.5"), D("0.5")), (D("0.5"), D(0))],  # edges touch
    ],
    ids=["three-points", "repeated-corner", "crossing-edges", "no-area", "touching-edges"],
)
def test_invalid_outlines(points):
    assert polygon_error(points) is not None


def test_clip_path():
    assert to_clip_path([]) is None
    assert to_clip_path(SQUARE) == "polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%)"
