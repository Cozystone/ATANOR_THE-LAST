"""Eighth body (the bike repair shop) guarantees, world behaviour only: outside changes replay from the seed and are
logged as the outside's, inflating steps the pressure along its ordered scale by the pump's current gauge and refuses
where it cannot act, releasing steps it down, bleeding refuses on steel frames, delivering is irreversible and needs a
grant, the tool changes work through the drift, the judge reads a pressure change against the state before, and the
eighth body's names, words, values and tools never repeat the seven earlier bodies'."""
import inspect
import json
import re

from atanor_os.eval import tutor_life
from atanor_os.eval.tutor_life import DRIFT, body_targets, english, spoke_inflow
from atanor_os.teach.tutor import SpokeSpec, Tutor, symbols, symbols_clime, symbols_crumb, symbols_dye, symbols_spoke
from atanor_os.world import board_world, clime_world, crumb_world, desk_world, dye_world, view_world
from atanor_os.world.raw_obs import raw_attrs, to_human
from atanor_os.world.spoke_world import PRESSURES, SpokeWorkspace


def _shop(tmp_path, name='s', gauges=(('track', 'trickle'), ('foot', 'gust'), ('mini', 'shut'))):
    ws = SpokeWorkspace(tmp_path / name, seed=7)
    spec = ws._read()
    for v, g in gauges:
        spec['pumps'][v] = {'gauge': g}
    ws._write(spec)
    ws.add_bikes({'b0': {'pressure': 'limp', 'frame': 'alloy', 'brake': 'spongy'}, 'b1': {'pressure': 'soft', 'frame': 'steel', 'brake': 'spongy'},
                  'b2': {'pressure': 'firm', 'frame': 'bamboo', 'brake': 'sharp'}, 'b3': {'pressure': 'soft', 'frame': 'alloy', 'brake': 'sharp'}})
    return ws


def test_outside_changes_replay_and_are_logged(tmp_path):
    a, b = _shop(tmp_path, 'a'), _shop(tmp_path, 'b')
    for _ in range(6):
        a.tick(), b.tick()
    assert a.observe(a.existing()) == b.observe(b.existing())
    st = a.observe(a.existing())
    assert {o for o in st if st[o]['kind'] == 'pump'} == {'p.track', 'p.foot', 'p.mini'}
    assert not any(st[o]['kind'] == 'bike' for o in st)                     # old bikes were collected
    rows = [json.loads(l) for l in open(a.root / 'world_log.jsonl', encoding='utf-8')]
    assert all(r['actor'] == 'outside' for r in rows if r['event'] in ('tick', 'arrive'))
    assert any(c[1] == 'collected' for r in rows if r['event'] == 'tick' for c in r['changes'])
    assert any(c[1] == 'gauge' for r in rows if r['event'] == 'tick' for c in r['changes'])


def test_inflate_steps_the_pressure_by_the_pumps_gauge(tmp_path):
    ws = _shop(tmp_path)
    assert ws.execute('inflate', ('b0', 'p.track'), {})['ok']               # trickle: one step
    st = ws.observe(ws.existing())
    assert st['b0']['pressure'] == 'soft'
    assert st['p.track'] == {'kind': 'pump', 'pressure': 'trickle', 'frame': '-', 'brake': '-', 'value': 'track'}
    assert ws.execute('inflate', ('b0', 'p.foot'), {})['ok']                # gust: two steps
    assert ws.observe(ws.existing())['b0']['pressure'] == 'taut'
    assert ws.execute('inflate', ('b0', 'p.foot'), {})['ok']                # the scale stops at its end
    assert ws.observe(ws.existing())['b0']['pressure'] == PRESSURES[-1]
    assert not ws.execute('inflate', ('b0', 'p.track'), {})['ok']           # a burst tyre takes no air
    assert not ws.execute('release', ('b0',), {})['ok']                     # and gives none
    assert not ws.execute('inflate', ('b3', 'p.mini'), {})['ok']            # a shut pump inflates nothing
    assert not ws.execute('inflate', ('p.track', 'b3'), {})['ok']           # the pump is the second argument
    assert ws.observe(ws.existing())['b3']['pressure'] == 'soft'


