import pytest
from packages.action_core.observation_scope import ancestor_closed_paths


def test_closure_preserves_handles_and_input():
    paths=['a/b/c','flat','a/d']
    assert ancestor_closed_paths(paths)==paths+['a','a/b']
    assert paths==['a/b/c','flat','a/d']
    assert ancestor_closed_paths(['a','a/b'])==['a','a/b']


def test_invalid_or_aliased_paths_rejected():
    for paths in [['../outside'],['a','A']]:
        with pytest.raises(ValueError):ancestor_closed_paths(paths)
