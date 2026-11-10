"""Seventh body (the bakery oven line) guarantees, world behaviour only: outside changes replay from the seed and are
logged as the outside's, baking steps the crust along its ordered scale by the oven's current dial and refuses where it
cannot act, boxing is irreversible and needs a grant, the tool changes work through the drift, the judge reads a bake
against the state before, and the seventh body's names, words and values never repeat the six earlier bodies'."""
import inspect
import json
import re

from atanor_os.eval import tutor_life
from atanor_os.eval.tutor_life import body_targets, english
from atanor_os.teach.tutor import CrumbSpec, Tutor, symbols, symbols_clime, symbols_crumb, symbols_dye
from atanor_os.world import board_world, clime_world, desk_world, dye_world, view_world
from atanor_os.world.crumb_world import CRUSTS, CrumbWorkspace


def _line(tmp_path, name='c', dials=(('brick', 'gentle'), ('stone', 'fierce'), ('clay', 'unlit'))):
    ws = CrumbWorkspace(tmp_path / name, seed=7)
    spec = ws._read()
    for v, dial in dials:
        spec['ovens'][v] = {'dial': dial}
    ws._write(spec)
    ws.add_loaves({'l0': {'crust': 'doughy', 'grain': 'rye', 'proof': 'risen'}, 'l1': {'crust': 'doughy', 'grain': 'spelt', 'proof': 'slack'},
                   'l2': {'crust': 'golden', 'grain': 'barley', 'proof': 'risen'}, 'l3': {'crust': 'blond', 'grain': 'rye', 'proof': 'risen'}})
    return ws


def test_outside_changes_replay_and_are_logged(tmp_path):
    a, b = _line(tmp_path, 'a'), _line(tmp_path, 'b')
    for _ in range(6):
        a.tick(), b.tick()
    assert a.observe(a.existing()) == b.observe(b.existing())
    st = a.observe(a.existing())
    assert {o for o in st if st[o]['kind'] == 'oven'} == {'o.brick', 'o.stone', 'o.clay'}
    assert not any(st[o]['kind'] == 'loaf' for o in st)                     # old loaves were sold
    rows = [json.loads(l) for l in open(a.root / 'world_log.jsonl', encoding='utf-8')]
    assert all(r['actor'] == 'outside' for r in rows if r['event'] in ('tick', 'arrive'))
    assert any(c[1] == 'sold' for r in rows if r['event'] == 'tick' for c in r['changes'])
    assert any(c[1] == 'dial' for r in rows if r['event'] == 'tick' for c in r['changes'])


def test_a_bake_steps_the_crust_by_the_ovens_dial(tmp_path):
    ws = _line(tmp_path)
    assert ws.execute('bake', ('l0', 'o.brick'), {})['ok']                  # gentle: one step
    st = ws.observe(ws.existing())
    assert st['l0']['crust'] == 'blond' and st['o.brick'] == {'kind': 'oven', 'crust': '-', 'grain': '-', 'proof': 'gentle', 'value': 'brick'}
    assert ws.execute('bake', ('l0', 'o.stone'), {})['ok']                  # fierce: two steps
    assert ws.observe(ws.existing())['l0']['crust'] == 'brown'
    assert ws.execute('bake', ('l0', 'o.stone'), {})['ok']                  # the scale stops at its end
    assert ws.observe(ws.existing())['l0']['crust'] == CRUSTS[-1]
    assert not ws.execute('bake', ('l0', 'o.brick'), {})['ok']              # charred bakes no further
    assert not ws.execute('bake', ('l3', 'o.clay'), {})['ok']               # an unlit oven bakes nothing
    assert not ws.execute('bake', ('l1', 'o.brick'), {})['ok']              # slack dough does not bake
    assert not ws.execute('bake', ('o.brick', 'l3'), {})['ok']              # the oven is the second argument
    assert ws.observe(ws.existing())['l3']['crust'] == 'blond'


def test_prove_knock_and_the_irreversible_box(tmp_path):
    ws = _line(tmp_path)
    assert ws.execute('prove', ('l1',), {})['ok'] and ws.observe(ws.existing())['l1']['proof'] == 'risen'
    assert not ws.execute('prove', ('l1',), {})['ok']                       # already risen
    assert ws.execute('knock', ('l1',), {})['ok'] and ws.observe(ws.existing())['l1']['proof'] == 'slack'
    assert not ws.execute('knock', ('l2',), {})['ok']                       # baked bread is not knocked back
    assert ws.execute('box', ('l0',), {})['blocked']                        # no grant, no box
    assert ws.observe(ws.existing())['l0']['value'] == '-'
    assert ws.execute('box', ('l0',), {'box_loaves': True})['ok']
    assert not ws.execute('bake', ('l0', 'o.brick'), {})['ok']              # boxed for good
    assert not ws.execute('knock', ('l0',), {})['ok']