def test_release_bleed_and_the_irreversible_delivery(tmp_path):
    ws = _shop(tmp_path)
    assert ws.execute('release', ('b2',), {})['ok'] and ws.observe(ws.existing())['b2']['pressure'] == 'soft'
    assert ws.execute('release', ('b2',), {})['ok'] and ws.observe(ws.existing())['b2']['pressure'] == 'limp'
    assert not ws.execute('release', ('b2',), {})['ok']                     # limp gives no more
    assert ws.execute('bleed', ('b0',), {})['ok'] and ws.observe(ws.existing())['b0']['brake'] == 'sharp'
    assert not ws.execute('bleed', ('b0',), {})['ok']                       # already sharp
    assert not ws.execute('bleed', ('b1',), {})['ok']                       # a steel frame's rim brakes are not bled
    assert ws.observe(ws.existing())['b1']['brake'] == 'spongy'
    assert ws.execute('deliver', ('b3',), {})['blocked']                    # no grant, no delivery
    assert ws.observe(ws.existing())['b3']['value'] == '-'
    assert ws.execute('deliver', ('b3',), {'deliver_bikes': True})['ok']
    assert ws.observe(ws.existing())['b3']['value'] == 'delivered'
    assert not ws.execute('inflate', ('b3', 'p.track'), {})['ok']           # delivered for good
    assert not ws.execute('release', ('b3',), {})['ok']


def test_tool_changes_through_the_drift(tmp_path):
    ws = _shop(tmp_path)
    ws.drift = frozenset({DRIFT['spoke'], 'release_retired'})
    assert 'prime' in ws.tools() and 'drop' in ws.tools()
    assert not ws.execute('bleed', ('b0',), {})['ok']
    assert ws.execute('prime', ('b0',), {})['ok']
    assert not ws.execute('release', ('b1',), {})['ok']
    assert ws.execute('drop', ('b1',), {})['ok'] and ws.observe(ws.existing())['b1']['pressure'] == 'limp'
    assert SpokeSpec.steps({'tool': 'bleed'}, 'b0', ws.drift) == ('prime', ('b0',))
    assert SpokeSpec.steps({'tool': 'release'}, 'b0', ws.drift) == ('drop', ('b0',))
    lab = ws.lab_copy(tmp_path / 'lab')
    assert lab.observe(lab.existing()) == ws.observe(ws.existing()) and lab.drift == ws.drift


def test_the_judge_reads_a_pressure_change_against_the_state_before(tmp_path):
    ws = _shop(tmp_path)
    t = Tutor(ws, SpokeSpec, 1)
    t.start({'kind': 'bike', 'frame': 'alloy'}, {'tool': 'inflate', 'second': 'p.track'})
    assert not t.judge()                                   # nothing inflated yet
    ws.execute('inflate', ('b0', 'p.track'), {})
    ws.execute('inflate', ('b3', 'p.track'), {})
    assert t.judge()                                       # each alloy bike one step up
    ws.execute('inflate', ('b0', 'p.track'), {})
    assert not t.judge()                                   # two steps is not what was meant
    t.start({'kind': 'bike', 'frame': 'bamboo'}, {'tool': 'inflate', 'second': 'p.foot'})
    assert not SpokeSpec.possible(t.act, 'b2', t.before)   # firm with a gust would burst: leave it
    assert t.judge()
    ws.execute('inflate', ('b2', 'p.foot'), {})
    assert not t.judge()                                   # a burst tyre is harm
    t.start({'kind': 'bike', 'frame': 'steel'}, {'tool': 'release'})
    ws.execute('release', ('b1',), {})
    assert t.judge()


def test_raw_observation_round_trip(tmp_path):
    ws = _shop(tmp_path)
    for o, a in ws.observe(ws.existing()).items():
        assert to_human('spoke', raw_attrs('spoke', a), {}) == a


def test_inflow_brings_every_frame_each_day():
    for d in range(100, 140):
        assert {b['frame'] for b in spoke_inflow(1, d).values()} == {'steel', 'alloy', 'bamboo'}


