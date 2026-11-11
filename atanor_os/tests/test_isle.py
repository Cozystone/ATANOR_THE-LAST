"""The island's five places (reef, moor, tarn, glen, crag: one connected world of five bodies) guarantees, world
behaviour only: outside changes replay from the seed and are logged as the outside's; a call's answer and effect are a
function of its arguments' attributes before the call; the irreversible tool needs a grant; the tool changes work
through the drift; the judge reads every change against the state before; the five places share kinds, attributes,
values and laws while their tools and command words are their own; and no name, word, value or tool repeats the eight
earlier bodies'."""
import inspect
import itertools
import json
import re

import pytest

from atanor_os.eval import isle_targets as it, tutor_life
from atanor_os.eval.tutor_life import DRIFT, body_spec, body_targets, english
from atanor_os.teach.isle_spec import ENDS, symbols_isle
from atanor_os.teach.tutor import Tutor, symbols, symbols_clime, symbols_crumb, symbols_dye, symbols_spoke
from atanor_os.world import board_world, clime_world, crumb_world, desk_world, dye_world, spoke_world, view_world
from atanor_os.world import isle_world as iw
from atanor_os.world.raw_obs import raw_attrs, to_human

PLACES = it.PLACES
U = {'u0': {'depth': 0, 'spin': 1, 'coat': 'ashen', 'tide': 'neap'}, 'u1': {'depth': 2, 'spin': 3, 'coat': 'ochre', 'tide': 'ebb'},
     'u2': {'depth': 4, 'spin': 0, 'coat': 'umber', 'tide': 'flood'}, 'u3': {'depth': 3, 'spin': 2, 'coat': 'ashen', 'tide': 'flood'},
     'u4': {'depth': 1, 'spin': 2, 'coat': 'umber', 'tide': 'neap'}}
S = {'flint': {'depth': 2, 'spin': 1, 'coat': 'ashen', 'tide': 'flood'}, 'basalt': {'depth': 4, 'spin': 2, 'coat': 'umber', 'tide': 'ebb'},
     'shale': {'depth': 1, 'spin': 3, 'coat': 'ochre', 'tide': 'neap'}}


def _place(tmp_path, body, name='w'):
    ws = it.workspace(body)(tmp_path / name, seed=7)
    spec = ws._read()
    spec['steles'] = {k: dict(v) for k, v in S.items()}
    ws._write(spec)
    ws.add_urns(U)
    return ws


def _grants(ws):
    return {c: True for c in ws.CAPABILITY.values()}


@pytest.mark.parametrize('body', PLACES)
def test_outside_changes_replay_and_are_logged(tmp_path, body):
    a, b = _place(tmp_path, body, 'a'), _place(tmp_path, body, 'b')
    for _ in range(6):
        a.tick(), b.tick()
    assert a.observe(a.existing()) == b.observe(b.existing())
    st = a.observe(a.existing())
    assert {o for o in st if st[o]['kind'] == 'stele'} == set(iw.VALUE_OBJECTS)
    assert not any(st[o]['kind'] == 'urn' for o in st)                      # old urns were taken away
    rows = [json.loads(l) for l in open(a.root / 'world_log.jsonl', encoding='utf-8')]
    assert all(r['actor'] == 'outside' for r in rows if r['event'] in ('tick', 'arrive'))
    assert any(c[1] == 'taken' for r in rows if r['event'] == 'tick' for c in r['changes'])
    assert any(c[0].startswith('k.') for r in rows if r['event'] == 'tick' for c in r['changes'])


