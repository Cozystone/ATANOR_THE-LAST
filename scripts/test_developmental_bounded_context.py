from scripts.developmental_bounded_context import supported
import pytest


def test_empty_history_is_not_support():
    assert not supported((1,), [])


def test_interpolation_and_boundary():
    assert supported((1, 2), [(0, 2), (2, 2)])
    assert supported((0, 2), [(0, 2), (2, 2)])


def test_one_unseen_dimension_denies():
    assert not supported((1, 3), [(0, 2), (2, 2)])


def test_width_mismatch():
    with pytest.raises(ValueError): supported((1,2), [(1,)])