def _old_values():
    out = set(board_world.TRAYS.values()) | set(board_world.MARKS) | set(board_world.LEVELS) | set(clime_world.LEVELS)
    out |= set(clime_world.WINGS) | set(clime_world.WEATHER) | set(desk_world.PLACES) | set(desk_world.TAGS)
    out |= set(dye_world.HUES) | set(dye_world.FIBRES) | set(dye_world.VATS) | set(view_world.EXTS) | set(view_world.KEYS)
    out |= set(view_world.GROUPS) | set(crumb_world.CRUSTS) | set(crumb_world.GRAINS) | set(crumb_world.DIALS)
    out |= set(crumb_world.OVENS) | {'card', 'bay', 'message', 'draft', 'task', 'note', 'file', 'dir', 'panel', 'bolt', 'vat',
                                     'loaf', 'oven', 'fresh', 'stale', 'sealed', 'fixed', 'wet', 'dry', 'unread', 'locked',
                                     'plain', 'open', 'boxed', 'slack', 'risen'}
    return out


def test_names_words_values_and_tools_never_repeat_the_seven_bodies(tmp_path):
    mine = {w for s in range(1, 200) for w in symbols_spoke(s)}
    assert all(re.fullmatch('[bdgkpt][lr][aeiou][fvxz]', w) for w in mine)     # a shape no earlier generator makes
    old = {w for s in range(1, 200) for g in (symbols, symbols_clime, symbols_dye, symbols_crumb) for w in g(s)}
    assert not mine & old
    src = inspect.getsource(tutor_life.english)              # every literal of the table, this body's own branches cut out
    src = re.sub(r"if spec\['kind'\] == 'bike'.*?(?=if spec\['kind'\] == 'loaf')", '', src, flags=re.S)
    src = re.sub(r"if t in \('inflate'.*?(?=if t in \('bake')", '', src, flags=re.S)
    words = set(re.findall(r"'([a-z]+)'", src))
    for b in ('board', 'fs', 'view', 'desk', 'clime', 'dye', 'crumb'):
        sels, acts = body_targets(b, 1)
        words |= {w for x in sels for w in english('sel', x)} | {str(w) for x in acts for w in english('act', x)}
    sels, acts = body_targets('spoke', 1)
    said = {w for x in sels for w in english('sel', x)} | {w for x in acts for w in english('act', x)}
    assert not said & words and 'the' not in said and not said & mine
    ws = _shop(tmp_path)
    values = {v for a in ws.observe(ws.existing()).values() for v in a.values()} - {'-'}
    ws.execute('deliver', ('b0',), {'deliver_bikes': True})
    values |= {v for a in ws.observe(ws.existing()).values() for v in a.values()} - {'-'}
    assert not values & _old_values()
    assert not values & words
    tools = set(ws.tools()) | {'prime', 'drop'}
    assert not tools & {'stamp', 'lodge', 'unlodge', 'lift', 'scrap', 'slot', 'brand', 'mkdir', 'copy', 'move', 'delete',
                        'convert', 'zap', 'replicate', 'shove', 'open', 'close', 'filter', 'sort', 'group', 'compare', 'sift',
                        'rank', 'read', 'file', 'tag', 'send', 'complete', 'pin', 'purge', 'shelve', 'mark', 'heat', 'chill',
                        'vent', 'route', 'seal', 'stoke', 'flush', 'dip', 'hang', 'bleach', 'fix', 'peg', 'scour', 'bake',
                        'prove', 'knock', 'box', 'leaven', 'punch'}
    assert not tools & words and not tools & values
    attrs = set(next(iter(ws.observe(ws.existing()).values())))
    assert attrs - {'kind', 'value'} == {'pressure', 'frame', 'brake'}
    assert not (attrs - {'kind', 'value'}) & {'mark', 'tray', 'level', 'place', 'status', 'tag', 'heat', 'air', 'wing', 'hue',
                                              'fibre', 'state', 'filter', 'sort', 'group', 'crust', 'grain', 'proof', 'ext', 'hash'}