def test_the_laws():
    x, s = {'kind': 'urn', 'depth': 2, 'spin': 3, 'coat': 'ochre', 'tide': 'ebb', 'value': '-'}, {'kind': 'stele', **S['basalt'], 'value': 'basalt'}
    E, R = iw.EFFECT, iw.REFUSE
    assert E['E1'](x, s) == {'depth': 4} and E['E1']({**x, 'depth': 3}, s) == {'depth': 4}        # stops at the end
    assert E['E2'](x, s) == {'depth': 1} and E['E2']({**x, 'depth': 0}, s) == {'depth': 0}
    assert E['E3'](x, s) == {'coat': 'umber'}
    assert [E['E4']({**x, 'tide': t}, s)['tide'] for t in iw.TIDES] == ['neap', 'flood', 'ebb']
    assert E['E5'](x, s) == {'spin': 2} and E['E5']({**x, 'coat': 'umber', 'spin': 2}, s) == {'spin': 3}
    assert E['E5']({**x, 'spin': 0}, s) == {'spin': 0} and E['E5']({**x, 'coat': 'umber'}, s) == {'spin': 3}
    assert E['E6'](x, s) == {'depth': 3, 'spin': 2} and E['E6']({**x, 'depth': 4, 'spin': 0}, s) == {'depth': 0, 'spin': 3}
    assert E['E7'](x, s) == {'spin': 2} and E['E7']({**x, 'depth': 0}, s) == {'spin': 3}
    assert [E['E8']({**x, 'spin': k}, s)['coat'] for k in iw.SPINS] == ['ashen', 'ochre', 'umber', 'ashen']
    assert E['E9'](x, s) == {'spin': 0} and E['E10'](x, s) == {'tide': 'ebb'} and E['E11'](x, s) == {'value': 'bound'}
    assert R['R3'](x, s) and not R['R3']({**x, 'tide': 'neap'}, s)
    assert R['R4'](x, {**s, 'spin': 0}) and not R['R4'](x, s)
    assert R['R5'](x, s) and not R['R5']({**x, 'coat': 'umber'}, s)
    assert R['R6']({**x, 'depth': 4}, {**s, 'depth': 3}) and not R['R6'](x, s)
    two = iw.tool('E2', 'E3', 'R4')
    assert two['arity'] == 2 and iw.result(two, x, s) == {**x, 'depth': 1, 'coat': 'umber'}       # both laws read the state before
    assert iw.result(two, x, {**s, 'spin': 0}) is None
    assert iw.result(iw.tool('E9'), {**x, 'spin': 0}) is None                                     # R2: nothing would change
    assert iw.result(iw.tool('E9'), {**x, 'value': 'bound'}) is None                              # R1: bound for good
    assert iw.result(two, s, x) is None and iw.result(two, x, x) is None                          # an urn first, then a stele


@pytest.mark.parametrize('body', PLACES)
def test_every_call_is_a_function_of_its_arguments_before(tmp_path, body):
    ws = _place(tmp_path, body)
    assert 4 <= len(ws.TABLE) <= 7
    for name, spec in ws.TABLE.items():
        for u in U:
            for k in (iw.VALUE_OBJECTS if spec['arity'] == 2 else (None,)):
                ws = _place(tmp_path, body, f'{name}-{u}-{k}')
                st = ws.observe(ws.existing())
                args = (u, k) if k else (u,)
                want = iw.result(spec, st[u], st.get(k))
                r = ws.execute(name, args, _grants(ws))
                now = ws.observe(ws.existing())
                assert r['ok'] == (want is not None)
                assert now[u] == (want or st[u])
                assert {o: a for o, a in now.items() if o != u} == {o: a for o, a in st.items() if o != u}   # nothing else moves
                if k:
                    assert not ws.execute(name, (k, u), _grants(ws))['ok']  # the stele is the second argument
    with pytest.raises(ValueError):
        ws.execute('nosuchtool', ('u0',), {})
    rows = [json.loads(l) for l in open(ws.root / 'world_log.jsonl', encoding='utf-8')]
    assert all(set(r['obs_before']) == set(r['args']) == set(r['obs_after']) for r in rows if r['event'] == 'act')


@pytest.mark.parametrize('body', PLACES)
def test_the_irreversible_tool_needs_its_grant(tmp_path, body):
    ws = _place(tmp_path, body)
    bind = it.BIND[body]
    assert ws.CAPABILITY == {bind: f'{bind}_urns'}
    assert ws.execute(bind, ('u0',), {})['blocked']                         # no grant, nothing bound
    assert ws.observe(ws.existing())['u0']['value'] == '-'
    assert ws.execute(bind, ('u0',), _grants(ws))['ok']
    st = ws.observe(ws.existing())
    assert st['u0'] == {'kind': 'urn', **U['u0'], 'value': 'bound'}
    for name, spec in ws.TABLE.items():                                     # bound for good: every tool refuses
        for k in (iw.VALUE_OBJECTS if spec['arity'] == 2 else (None,)):
            assert not ws.execute(name, ('u0', k) if k else ('u0',), _grants(ws))['ok']
    assert ws.observe(ws.existing()) == st
    for _ in range(3):
        ws.tick()
    assert ws.observe(ws.existing())['u0'] == st['u0']                      # the outside leaves a bound urn alone too


