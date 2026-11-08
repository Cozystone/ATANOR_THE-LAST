"""SIXTH_BODY_DESIGN.md body guarantees (world behaviour only): outside changes replay from the seed and are logged as
the outside's, a dip changes both its arguments and depends on the vat's state, fixing is irreversible and needs a
grant, the tool changes work through the drift, the judge lets only the dip's own vat change, and the sixth body's
names and words never repeat the five earlier bodies'."""
import json

from atanor_os.eval.tutor_life import body_targets, english
from atanor_os.teach.tutor import DyeSpec, Tutor, symbols, symbols_clime, symbols_dye
from atanor_os.world.dye_world import DyeWorkspace


def _works(tmp_path, name='d', vats=(('oak', 'indigo', 3), ('elm', 'madder', 1), ('yew', 'weld', 8))):
    ws = DyeWorkspace(tmp_path / name, seed=7)
    spec = ws._read()
    for v, hue, stock in vats:
        spec['vats'][v] = {'hue': hue, 'stock': stock}
    ws._write(spec)
    ws.add_bolts({'b0': {'hue': 'ecru', 'fibre': 'wool', 'state': 'dry'}, 'b1': {'hue': 'ecru', 'fibre': 'silk', 'state': 'dry'},
                  'b2': {'hue': 'madder', 'fibre': 'flax', 'state': 'wet'}, 'b3': {'hue': 'weld', 'fibre': 'silk', 'state': 'dry'}})
    return ws


def test_outside_changes_replay_and_are_logged(tmp_path):
    a, b = _works(tmp_path, 'a'), _works(tmp_path, 'b')
    for _ in range(6):
        a.tick(), b.tick()
    assert a.observe(a.existing()) == b.observe(b.existing())
    st = a.observe(a.existing())
    assert {o for o in st if st[o]['kind'] == 'vat'} == {'v.oak', 'v.elm', 'v.yew'}
    assert not any(st[o]['kind'] == 'bolt' for o in st)                     # old bolts were shipped
    rows = [json.loads(l) for l in open(a.root / 'world_log.jsonl', encoding='utf-8')]
    assert all(r['actor'] == 'outside' for r in rows if r['event'] in ('tick', 'arrive'))
    assert any(c[1] == 'shipped' for r in rows if r['event'] == 'tick' for c in r['changes'])


def test_a_dip_changes_both_arguments_and_reads_the_vat(tmp_path):
    ws = _works(tmp_path)
    assert ws.execute('dip', ('b0', 'v.oak'), {})['ok']
    st = ws.observe(ws.existing())
    assert (st['b0']['hue'], st['b0']['state'], st['v.oak']['state']) == ('indigo', 'wet', '2')   # both arguments changed
    assert not ws.execute('dip', ('b0', 'v.oak'), {})['ok']                  # a wet bolt takes no dye
    assert ws.execute('dip', ('b1', 'v.elm'), {})['ok']                      # the result is the dye this vat holds now
    st = ws.observe(ws.existing())
    assert (st['b1']['hue'], st['v.elm']['state']) == ('madder', '0')
    assert not ws.execute('dip', ('b3', 'v.elm'), {})['ok']                  # a spent vat dyes nothing
    assert ws.observe(ws.existing())['b3']['hue'] == 'weld'
    assert not ws.execute('dip', ('v.oak', 'b3'), {})['ok']                  # the vat is the second argument


def test_hang_bleach_and_the_irreversible_fix(tmp_path):
    ws = _works(tmp_path)
    assert ws.execute('hang', ('b2',), {})['ok'] and ws.observe(ws.existing())['b2']['state'] == 'dry'
    assert not ws.execute('bleach', ('b3',), {})['ok']                       # silk does not take the bleach
    assert ws.execute('bleach', ('b2',), {})['ok'] and ws.observe(ws.existing())['b2']['hue'] == 'ecru'
    assert ws.execute('fix', ('b0',), {})['blocked']                         # no grant, no fix
    assert ws.observe(ws.existing())['b0']['value'] == '-'
    assert ws.execute('fix', ('b0',), {'fix_bolts': True})['ok']
    assert not ws.execute('hang', ('b0',), {})['ok']                         # fixed for good
    assert not ws.execute('bleach', ('b0',), {})['ok']


def test_tool_changes_through_the_drift(tmp_path):
    ws = _works(tmp_path)
    ws.drift = frozenset({'hang_retired', 'bleach_retired'})
    assert 'peg' in ws.tools() and 'scour' in ws.tools()
    assert not ws.execute('hang', ('b2',), {})['ok']
    assert ws.execute('peg', ('b2',), {})['ok']
    assert not ws.execute('bleach', ('b2',), {})['ok']
    assert ws.execute('scour', ('b2',), {})['ok']
    assert DyeSpec.steps({'tool': 'hang'}, 'b2', ws.drift) == ('peg', ('b2',))
    lab = ws.lab_copy(tmp_path / 'lab')
    assert lab.observe(lab.existing()) == ws.observe(ws.existing()) and lab.drift == ws.drift


def test_the_judge_lets_only_the_dips_own_vat_change(tmp_path):
    ws = _works(tmp_path)
    t = Tutor(ws, DyeSpec, 1)
    t.start({'kind': 'bolt', 'hue': 'ecru'}, {'tool': 'dip', 'second': 'v.oak'})
    ws.execute('dip', ('b0', 'v.oak'), {})
    ws.execute('dip', ('b1', 'v.oak'), {})
    assert t.judge()                                       # both undyed bolts indigo; the oak vat lost stock
    t.start({'kind': 'bolt', 'fibre': 'silk'}, {'tool': 'dip', 'second': 'v.yew'})
    ws.execute('dip', ('b3', 'v.elm'), {})                 # the wrong vat: a madder bolt and the elm vat changed
    assert not t.judge()


def test_names_and_words_never_repeat_the_five_bodies():
    old = {w for s in range(1, 200) for w in symbols(s)} | {w for s in range(1, 200) for w in symbols_clime(s)}
    new = {w for s in range(1, 200) for w in symbols_dye(s)}
    assert not old & new
    words = set()
    for b in ('board', 'fs', 'view', 'desk', 'clime'):
        for s in range(1, 30):
            sels, acts = body_targets(b, s)
            words |= {w for x in sels for w in english('sel', x)} | {str(w) for x in acts for w in english('act', x)}
    sels, acts = body_targets('dye', 1)
    mine = {w for x in sels for w in english('sel', x)} | {w for x in acts for w in english('act', x)}
    assert not mine & words and 'the' not in mine
    assert not mine & new
