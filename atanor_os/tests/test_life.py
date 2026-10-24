"""Living core: learns a change from one demonstration, survives a restart, reuses it on new objects with no help,
never acts on an interpretation the person rejected, and keeps what a demonstration left unchanged."""
from pathlib import Path

from atanor_os.agent.life import Mind
from atanor_os.teach.life_teacher import Teacher
from atanor_os.world.fs_world import Workspace


def _home(tmp_path, files):
    ws = Workspace(tmp_path / 'home')
    for name in files:
        (ws.root / name).write_bytes(name.encode())
    return ws


def _do(ws, tmp_path, teacher, task, tid, user=True):
    teacher.begin(task)
    m = Mind(ws, tmp_path / 'mind', tmp_path / 'lab', user=teacher if user else None)
    r = m.do(task['command'], tid)
    return r, teacher.judge(), m


def test_learns_from_one_demonstration_and_reuses_after_restart_without_help(tmp_path):
    ws = _home(tmp_path, ['a.csv', 'b.csv', 'c.txt', 'd.log'])
    t = Teacher(ws)
    r, ok, _ = _do(ws, tmp_path, t, {'command': 'Move the csv files into a folder called box.', 'tool': 'move', 'ext': 'csv', 'dest': 'box'}, 't1')
    assert ok and t.help['demonstrate'] == 1
    (ws.root / 'e.txt').write_bytes(b'e')
    before = dict(t.help)
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Move the txt files into a folder called shelf.', 'tool': 'move', 'ext': 'txt', 'dest': 'shelf'}, 't2', user=False)
    assert ok, r                                                       # a new process, a new extension and folder, nobody to ask
    assert t.help == before
    assert (tmp_path / 'mind' / 'episodes.jsonl').exists() and m.patterns


def test_copy_keeps_the_originals(tmp_path):
    ws = _home(tmp_path, ['a.md', 'b.md', 'c.txt'])
    t = Teacher(ws)
    _do(ws, tmp_path, t, {'command': 'Make a copy of the md files in a folder called spare.', 'tool': 'copy', 'ext': 'md', 'dest': 'spare'}, 't1')
    (ws.root / 'd.md').write_bytes(b'd')
    r, ok, _ = _do(ws, tmp_path, t, {'command': 'Make a copy of the md files in a folder called extra.', 'tool': 'copy', 'ext': 'md', 'dest': 'extra'}, 't2', user=False)
    assert ok and ws.kind('d.md') == 'file' and ws.kind('extra/d.md') == 'file'


class _Refuses(Teacher):
    def check(self, proposal):
        self.help['check'] += 1
        return False

    def demonstrate(self, command, o, dest):
        self.help['demonstrate'] += 1
        return []                                                      # shows nothing useful


def test_never_acts_on_a_rejected_interpretation(tmp_path):
    ws = _home(tmp_path, ['a.csv', 'b.txt'])
    t = Teacher(ws)
    _do(ws, tmp_path, t, {'command': 'Move the csv files into a folder called box.', 'tool': 'move', 'ext': 'csv', 'dest': 'box'}, 't1')
    (ws.root / 'c.csv').write_bytes(b'c')
    r2 = _Refuses(ws)
    r2.begin({'command': 'Shove the csv files into a folder called bag.', 'tool': 'copy', 'ext': 'csv', 'dest': 'bag'})
    m = Mind(ws, tmp_path / 'mind', tmp_path / 'lab', user=r2)
    out = m.do('Shove the csv files into a folder called bag.', 't2')
    assert not out['ok'] and ws.kind('c.csv') == 'file' and ws.kind('bag') == 'absent'