@pytest.mark.parametrize('body', PLACES)
def test_tool_changes_through_the_drift(tmp_path, body):
    spec = body_spec(body)
    for old in (it.RETIRED[body], it.UNSEEN[body]):
        ws = _place(tmp_path, body, f'd-{old}')
        new = ws.RETIRE[old]
        assert new not in ws.tools()
        act = next(a for a in body_targets(body, 1)[1] if a['tool'] == old)
        st = ws.observe(ws.existing())
        u = next(o for o in U if spec.possible(act, o, st))
        assert spec.steps(act, u, ws.drift)[0] == old
        ws.drift = frozenset({f'{old}_retired'})
        assert ws.tools()[new] == ws.tools()[old] == ws.TABLE[old]['arity']
        tool, args = spec.steps(act, u, ws.drift)
        assert tool == new
        assert not ws.execute(old, args, _grants(ws))['ok']                 # the old name does nothing now
        assert ws.observe(ws.existing()) == st
        assert ws.execute(new, args, _grants(ws))['ok']
        assert ws.observe(ws.existing())[u] == spec.given(act, u, st)
        lab = ws.lab_copy(tmp_path / f'lab-{old}')
        assert type(lab) is type(ws) and lab.observe(lab.existing()) == ws.observe(ws.existing()) and lab.drift == ws.drift
    assert DRIFT[body] == f'{it.RETIRED[body]}_retired'


@pytest.mark.parametrize('body', PLACES)
def test_the_judge_reads_every_change_against_the_state_before(tmp_path, body):
    spec = body_spec(body)
    sels, acts = body_targets(body, 1)
    assert spec.BODY == body and spec.RELATIVE and spec.KEEP_IMPOSSIBLE
    for act in acts:
        ws = _place(tmp_path, body, f"j-{act['tool']}-{act.get('second', 'x')[-3:]}")
        t = Tutor(ws, spec, 1)
        t.start({'kind': 'urn', 'at': body}, act)
        assert t.truth == sorted(U)
        can = [o for o in t.truth if spec.possible(act, o, t.before)]
        assert can, act                                                     # the fixture lets every act be shown
        assert not t.judge()                                                # nothing done yet
        assert not any(spec.shows(act, o, t.before) for o in t.truth)
        for o in can:
            tool, args = spec.steps(act, o, ws.drift)
            assert ws.execute(tool, args, t.grants())['ok']
        assert t.judge()                                                    # each urn that can change shows it; the rest are as they were
        other = next(a for a in acts if a['tool'] not in (act['tool'], it.BIND[body]))
        st = ws.observe(ws.existing())
        hit = next((o for o in t.truth if spec.possible(other, o, st)), None)
        if hit:
            ws.execute(*spec.steps(other, hit, ws.drift), t.grants())
            assert not t.judge()                                            # another change is not what was meant
    t.start(sels[0], acts[0])
    assert all(o in U and ws.observe(ws.existing())[o]['kind'] == 'urn' for o in t.truth)


@pytest.mark.parametrize('body', PLACES)
def test_raw_observation_round_trip_and_hooks(tmp_path, body):
    from atanor_os.life.host import open_world
    from atanor_os.repr.run_act import worlds
    from atanor_os.repr.run_bundles import RETIRED
    from atanor_os.rebuild.summ_stage4 import NEW
    ws = _place(tmp_path, body, body)
    for o, a in ws.observe(ws.existing()).items():
        assert to_human(body, raw_attrs(body, a), {}) == a and list(a) == list(iw.ATTRS)
    assert open_world(body, tmp_path).observe(ws.existing()) == ws.observe(ws.existing())
    assert body in NEW and RETIRED[body] == it.RETIRED[body]
    mk = worlds(body, tmp_path / 'ev', 101, [DRIFT[body]])
    assert len(mk) == 3
    h = mk[1]()
    assert type(h) is type(ws) and h.drift == frozenset({DRIFT[body]}) and sum(a['kind'] == 'urn' for a in h.observe(h.existing()).values()) > 5
    home = tutor_life.make_home(body, tmp_path / 'mh', 1, 100)
    assert type(home) is type(ws) and (tmp_path / 'mh' / body / f'{body}.json').exists()
    mod = __import__(f'atanor_os.eval.{body}_eval', fromlist=['evaluate'])
    assert callable(mod.evaluate) and callable(mod.oracle_only) and callable(__import__(f'atanor_os.eval.{body}_run', fromlist=['run']).run)


