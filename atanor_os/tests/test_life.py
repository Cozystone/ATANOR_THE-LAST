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


class _PointsAtLogs(Teacher):
    """Rejects every proposal; points at the log files and shows one deletion."""
    def check(self, proposal):
        self.help['check'] += 1
        return False


def test_after_a_rejection_an_irreversible_change_only_touches_what_was_pointed_at(tmp_path):
    ws = _home(tmp_path, ['a.log', 'b.log', 'c.txt', 'd.csv', 'e.md'])
    t = _PointsAtLogs(ws)
    t.begin({'command': 'Zorp the log files.', 'tool': 'delete', 'ext': 'log', 'dest': None})
    m = Mind(ws, tmp_path / 'mind', tmp_path / 'lab', user=t)
    m.do('Zorp the log files.', 't1')
    assert [p for p in ('c.txt', 'd.csv', 'e.md') if ws.kind(p) != 'file'] == []     # nothing else was deleted


def test_a_tool_that_never_failed_is_trusted_on_a_new_object_after_three_successes(tmp_path):
    from atanor_os.agent.life import WorldModel
    from atanor_os.core.types import Experience
    ws = _home(tmp_path, ['a.txt', 'b.txt', 'c.txt'])
    (ws.root / 'box').mkdir()
    eps = []
    for i, f in enumerate(['a.txt', 'b.txt', 'c.txt']):
        pre = ws.observe([f, f'box/{f}', 'box'])
        ws.execute('copy', (f, f'box/{f}'), {})
        post = ws.observe([f, f'box/{f}', 'box'])
        eps.append(Experience(f'e{i}', 'copy', (f, f'box/{f}'), pre, post, True, False, 0.0, False, 'home'))
    (ws.root / 'd.md').write_bytes(b'd')
    m = WorldModel(eps)
    st = ws.observe(['d.md', 'box/d.md', 'box'])
    post, status = m.predict(st, 'copy', ('d.md', 'box/d.md'))                    # an extension never copied before
    assert status == 'learned' and post['box/d.md']['kind'] == 'file'
    assert WorldModel(eps[:2]).predict(st, 'copy', ('d.md', 'box/d.md'))[1] == 'unknown'   # two successes are not enough


def test_one_use_word_meaning_does_not_constrain_and_informative_word_decides():
    from atanor_os.agent.life import Lexicon, tokens
    v = _scene_for_lexicon()
    L = Lexicon()
    L.learn(tokens('zap the json files'), v, 'DEL', ['x.json'], None)          # 'zap' once, with a json file
    L.learn(tokens('copy the csv files into box'), v, 'CPY', ['y.csv'], 'box')
    L.learn(tokens('copy the json files into bin'), v, 'CPY', ['x.json'], 'bin')
    L.learn(tokens('copy the txt files into bag'), v, 'CPY', ['z.txt'], 'bag')
    r = L.interpret(tokens('zap the csv files'), v, True)
    assert r['selected'] == ['y.csv'], r                                        # 'zap' seen once does not force json
    assert r['pid'] == 'DEL' and not r['ambiguous'], r                          # the one informative word decides


def _scene_for_lexicon():
    def at(ext):
        return frozenset({('N', 0), ('U', 0, 'a0', 1), ('U', 0, 'a1', 0), ('U', 0, 'a2', ext)})
    return {'x.json': (at('json'), 'json'), 'y.csv': (at('csv'), 'csv'), 'z.txt': (at('txt'), 'txt')}


def test_a_long_goal_is_not_mistaken_for_a_knowledge_gap(tmp_path):
    """15 steps are needed but the planner's depth is 12: the core must plan object by object, not experiment."""
    ws = _home(tmp_path, [f'f{i}.txt' for i in range(14)] + ['keep.md'])
    t = Teacher(ws)
    _do(ws, tmp_path, t, {'command': 'Move the md files into a folder called one.', 'tool': 'move', 'ext': 'md', 'dest': 'one'}, 't1')
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Move the txt files into a folder called two.', 'tool': 'move', 'ext': 'txt', 'dest': 'two'}, 't2')
    assert ok, r
    assert m.counts.get('world_gaps', 0) == 0 and m.counts.get('demonstrate_how', 0) == 0, dict(m.counts)
