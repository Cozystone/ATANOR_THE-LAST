"""The evaluator's ground-truth model must match the real filesystem on random actions."""
from atanor_os.eval.oracle import semantic_check

import pytest


@pytest.mark.fs
def test_oracle_matches_reality(tmp_path):
    r = semantic_check(20, seed=3, root=tmp_path / 'sem')
    assert r['ok'] and r['n_mismatch'] == 0, r
    assert min(r['cells'].values()) >= 20, r['cells']