def test_inflow_brings_every_coat_each_day():
    for body in PLACES:
        for d in range(100, 140):
            urns = it.inflow(body, 1, d)
            assert {u['coat'] for u in urns.values()} == set(iw.COATS)
            assert all(u['depth'] in iw.DEPTHS and u['spin'] in iw.SPINS and u['tide'] in iw.TIDES for u in urns.values())
        assert it.inflow(body, 1, 100) == it.inflow(body, 1, 100) != it.inflow(body, 2, 100)


def test_one_world_the_places_share_laws_under_their_own_tool_names():
    tables = {b: it.workspace(b).TABLE for b in PLACES}
    where = {}
    for b, table in tables.items():
        for name, spec in table.items():
            for law in spec['effects'] + spec['refuse']:
                where.setdefault(law, set()).add((b, name))
    effects = [l for l in iw.EFFECT if l != 'E11']
    assert set(where) == set(iw.EFFECT) | set(iw.REFUSE) and 8 <= len(effects) + 1 <= 12 and 4 <= len(iw.REFUSE) + 2 <= 6
    for law, uses in where.items():
        assert len({b for b, _ in uses}) >= 2, law                         # every law is met in at least two places
        assert len({n for _, n in uses}) == len(uses)                      # ... under another tool name each time
    alone = {l: {b for b, t in tables.items() for s in t.values() if s['effects'] == (l,)} for l in effects}
    for b, table in tables.items():                                        # each place joins two laws that stand alone elsewhere
        assert any(len(s['effects']) == 2 and all(alone[l] - {b} for l in s['effects']) for s in table.values()), b
        assert all(1 <= len(s['effects']) <= 2 and len(s['refuse']) <= 1 for s in table.values())
    names = [n for b in PLACES for n in list(tables[b]) + list(it.workspace(b).RETIRE.values())]
    assert len(names) == len(set(names))                                   # no tool name is used in two places
    for b in PLACES:
        ws = it.workspace(b)
        assert set(ws.RETIRE) <= set(ws.TABLE) and {it.RETIRED[b], it.UNSEEN[b]} == set(ws.RETIRE) and it.BIND[b] in ws.TABLE
        assert {a['tool'] for a in body_targets(b, 1)[1]} == set(ws.TABLE)
        assert all(('second' in a) == (ws.TABLE[a['tool']]['arity'] == 2) for a in body_targets(b, 1)[1])


def _old():
    values = set(board_world.TRAYS.values()) | set(board_world.MARKS) | set(board_world.LEVELS) | set(clime_world.LEVELS)
    values |= set(clime_world.WINGS) | set(clime_world.WEATHER) | set(desk_world.PLACES) | set(desk_world.TAGS)
    values |= set(dye_world.HUES) | set(dye_world.FIBRES) | set(dye_world.VATS) | set(view_world.EXTS) | set(view_world.KEYS)
    values |= set(view_world.GROUPS) | set(crumb_world.CRUSTS) | set(crumb_world.GRAINS) | set(crumb_world.DIALS)
    values |= set(crumb_world.OVENS) | set(spoke_world.PRESSURES) | set(spoke_world.FRAMES) | set(spoke_world.BRAKES)
    values |= set(spoke_world.GAUGES) | set(spoke_world.PUMPS)
    values |= {'card', 'bay', 'message', 'draft', 'task', 'note', 'file', 'dir', 'panel', 'bolt', 'vat', 'loaf', 'oven', 'bike', 'pump',
               'fresh', 'stale', 'sealed', 'fixed', 'wet', 'dry', 'unread', 'locked', 'plain', 'open', 'boxed', 'slack', 'risen',
               'delivered'}
    tools = {'stamp', 'lodge', 'unlodge', 'lift', 'scrap', 'slot', 'brand', 'mkdir', 'copy', 'move', 'delete', 'convert', 'zap',
             'replicate', 'shove', 'open', 'close', 'filter', 'sort', 'group', 'compare', 'sift', 'rank', 'read', 'file', 'tag',
             'send', 'complete', 'pin', 'purge', 'shelve', 'mark', 'heat', 'chill', 'vent', 'route', 'seal', 'stoke', 'flush',
             'dip', 'hang', 'bleach', 'fix', 'peg', 'scour', 'bake', 'prove', 'knock', 'box', 'leaven', 'punch', 'inflate',
             'release', 'bleed', 'deliver', 'prime', 'drop'}
    tools |= set(board_world.TOOLS) | set(clime_world.TOOLS) | set(desk_world.TOOLS) | set(dye_world.TOOLS) | set(view_world.TOOLS)
    tools |= set(crumb_world.TOOLS) | set(spoke_world.TOOLS)
    words = set(re.findall(r"'([a-z]+)'", inspect.getsource(tutor_life.english)))   # every literal of the eight bodies' table
    for b in ('board', 'fs', 'view', 'desk', 'clime', 'dye', 'crumb', 'spoke'):
        sels, acts = body_targets(b, 1)
        words |= {w for x in sels for w in english('sel', x)} | {str(w) for x in acts for w in english('act', x)}
    attrs = {'mark', 'tray', 'level', 'place', 'status', 'tag', 'heat', 'air', 'wing', 'hue', 'fibre', 'state', 'filter', 'sort',
             'group', 'crust', 'grain', 'proof', 'ext', 'hash', 'pressure', 'frame', 'brake'}
    return values, tools, words, attrs


