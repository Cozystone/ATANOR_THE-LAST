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
    return {'x.json': (at('json'), frozenset({'json'})), 'y.csv': (at('csv'), frozenset({'csv'})), 'z.txt': (at('txt'), frozenset({'txt'}))}


def test_a_long_goal_is_not_mistaken_for_a_knowledge_gap(tmp_path):
    """15 steps are needed but the planner's depth is 12: the core must plan object by object, not experiment."""
    ws = _home(tmp_path, [f'f{i}.txt' for i in range(14)] + ['keep.md'])
    t = Teacher(ws)
    _do(ws, tmp_path, t, {'command': 'Move the md files into a folder called one.', 'tool': 'move', 'ext': 'md', 'dest': 'one'}, 't1')
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Move the txt files into a folder called two.', 'tool': 'move', 'ext': 'txt', 'dest': 'two'}, 't2')
    assert ok, r
    assert m.counts.get('world_gaps', 0) == 0 and m.counts.get('demonstrate_how', 0) == 0, dict(m.counts)


def test_a_long_copy_goal_keeps_each_source_in_its_sub_goal(tmp_path):
    """A copy leaves the source unchanged (it is only a 'keep'); the per-object sub-goal must still contain it."""
    ws = _home(tmp_path, [f'f{i}.txt' for i in range(14)] + ['one.md'])
    t = Teacher(ws)
    _do(ws, tmp_path, t, {'command': 'Copy the md files into a folder called one.', 'tool': 'copy', 'ext': 'md', 'dest': 'one'}, 't1')
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Copy the txt files into a folder called two.', 'tool': 'copy', 'ext': 'txt', 'dest': 'two'}, 't2')
    assert ok, r
    assert m.counts.get('world_gaps', 0) == 0 and m.counts.get('demonstrate_how', 0) == 0, dict(m.counts)


def test_two_word_verbs_sharing_a_word_do_not_look_like_disagreement():
    """'throw away' means one change and 'put away' another; 'away' alone must not make them ambiguous."""
    from atanor_os.agent.life import Lexicon, tokens
    v = _scene_for_lexicon()
    L = Lexicon()
    for _ in range(3):
        L.learn(tokens('throw away the json files'), v, 'DEL', ['x.json'], None)
        L.learn(tokens('put away the csv files into box'), v, 'MOV', ['y.csv'], 'box')
    L.learn(tokens('get rid of the txt files'), v, 'DEL', ['z.txt'], None)
    L.learn(tokens('make a copy of the txt files into bag'), v, 'CPY', ['z.txt'], 'bag')
    r = L.interpret(tokens('throw away the txt files'), v, True)
    assert r['pid'] == 'DEL' and not r['ambiguous'], r
    r = L.interpret(tokens('put away the json files into bin'), v, True)
    assert r['pid'] == 'MOV' and not r['ambiguous'] and r['dest'] == 'bin', r


def test_object_words_do_not_become_change_words_and_two_uses_are_not_decisive():
    """'spreadsheets' used twice with a move must stay an object word; the selection must not fall back to everything."""
    from atanor_os.agent.life import Lexicon, tokens
    v = _scene_for_lexicon()
    L = Lexicon()
    for i in range(3):
        L.learn(tokens('move the csv files into box'), v, 'MOV', ['y.csv'], 'box')
        L.confirmed.update({'move': 1, 'the': 1, 'files': 1})
    L.learn(tokens('move the spreadsheets into bag'), v, 'MOV', ['y.csv'], 'bag')
    L.learn(tokens('move the spreadsheets into bin'), v, 'MOV', ['y.csv'], 'bin')
    L.pointed['spreadsheets'] += 3                                            # pointed at csv files three times: strong object word
    assert L.names_value('spreadsheets')
    r = L.interpret(tokens('move the spreadsheets into crate'), v, True)
    assert r['selected'] == ['y.csv'] and 'spreadsheets' not in {w for w in tokens('move the spreadsheets into crate') if L._share(w, ['MOV'])[1] > 0}, r