def test_tool_changes_through_the_drift(tmp_path):
    ws = _line(tmp_path)
    ws.drift = frozenset({'prove_retired', 'knock_retired'})
    assert 'leaven' in ws.tools() and 'punch' in ws.tools()
    assert not ws.execute('prove', ('l1',), {})['ok']
    assert ws.execute('leaven', ('l1',), {})['ok']
    assert not ws.execute('knock', ('l1',), {})['ok']
    assert ws.execute('punch', ('l1',), {})['ok']
    assert CrumbSpec.steps({'tool': 'prove'}, 'l1', ws.drift) == ('leaven', ('l1',))
    lab = ws.lab_copy(tmp_path / 'lab')
    assert lab.observe(lab.existing()) == ws.observe(ws.existing()) and lab.drift == ws.drift


def test_the_judge_reads_a_bake_against_the_state_before(tmp_path):
    ws = _line(tmp_path)
    t = Tutor(ws, CrumbSpec, 1)
    t.start({'kind': 'loaf', 'grain': 'rye'}, {'tool': 'bake', 'second': 'o.brick'})
    assert not t.judge()                                   # nothing baked yet
    ws.execute('bake', ('l0', 'o.brick'), {})
    ws.execute('bake', ('l3', 'o.brick'), {})
    assert t.judge()                                       # each rye loaf one step on
    ws.execute('bake', ('l0', 'o.brick'), {})
    assert not t.judge()                                   # two steps is not what was meant
    t.start({'kind': 'loaf', 'grain': 'barley'}, {'tool': 'bake', 'second': 'o.stone'})
    assert not CrumbSpec.possible(t.act, 'l2', t.before)   # golden in a fierce oven would char: leave it
    assert t.judge()
    ws.execute('bake', ('l2', 'o.stone'), {})
    assert not t.judge()                                   # a charred loaf is harm


def _old_values():
    out = set(board_world.TRAYS.values()) | set(board_world.MARKS) | set(board_world.LEVELS) | set(clime_world.LEVELS)
    out |= set(clime_world.WINGS) | set(clime_world.WEATHER) | set(desk_world.PLACES) | set(desk_world.TAGS)
    out |= set(dye_world.HUES) | set(dye_world.FIBRES) | set(dye_world.VATS) | set(view_world.EXTS) | set(view_world.KEYS)
    out |= set(view_world.GROUPS) | {'card', 'bay', 'message', 'draft', 'task', 'note', 'file', 'dir', 'panel', 'bolt', 'vat',
                                     'fresh', 'stale', 'sealed', 'fixed', 'wet', 'dry', 'unread', 'locked', 'plain', 'open'}
    return out


def test_names_words_and_values_never_repeat_the_six_bodies(tmp_path):
    mine = {w for s in (1,) for w in symbols_crumb(s)}
    assert all(re.fullmatch('[aeiou][bdgkp][bdgkp][aeiou]', w) for w in mine)   # a shape no earlier generator makes
    assert not mine & ({*symbols(1), *symbols_clime(1), *symbols_dye(1)})
    src = inspect.getsource(tutor_life.english)              # every literal of the table, this body's own branches cut out
    src = re.sub(r"if spec\['kind'\] == 'loaf'.*?(?=if spec\['kind'\] == 'bolt')", '', src, flags=re.S)
    src = re.sub(r"if t in \('bake'.*?(?=if t in \('dip')", '', src, flags=re.S)
    words = set(re.findall(r"'([a-z]+)'", src))
    for b in ('board', 'fs', 'view', 'desk', 'clime', 'dye'):
        sels, acts = body_targets(b, 1)
        words |= {w for x in sels for w in english('sel', x)} | {str(w) for x in acts for w in english('act', x)}
    sels, acts = body_targets('crumb', 1)
    said = {w for x in sels for w in english('sel', x)} | {w for x in acts for w in english('act', x)}
    assert not said & words and 'the' not in said and not said & mine
    ws = _line(tmp_path)
    values = {v for a in ws.observe(ws.existing()).values() for v in a.values()} - {'-'}
    assert not values & _old_values()
    assert not values & words
    tools = set(ws.tools()) | {'leaven', 'punch'}
    assert not tools & {'stamp', 'lodge', 'unlodge', 'lift', 'scrap', 'slot', 'brand', 'mkdir', 'copy', 'move', 'delete',
                        'convert', 'zap', 'replicate', 'shove', 'open', 'close', 'filter', 'sort', 'group', 'compare', 'sift',
                        'rank', 'read', 'file', 'tag', 'send', 'complete', 'pin', 'purge', 'shelve', 'mark', 'heat', 'chill',
                        'vent', 'route', 'seal', 'stoke', 'flush', 'dip', 'hang', 'bleach', 'fix', 'peg', 'scour'}