def test_names_words_values_and_tools_never_repeat_the_eight_bodies_nor_another_place(tmp_path):
    old_values, old_tools, old_words, old_attrs = _old()
    old_syms = {w for s in range(1, 60) for g in (symbols, symbols_clime, symbols_dye, symbols_crumb, symbols_spoke) for w in g(s)}
    said, syms, tools = {}, {}, {}
    for b in PLACES:
        syms[b] = {w for s in range(1, 60) for w in symbols_isle(b, s)}
        assert all(re.fullmatch(f'[bdfgkmnprstvz][aeiou][bdfgkmnprstvz][aeiou]{ENDS[b]}', w) for w in syms[b])   # five letters: a shape no earlier generator makes
        assert len(symbols_isle(b, 1)) == 40 == len(set(symbols_isle(b, 1))) and symbols_isle(b, 1) == symbols_isle(b, 1)
        sels, acts = body_targets(b, 1)
        assert all(s['kind'] == 'urn' and s['at'] == b for s in sels)
        own = {w for x in sels for w in english('sel', x)} | {w for x in acts if 'second' not in x for w in english('act', x)}
        own |= {english('act', x)[0] for x in acts} | {w for ws in it.DEV_SUBS[b].values() for w in ws}
        assert all(english('act', x)[1:] == ([x['second'][2:]] if 'second' in x else []) for x in acts)   # a stele is called by its name
        assert set(it.DEV_SUBS[b]) <= own and 'the' not in own
        said[b] = own
        ws = it.workspace(b)
        tools[b] = set(ws.TABLE) | set(ws.RETIRE.values())
        assert not syms[b] & old_syms and not said[b] & (old_words | old_values | old_tools | old_attrs)
        assert not tools[b] & (old_tools | old_words | old_values | old_attrs)
        assert not said[b] & tools[b] and not syms[b] & (said[b] | tools[b])
    for a, b in itertools.combinations(PLACES, 2):                         # between the places: tools and command words differ
        assert not said[a] & said[b] and not tools[a] & tools[b] and not syms[a] & syms[b]
        assert not said[a] & tools[b] and not said[b] & tools[a]
    seen = {}
    for b in PLACES:                                                       # ... while kinds, attributes and values are the same
        ws = _place(tmp_path, b, b)
        ws.execute(it.BIND[b], ('u0',), _grants(ws))
        st = ws.observe(ws.existing())
        seen[b] = (sorted({a['kind'] for a in st.values()}), [list(a) for a in st.values()][0], st)
        values = {v for a in st.values() for v in a.values() if isinstance(v, str)} - {'-'}
        assert values == {'urn', 'stele', 'bound', *iw.COATS, *iw.TIDES, *iw.STELES}
        assert not values & (old_values | old_words | old_tools) and not values & set().union(*said.values(), *tools.values())
        assert all(isinstance(a[k], int) for a in st.values() for k in ('depth', 'spin'))                 # numeric attributes are small ints
        assert not (set(iw.ATTRS) - {'kind', 'value'}) & (old_attrs | old_words | old_tools | old_values)
    assert all(seen[b] == seen[PLACES[0]] for b in PLACES)
    assert not set(PLACES) & (old_values | old_words | old_tools | old_attrs | {'board', 'clime', 'desk', 'dye', 'fs', 'view', 'crumb', 'spoke'})