def test_irreversible_change_without_literal_naming_is_held_alone(tmp_path):
    """Alone, a delete whose selection rests only on generic meanings ('everything') is not acted on."""
    ws = _home(tmp_path, ['a.log', 'b.log', 'c.txt', 'd.csv'])
    t = Teacher(ws)
    for i, (ext, cmd) in enumerate([('log', 'Discard the log files.'), ('txt', 'Discard the txt files.'), ('csv', 'Discard the csv files.')]):
        _do(ws, tmp_path, t, {'command': cmd, 'tool': 'delete', 'ext': ext, 'dest': None}, f't{i}')
    for n in ('e.log', 'f.md', 'g.json'):
        (ws.root / n).write_bytes(n.encode())
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Discard every logs.', 'tool': 'delete', 'ext': 'log', 'dest': None}, 't9', user=False)
    assert ws.kind('f.md') == 'file' and ws.kind('g.json') == 'file', 'nothing but log files may be deleted'


def test_an_explanation_never_makes_a_meaning_less_specific():
    from atanor_os.agent.life import Lexicon, tokens
    v = _scene_for_lexicon()
    L = Lexicon()
    for _ in range(3):
        L.learn(tokens('zap the markdown files'), v, 'DEL', ['x.json'], None)        # 'markdown' learned with json objects here
    before = set(L.meaning['markdown'])
    assert any("'json'" in a for a in before)
    L.learn_word('markdown', meaning={"('N', 0)"})                                    # an explanation that names no value
    assert L.meaning['markdown'] == before                                             # the specific meaning is kept
    L.learn_word('markdown', meaning={"('N', 0)", "('U', 0, 'a2', 'md')"})            # an explanation that names a value
    assert "('U', 0, 'a2', 'md')" in L.meaning['markdown']


def test_one_bad_use_does_not_poison_a_meaning():
    """A use whose objects share less (here a txt and a json file) must not erase what 'text' has meant every other time."""
    from atanor_os.agent.life import Lexicon, tokens
    v = _scene_for_lexicon()
    L = Lexicon()
    for _ in range(4):
        L.learn(tokens('copy the text files'), v, 'CP', ['z.txt'], None)
    L.learn(tokens('copy the text files'), v, 'CP', ['x.json', 'z.txt'], None)          # one use with mixed objects
    assert "('U', 0, 'a2', 'txt')" in L.meaning['text']
    for _ in range(12):                                                                 # if the word's use really changes, the meaning follows
        L.learn(tokens('copy the text files'), v, 'CP', ['x.json', 'z.txt'], None)
    assert "('U', 0, 'a2', 'txt')" not in L.meaning['text']
    assert Lexicon.from_json(L.to_json()).meaning == L.meaning


def test_a_selection_naming_no_value_is_weak():
    from atanor_os.agent.life import Lexicon, tokens
    v = _scene_for_lexicon()
    L = Lexicon()
    for _ in range(4):
        L.learn(tokens('copy the files'), v, 'CP', ['x.json', 'y.csv', 'z.txt'], None)
    r = L.interpret(tokens('copy the files'), v, False)
    assert r['weak_selection'] and not r['literal'], r


def test_an_unfinished_goal_survives_restarts_and_is_brought_up_with_the_person(tmp_path):
    """Alone, an unknown verb is held and remembered; days later, with the person, the core asks if it is still wanted and does it."""
    ws = _home(tmp_path, ['a.csv', 'b.csv', 'c.txt'])
    t = Teacher(ws)
    task = {'command': 'Relocate the csv files into a folder called box.', 'tool': 'move', 'ext': 'csv', 'dest': 'box'}
    r, ok, m = _do(ws, tmp_path, t, task, 'd1-t0', user=False)
    assert not ok and r['reason'] == 'not understood'
    assert [g['id'] for g in Mind(ws, tmp_path / 'mind', tmp_path / 'lab').pending_goals()] == ['d1-t0']   # after a restart
    t.begin(task)
    m = Mind(ws, tmp_path / 'mind', tmp_path / 'lab', user=t)
    g = m.pending_goals()[0]
    r = m.resume(g)
    assert r is not None and t.judge() and t.help['recall'] == 1, (r, dict(t.help))
    assert Mind(ws, tmp_path / 'mind', tmp_path / 'lab').pending_goals() == []


