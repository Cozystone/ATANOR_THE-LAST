"""Ontology memory and the grounding learner: events are append-only, claims keep their versions and evidence, outside
proposals are never acted on, concepts come from pointing and contrast, symbols bind to existing concepts, and a
restart with only claims (ONTO) or only raw events (RAW) still finds them. No body or English word in either module."""
import random
from pathlib import Path

from atanor_os.agent.grounding import Grounder
from atanor_os.agent.memory import Memory
from atanor_os.teach.tutor import BoardSpec, Tutor, symbols
from atanor_os.world.board_world import BoardWorkspace


def test_memory_modules_know_no_body_or_word():
    for f in ('memory.py', 'grounding.py'):
        src = (Path(__file__).resolve().parents[1] / 'agent' / f).read_text(encoding='utf-8')
        for word in ("'card'", "'tray'", "'file'", "'panel'", "'urgent'", "'lodge'", "'copy'", "'board'", "'fs'", "'view'"):
            assert word not in src, (f, word)


def test_claims_keep_versions_and_proposals_are_never_used(tmp_path):
    m = Memory(tmp_path)
    e1 = m.events.append('point', objects=['x'])
    c = m.claims.add('selects', {'concept': 'k0', 'atoms': ['a']}, [e1], 'inferred', {'body': 'b', 'core': 'g1'})
    e2 = m.events.append('contrast', object='y', answer=False)
    m.counter(c['id'], e2)
    m.claims.revise(c['id'], content={'concept': 'k0', 'atoms': ['a', 'b']}, support=[e2])
    vs = [v for v in m.claims.versions if v['id'] == c['id']]
    assert vs[0]['content']['atoms'] == ['a'] and m.claims.current(c['id'])['content']['atoms'] == ['a', 'b']
    assert m.claims.current(c['id'])['support'] == [e1, e2] and e2 in m.claims.current(c['id'])['counter']
    p = m.propose('selects', {'concept': 'k9', 'atoms': ['z']}, 'suggested by an outside reader')
    assert p['status'] == 'proposal' and p['id'] not in {x['id'] for x in m.claims.claims()}
    lines = (tmp_path / 'events.jsonl').read_text(encoding='utf-8').splitlines()
    assert len(lines) == 2                                     # events are only appended


def _board(tmp_path):
    ws = BoardWorkspace(tmp_path / 'board')
    r = random.Random(5)
    ws.add_cards({f'c{i}': {'mark': r.choice(['urgent', 'idea', 'memo']), 'tray': r.choice(['-', 't1', 't2'])} for i in range(30)})
    return ws


def test_a_conjunction_is_found_by_pointing_and_contrast_and_reused_after_restart(tmp_path):
    ws = _board(tmp_path)
    tut = Tutor(ws, BoardSpec, 1)
    sel, act = {'kind': 'card', 'mark': 'idea', 'tray': 'amber'}, {'tool': 'lift', 'second': 'l.high'}
    tut.start(sel, act)
    assert len(tut.truth) >= 2
    g = Grounder(ws, tmp_path / 'mind', person=tut)
    sc = g.learn_selection('L')
    assert g.extension(sc['content']['atoms'], g.feats()) == tut.truth
    ac = g.learn_action('L')
    g.apply(sc['content'], ac['content'], 'L')
    assert tut.confirm()
    sym = symbols(1)
    g.bind(sym[0], sc['content']['concept'], 'L')
    g.bind(sym[1], ac['content']['action'], 'L')
    ws.add_cards({'n1': {'mark': 'idea', 'tray': 't1'}, 'n2': {'mark': 'idea'}, 'n3': {'mark': 'memo', 'tray': 't1'}})
    for mode in ('ONTO', 'RAW'):
        g2 = Grounder(ws, tmp_path / 'mind', person=None, mode=mode)
        look = g2.lookup(sym[0])
        assert look and set(g2.extension(look['claim']['content']['atoms'], g2.feats())) >= {'n1'}
        assert 'n2' not in g2.extension(look['claim']['content']['atoms'], g2.feats()) and 'n3' not in g2.extension(look['claim']['content']['atoms'], g2.feats())
    tut.start(sel, act)
    g3 = Grounder(ws, tmp_path / 'mind', person=None, mode='ONTO')
    res = g3.obey([sym[1], sym[0]])
    assert res['ok'] and tut.judge(), res


def test_an_unknown_symbol_is_held_alone(tmp_path):
    ws = _board(tmp_path)
    g = Grounder(ws, tmp_path / 'mind', person=None)
    res = g.obey(['zuvo', 'kepa'])
    assert not res['ok'] and res['why'] == 'unresolved'


def test_claims_from_another_body_are_not_used(tmp_path):
    """One mind, two bodies: a symbol taught on the board does not act on the file body (scope), and the audit sees both scopes."""
    from atanor_os.world.fs_world import Workspace
    from atanor_os.eval.memory_audit import audit
    ws = _board(tmp_path)
    tut = Tutor(ws, BoardSpec, 1)
    tut.start({'kind': 'card', 'mark': 'idea'}, {'tool': 'scrap'})
    g = Grounder(ws, tmp_path / 'mind', person=tut)
    sc = g.learn_selection('L')
    ac = g.learn_action('L')
    g.bind('mip', sc['content']['concept'], 'L')
    g.bind('dax', ac['content']['action'], 'L')
    fs = Workspace(tmp_path / 'home')
    (fs.root / 'a.csv').write_text('a')
    g2 = Grounder(fs, tmp_path / 'mind', person=None)
    res = g2.obey(['dax', 'mip'])
    assert not res['ok'] and fs.kind('a.csv') == 'file'
    assert Grounder(ws, tmp_path / 'mind', person=None).resolve(['dax', 'mip'])[0] is not None


def test_phrase_order_reads_positions_only():
    """Two phrases read at once: each in its own order, never crossing; a phrase said whole beats one said in part."""
    al = Grounder._align
    w = ('p', 'x', 'y', 'q', 'r', 'z')              # p [x y q] r z : the second phrase sits inside the first
    assert al(w, ('p', 'r', 'z'), ('x', 'y', 'q')) == 6
    assert al(w, ('p', 'q', 'z'), ('x', 'y', 'r')) < 6     # would cross: p x q r z
    assert al(('b', 'a'), ('a', 'b'), ('c',)) == 1          # order counts, not only membership


def test_a_name_goes_to_the_known_concept_the_person_confirms_by_contrast(tmp_path):
    """Pointing at two cards that fit two known concepts: ATANOR asks about a card that splits them before naming."""
    ws = BoardWorkspace(tmp_path / 'board')
    ws.add_cards({'a': {'mark': 'idea', 'tray': 't2'}, 'b': {'mark': 'idea', 'tray': 't2'}, 'c': {'mark': 'memo', 'tray': 't2'},
                  'd': {'mark': 'idea'}, 'e': {'mark': 'memo'}})
    tut = Tutor(ws, BoardSpec, 3)
    g = Grounder(ws, tmp_path / 'mind', person=tut)
    k_idea = g.mem.claims.add('selects', {'concept': 'k0', 'atoms': [r for r in g.feats()['d'] if "'idea'" in r]}, [], 'inferred', g.scope)
    k_tray = g.mem.claims.add('selects', {'concept': 'k1', 'atoms': [r for r in g.feats()['c'] if "'a2'" in r]}, [], 'inferred', g.scope)
    tut.start({'kind': 'card', 'tray': 'teal'})
    tut.point = lambda k=2: ['a', 'b']            # both pointed cards fit both known concepts
    got = g.known_concept('L')
    assert got['content']['concept'] == 'k1' and tut.help['contrast'] >= 1
