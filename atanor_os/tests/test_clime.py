"""NEW_BODY_DESIGN.md body guarantees: outside changes replay from the seed and are logged as the outside's, the
weather is observable, effects are relative, a legal action can harm, sealing is irreversible and needs a grant,
and the judge fails a command that harms a bay the person did not expect to change."""
import json

from atanor_os.teach.tutor import ClimeSpec, Tutor, symbols, symbols_clime
from atanor_os.world.clime_world import ClimeWorkspace


def _bays(tmp_path, name='c'):
    ws = ClimeWorkspace(tmp_path / name, seed=7)
    ws.add_bays({'b0': {'heat': 'chill', 'air': 'stale', 'wing': 'north'}, 'b1': {'heat': 'mild', 'air': 'fresh', 'wing': 'south'},
                 'b2': {'heat': 'hot', 'air': 'stale', 'wing': 'east'}})
    return ws


def test_outside_changes_replay_and_are_observable(tmp_path):
    a, b = _bays(tmp_path, 'a'), _bays(tmp_path, 'b')
    for _ in range(4):
        a.tick(), b.tick()
    assert a.observe(a.existing()) == b.observe(b.existing())
    assert a.observe(a.existing())['sky']['heat'] in ('cold', 'fair', 'hot')
    rows = [json.loads(l) for l in open(a.root / 'world_log.jsonl', encoding='utf-8')]
    assert all(r['actor'] == 'outside' for r in rows if r['event'] in ('tick', 'arrive'))


def test_relative_effects_harm_and_the_seal(tmp_path):
    ws = _bays(tmp_path)
    for o in ('b0', 'b1', 'b2'):
        assert ws.execute('heat', (o,), {})['ok']
    st = ws.observe(ws.existing())
    assert (st['b0']['heat'], st['b1']['heat'], st['b2']['heat']) == ('mild', 'warm', 'scorch')   # one step each; hot harms
    assert ws.execute('seal', ('b1',), {})['blocked']                                          # no grant, no seal
    assert ws.execute('seal', ('b1',), {'seal_bays': True})['ok']
    assert not ws.execute('chill', ('b1',), {})['ok']                                          # sealed for good


def test_the_judge_fails_a_harm(tmp_path):
    ws = _bays(tmp_path)
    t = Tutor(ws, ClimeSpec, 1)
    t.start({'kind': 'bay'}, {'tool': 'heat'})
    ws.execute('heat', ('b0',), {})
    ws.execute('heat', ('b1',), {})
    assert t.judge()                                       # the hot bay left as it was
    ws.execute('heat', ('b2',), {})
    assert not t.judge()                                   # the hot bay scorched


def test_generation_2_names_never_repeat_generation_1(tmp_path):
    old = {w for s in range(1, 200) for w in symbols(s)}
    new = {w for s in range(1, 200) for w in symbols_clime(s)}
    assert not old & new
