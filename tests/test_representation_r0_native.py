import hashlib
import random

from packages.action_core.world import Action
from scripts.representation_r0_eval import build, FIELDS


def test_native_aliasing_is_real_not_setup_label(tmp_path):
    frames, outcomes, stats = [], [], []
    for linked in (False, True):
        body, paths = build(tmp_path, str(linked), b'native-dev-only', linked, 3,
                            random.Random(481))
        frames.append(body.observe().to_dict())
        stats.append(tuple(tuple(getattr(p.stat(), f) for f in FIELDS) for p in paths))
        before = paths[1].read_bytes()
        assert body.step(Action('empty', ('n0',)))
        outcomes.append(paths[1].read_bytes() != before)
        assert paths[0].read_bytes() == b''
        assert body.evidence()['n1']['sha256'] == hashlib.sha256(paths[1].read_bytes()).hexdigest()
    assert frames[0] == frames[1]
    assert outcomes == [False, True]
    assert stats[0][0][2] == stats[0][1][2] == stats[1][0][2] == stats[1][1][2] == 3


def test_second_target_role_and_native_failure_do_not_get_fabricated(tmp_path):
    body, paths = build(tmp_path, 'reverse', b'reverse-dev', True, 2, random.Random(487))
    assert body.step(Action('empty', ('n1',)))
    assert all(p.read_bytes() == b'' for p in paths)
    # A missing source must be an error, not silently copied as a hardlink fallback.
    import os
    import pytest
    with pytest.raises(OSError):
        os.link(tmp_path / 'absent', tmp_path / 'new_link')
