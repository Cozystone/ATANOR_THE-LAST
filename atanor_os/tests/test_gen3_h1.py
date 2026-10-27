"""GEN3_H1_PROTOCOL.md (on the core with G): two demonstrations of the same tool from different starts recorded
different results, so they became two action nodes under the same words. Alone, the command is one reading (the same objects, the same tool and
roles), not a tie. Without H1 it is held. A constructed development case."""
import pytest

from atanor_os.agent.grounding import Grounder
from atanor_os.teach.tutor import ClimeSpec, Tutor, symbols_clime
from atanor_os.world.clime_world import ClimeWorkspace


def _lesson(root, mind, bays, sym):            # a frosty or icy bay cannot be chilled: the demo starts on the other
    ws = ClimeWorkspace(root, seed=7)
    ws.add_bays(bays)
    tut = Tutor(ws, ClimeSpec, 1)
    tut.start({'kind': 'bay'}, {'tool': 'chill'})
    g = Grounder(ws, mind, person=tut)
    sc, ac = g.learn_selection('L'), g.learn_action('L')
    g.bind(sym[0], sc['content']['concept'], 'L')
    g.bind(sym[1], ac['content']['action'], 'L')
    return ac['content']['gained']


@pytest.mark.parametrize('same_doing', [True, False])
def test_one_doing_from_two_starts_is_one_reading(tmp_path, same_doing):
    sym, mind = symbols_clime(1), tmp_path / 'mind'
    first = _lesson(tmp_path / 'a', mind, {'p0': {'heat': 'warm', 'air': 'stale', 'wing': 'north'},
                                                  'p1': {'heat': 'frost', 'air': 'stale', 'wing': 'north'}}, sym)
    second = _lesson(tmp_path / 'b', mind, {'q0': {'heat': 'chill', 'air': 'stale', 'wing': 'north'},
                                                   'q1': {'heat': 'ice', 'air': 'stale', 'wing': 'north'}}, sym)
    assert first != second                                 # two nodes: the results were seen from different starts
    ws = ClimeWorkspace(tmp_path / 'c', seed=7)
    ws.add_bays({'r0': {'heat': 'mild', 'air': 'stale', 'wing': 'north'}})
    res = Grounder(ws, mind, person=None, caps={}, same_doing=same_doing).obey([sym[1], sym[0]])
    if same_doing:
        assert res['acted'] == ['r0'] and ws.observe(ws.existing())['r0']['heat'] == 'chill'
    else:
        assert res['why'] == 'unresolved' and not res.get('acted')
