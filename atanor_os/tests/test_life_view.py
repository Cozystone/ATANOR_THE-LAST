"""The same core on the screen body: learns a screen change from one demonstration and reuses it on another panel
and another value with nobody to ask. Nothing in the core names panels, filters or value objects."""
from pathlib import Path

from atanor_os.agent.life import Mind
from atanor_os.teach.life_teacher import ViewTeacher
from atanor_os.world.fs_world import Workspace
from atanor_os.world.view_world import ViewWorkspace


def _screen(tmp_path):
    data = Workspace(tmp_path / 'data')
    for n in ('a.csv', 'b.md', 'c.txt'):
        (data.root / n).write_bytes(n.encode())
    spec = {'p1': {'kind': 'panel', 'filter': 'all', 'sort': 'name', 'group': 'none'},
            'p2': {'kind': 'panel', 'filter': 'all', 'sort': 'name', 'group': 'none'}}
    return ViewWorkspace(tmp_path / 'view', data, spec=spec)


def _do(ws, tmp_path, teacher, task, tid, user=True):
    teacher.begin(task)
    m = Mind(ws, tmp_path / 'mind', tmp_path / 'lab', user=teacher if user else None)
    r = m.do(task['command'], tid)
    return r, teacher.judge(), m


def test_core_has_no_screen_or_file_words():
    src = (Path(__file__).resolve().parents[1] / 'agent' / 'life.py').read_text(encoding='utf-8')
    for word in ("'panel'", "'filter'", "'ext:'", "'key:'", "'grp:'", "'file'", "'dir'", "'hash'", "'ext'"):
        assert word not in src, word


def test_learns_filter_from_one_demonstration_and_reuses_it_alone(tmp_path):
    ws = _screen(tmp_path)
    t = ViewTeacher(ws)
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Filter p1 to csv.', 'tool': 'filter', 'panel': 'p1', 'value': 'ext:csv'}, 't1')
    assert ok, r
    assert t.help.get('demonstrate', 0) >= 1
    before = dict(t.help)
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Filter p2 to md.', 'tool': 'filter', 'panel': 'p2', 'value': 'ext:md'}, 't2', user=False)
    assert ok, (r, dict(m.counts))
    assert t.help == before                                                   # nobody was asked


def test_sort_is_a_different_change_learned_the_same_way(tmp_path):
    ws = _screen(tmp_path)
    t = ViewTeacher(ws)
    _do(ws, tmp_path, t, {'command': 'Filter p1 to csv.', 'tool': 'filter', 'panel': 'p1', 'value': 'ext:csv'}, 't1')
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Sort p2 by size.', 'tool': 'sort', 'panel': 'p2', 'value': 'key:size'}, 't2')
    assert ok, r
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Sort p1 by ext.', 'tool': 'sort', 'panel': 'p1', 'value': 'key:ext'}, 't3', user=False)
    assert ok, (r, dict(m.counts))


def test_after_a_world_change_a_budget_stop_with_no_known_effect_is_a_gap(tmp_path, monkeypatch):
    """Sort retires. On a big screen the plan search would stop on its budget; since no known tool changes the sort any
    more, the core must read this as a gap and experiment (finding the new tool), not give up as if it only ran long."""
    import atanor_os.agent.life as life
    ws = _screen(tmp_path)
    t = ViewTeacher(ws)
    for i, (p, k) in enumerate([('p1', 'size'), ('p2', 'ext'), ('p1', 'name'), ('p2', 'size')]):
        _do(ws, tmp_path, t, {'command': f'Sort {p} by {k}.', 'tool': 'sort', 'panel': p, 'value': f'key:{k}'}, f't{i}')
    real = life.plan

    def big_screen(*a, **kw):
        p, st = real(*a, **kw)
        return (p, {**st, 'stop': 'predictions'}) if not p else (p, st)
    monkeypatch.setattr(life, 'plan', big_screen)
    ws.drift = frozenset({'sort_retired'})
    demos = t.help.get('demonstrate', 0)
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Sort p1 by ext.', 'tool': 'sort', 'panel': 'p1', 'value': 'key:ext'}, 't9')
    assert ok and t.help.get('demonstrate', 0) == demos, (r, dict(m.counts))
    assert m.counts.get('world_changes') == 1 and m.counts.get('lab_actions', 0) > 0, dict(m.counts)


