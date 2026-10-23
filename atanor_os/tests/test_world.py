"""Spec tests for the real workspace adapter (compliance, not learning evidence)."""
import pytest

from atanor_os.world.fs_world import Workspace


def test_bad_paths_rejected(tmp_path):
    ws = Workspace(tmp_path / 'w')
    for bad in ('../x', '/abs', 'a\\b', 'a//b', '', 'a/./b', 'C:x', ' a'):
        with pytest.raises(ValueError):
            ws.path(bad)


def test_tool_semantics_and_observation(tmp_path):
    ws = Workspace(tmp_path / 'w')
    caps = {'destroy': True}
    (ws.root / 'a.txt').write_bytes(b'hello')
    assert ws.execute('mkdir', ('d/e',), caps)['ok'] is False          # parent missing
    assert ws.execute('mkdir', ('d',), caps)['ok'] is True
    assert ws.execute('mkdir', ('d',), caps)['ok'] is False             # exists
    assert ws.execute('copy', ('a.txt', 'd/b.txt'), caps)['ok'] is True
    assert ws.execute('copy', ('a.txt', 'd/b.txt'), caps)['ok'] is False  # no overwrite
    assert ws.execute('copy', ('d', 'x'), caps)['ok'] is False          # source must be a file
    assert ws.execute('move', ('d', 'e'), caps)['ok'] is False          # files only
    assert ws.execute('move', ('d/b.txt', 'c.txt'), caps)['ok'] is True
    assert ws.execute('convert', ('c.txt', 'c.md'), caps)['ok'] is True
    assert ws.execute('convert', ('c.md', 'x.md'), caps)['ok'] is False
    assert ws.execute('convert', ('c.txt', 'x.txt'), caps)['ok'] is False
    r = ws.execute('delete', ('c.md',), {'destroy': False})
    assert r['blocked'] and not r['ok'] and (ws.root / 'c.md').exists()
    assert ws.execute('delete', ('c.md',), caps)['ok'] is True
    assert ws.execute('delete', ('d',), caps)['ok'] is False
    with pytest.raises(ValueError):
        ws.execute('copy', ('a.txt', 'a.txt'), caps)
    st = ws.observe(['zz/q.txt'])
    assert st['zz']['kind'] == 'absent' and st['zz/q.txt']['parent_kind'] == 'absent'
    assert st['a.txt'] == {'kind': 'file', 'ext': 'txt', 'hash': st['c.txt']['hash'], 'parent_kind': 'dir'}
    assert st['d']['kind'] == 'dir' and st['d']['hash'] == '-'