def test_a_goal_already_done_is_not_redone(tmp_path):
    ws = _home(tmp_path, ['a.csv', 'c.txt'])
    t = Teacher(ws)
    task = {'command': 'Zorp the csv files.', 'tool': 'delete', 'ext': 'csv', 'dest': None}
    _do(ws, tmp_path, t, task, 'd1-t0', user=False)
    (ws.root / 'a.csv').unlink()                                                     # someone else did it meanwhile
    t.begin(task)
    m = Mind(ws, tmp_path / 'mind', tmp_path / 'lab', user=t)
    assert m.resume(m.pending_goals()[0]) is None and ws.kind('c.txt') == 'file'


def test_a_joining_word_is_learned_from_pointed_unions_and_then_used_alone(tmp_path):
    """'the csv and md files' brings two values for one attribute. Nothing tells the core what 'and' does: after the
    person pointed at the union twice, a new pair ('log and txt') is selected as a union with nobody to ask."""
    names = ['a.csv', 'b.csv', 'c.md', 'd.txt', 'e.log', 'f.json']
    ws = _home(tmp_path, names)
    t = Teacher(ws)
    for i, (ext, d) in enumerate([('csv', 'one'), ('md', 'two'), ('txt', 'three'), ('log', 'four')]):
        _do(ws, tmp_path, t, {'command': f'Copy the {ext} files into a folder called {d}.', 'tool': 'copy', 'ext': ext, 'dest': d}, f't{i}')
    for i, (pair, d) in enumerate([(['csv', 'md'], 'five'), (['md', 'json'], 'six')]):
        r, ok, m = _do(ws, tmp_path, t, {'command': f'Copy the {pair[0]} and {pair[1]} files into a folder called {d}.', 'tool': 'copy',
                                        'ext': pair, 'dest': d}, f'u{i}')
        assert ok, (r, dict(m.counts))
    before = dict(t.help)
    r, ok, m = _do(ws, tmp_path, t, {'command': 'Copy the log and txt files into a folder called seven.', 'tool': 'copy',
                                    'ext': ['log', 'txt'], 'dest': 'seven'}, 'v', user=False)
    assert ok, (r, dict(m.counts))
    assert t.help == before


def _scene_more():
    def at(ext, n):
        return frozenset({('N', n), ('U', 0, 'a0', 1), ('U', 0, 'a1', 0), ('U', 0, 'a2', ext)})
    return {f'{c}.{e}': (at(e, 0), frozenset({e})) for c, e in [('a', 'csv'), ('b', 'csv'), ('c', 'md'), ('d', 'log'), ('e', 'txt')]}


def test_a_union_not_yet_read_as_one_does_not_count_against_values():
    from atanor_os.agent.life import Lexicon, tokens
    v = _scene_more()
    L = Lexicon()
    for _ in range(4):
        L.learn(tokens('copy the csv files'), v, 'CP', ['a.csv', 'b.csv'], None)
    hits, opp = L.value_rule
    L.learn(tokens('copy the csv files plus markdown files'), v, 'CP', ['a.csv', 'b.csv', 'c.md'], None)   # 'plus', 'markdown' never heard
    assert L.value_rule[0] - hits == L.value_rule[1] - opp, L.value_rule


def test_a_word_whose_part_cannot_be_told_apart_learns_nothing_from_that_use():
    from atanor_os.agent.life import Lexicon, tokens
    v = _scene_more()
    L = Lexicon()
    for _ in range(4):
        L.learn(tokens('copy the logs'), v, 'CP', ['d.log'], None)
        L.confirmed['logs'] += 1
    before = set(L.meaning['logs'])
    nolog = {o: x for o, x in v.items() if not o.endswith('.log')}                        # no log file at all today
    for _ in range(3):
        L.learn(tokens('copy the csv files plus logs'), nolog, 'CP', ['a.csv', 'b.csv'], None)
    assert L.meaning['logs'] == before


def test_a_reading_that_leaves_named_values_unused_is_held_alone_even_if_reversible():
    from atanor_os.agent.life import Lexicon, tokens
    v = _scene_more()
    L = Lexicon()
    for _ in range(4):
        L.learn(tokens('copy the files'), v, 'CP', sorted(v), None)
    L.value_rule = [1, 5]                                                                 # values are not trusted to restrict yet
    r = L.interpret(tokens('copy the csv files'), v, False)
    assert r['weak_selection'] and not r['support'], r