def test_a_second_object_named_by_a_well_used_word_is_not_a_guess(tmp_path):
    """'extension' is never the value's own name; after three confirmed uses naming the sort key, it names it alone."""
    ws = _screen(tmp_path)
    t = ViewTeacher(ws)
    for i, (p, k) in enumerate([('p1', 'size'), ('p2', 'name'), ('p1', 'ext'), ('p2', 'ext'), ('p1', 'ext'), ('p2', 'ext')]):
        word = 'extension' if k == 'ext' else k
        _do(ws, tmp_path, t, {'command': f'Sort {p} by {word}.', 'tool': 'sort', 'panel': p, 'value': f'key:{k}'}, f't{i}')
    _do(ws, tmp_path, t, {'command': 'Sort p1 by size.', 'tool': 'sort', 'panel': 'p1', 'value': 'key:size'}, 't8')
    before = dict(t.help)
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Sort p1 by extension.', 'tool': 'sort', 'panel': 'p1', 'value': 'key:ext'}, 't9', user=False)
    assert ok, (r, dict(m.counts))
    assert t.help == before


def test_how_the_second_object_is_named_is_learned_from_every_use(tmp_path):
    """A demonstration once recorded the sort key as named by meaning only ('by extension'). Later confirmed uses name it
    by its value ('by ext'): that one demonstration must not decide forever how the key can be named."""
    import json
    ws = _screen(tmp_path)
    t = ViewTeacher(ws)
    for i, (p, k) in enumerate([('p1', 'size'), ('p2', 'name'), ('p1', 'ext')]):
        _do(ws, tmp_path, t, {'command': f'Sort {p} by {k}.', 'tool': 'sort', 'panel': p, 'value': f'key:{k}'}, f't{i}')
    for i, (p, k) in enumerate([('p2', 'ext'), ('p1', 'size'), ('p2', 'name')]):
        _do(ws, tmp_path, t, {'command': f'Sort {p} by {k}.', 'tool': 'sort', 'panel': p, 'value': f'key:{k}'}, f'u{i}')
    mp = tmp_path / 'mind' / 'pattern_meta.json'
    meta = json.loads(mp.read_text(encoding='utf-8'))
    for v in meta.values():
        v['D_by'] = None                                    # as if the latest demonstration had said 'by extension'
    mp.write_text(json.dumps(meta), encoding='utf-8')
    before = dict(t.help)
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Sort p1 by ext.', 'tool': 'sort', 'panel': 'p1', 'value': 'key:ext'}, 't9', user=False)
    assert ok, (r, dict(m.counts))
    assert t.help == before


def test_a_well_used_screen_verb_stops_needing_a_check(tmp_path):
    """The panel kind is not a name: after several confirmed filters, 'filter' decides the change and is not re-checked."""
    ws = _screen(tmp_path)
    t = ViewTeacher(ws)
    for i, (p, e) in enumerate([('p1', 'csv'), ('p2', 'md'), ('p1', 'txt'), ('p2', 'csv'), ('p1', 'md')]):
        _do(ws, tmp_path, t, {'command': f'Filter {p} to {e}.', 'tool': 'filter', 'panel': p, 'value': f'ext:{e}'}, f't{i}')
    before = dict(t.help)
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Filter p2 to txt.', 'tool': 'filter', 'panel': 'p2', 'value': 'ext:txt'}, 't9')
    used = {q: t.help[q] - before.get(q, 0) for q in t.help if t.help[q] - before.get(q, 0)}
    assert ok and not used.get('check') and not used.get('point'), used
