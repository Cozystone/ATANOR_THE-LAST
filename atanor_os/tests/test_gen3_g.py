"""GEN3_G_PROTOCOL.md: alone, the learner's own cases of an action decide the objects they agree on; the others are
acted on as the core does, their needed evidence kept as a claim. In the lesson a warm bay was chilled and a sealed
one did not change. Later, alone: a warm bay is chilled (a case agrees on a change), a sealed warm bay is left (a case
agrees nothing changes; without step G it is tried and fails), and a mild bay, from a start never seen with the action,
is chilled as the core would. A constructed development case."""
import shutil

from atanor_os.agent.grounding import Grounder
from atanor_os.teach.tutor import ClimeSpec, Tutor, symbols_clime
from atanor_os.world.clime_world import ClimeWorkspace


def _bays(root, bays):
    ws = ClimeWorkspace(root, seed=7)
    ws.add_bays({k: {'air': 'stale', 'wing': 'north', **{a: b for a, b in v.items() if a != 'sealed'}} for k, v in bays.items()})
    for k, v in bays.items():
        if v.get('sealed'):
            ws.execute('seal', (k,), {'seal_bays': True}, actor='person')
    return ws


def test_cases_decide_where_they_agree(tmp_path):
    sym, mind = symbols_clime(1), tmp_path / 'mind'
    ws = _bays(tmp_path / 'a', {'p0': {'heat': 'warm'}, 'p1': {'heat': 'warm', 'sealed': True},
                                'p2': {'heat': 'hot', 'air': 'fresh', 'wing': 'south'}, 'p3': {'heat': 'chill', 'air': 'fresh', 'wing': 'east'}})
    tut = Tutor(ws, ClimeSpec, 1)
    tut.start({'kind': 'bay'}, {'tool': 'chill'})
    g = Grounder(ws, mind, person=tut)
    sc, ac = g.learn_selection('L'), g.learn_action('L')
    g.apply(sc['content'], ac['content'], 'L')             # with the person there: the other bays, the sealed one fails
    g.bind(sym[0], sc['content']['concept'], 'L')
    g.bind(sym[1], ac['content']['action'], 'L')
    for cases in (True, False):
        home = _bays(tmp_path / f'b{cases}', {'r0': {'heat': 'warm'}, 'r1': {'heat': 'warm', 'sealed': True},
                                                   'r2': {'heat': 'mild', 'air': 'fresh', 'wing': 'south'}})
        run = tmp_path / f'mind{cases}'                    # each run from the lesson's mind alone
        shutil.copytree(mind, run)
        alone = Grounder(home, run, person=None, caps={}, cases=cases)
        res = alone.obey([sym[1], sym[0]])
        st = home.observe(home.existing())
        assert set(res['acted']) == {'r0', 'r2'} and st['r0']['heat'] == 'mild' and st['r2']['heat'] == 'chill'
        assert (res['failed'] == []) if cases else (res['failed'] == ['r1'])
        assert bool(alone.mem.claims.claims('need')) == cases   # the mild bay's needed evidence (with G only)
