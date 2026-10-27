"""GEN3_F_PROTOCOL.md: alone, each object the concept picks is acted on or left as the learner's own cases of that action
say. A warm bay was chilled in the lesson; later, alone, another warm bay is chilled (a case agrees on a change), while a
hot bay, from which the action was never seen, is left and reported, and the evidence needed is kept as a claim.
A constructed development case."""
from atanor_os.agent.grounding import Grounder
from atanor_os.teach.tutor import ClimeSpec, Tutor, symbols_clime
from atanor_os.world.clime_world import ClimeWorkspace


def test_alone_each_object_as_own_cases_say(tmp_path):
    sym, mind = symbols_clime(1), tmp_path / 'mind'
    ws = ClimeWorkspace(tmp_path / 'a', seed=7)
    ws.add_bays({'p0': {'heat': 'warm', 'air': 'stale', 'wing': 'north'},     # a frosty bay cannot be chilled: the demo
                 'p1': {'heat': 'frost', 'air': 'stale', 'wing': 'north'}})   # starts on the warm one
    tut = Tutor(ws, ClimeSpec, 1)
    tut.start({'kind': 'bay'}, {'tool': 'chill'})
    g = Grounder(ws, mind, person=tut)
    sc, ac = g.learn_selection('L'), g.learn_action('L')
    g.bind(sym[0], sc['content']['concept'], 'L')
    g.bind(sym[1], ac['content']['action'], 'L')
    home = ClimeWorkspace(tmp_path / 'b', seed=7)
    home.add_bays({'r0': {'heat': 'warm', 'air': 'stale', 'wing': 'north'}, 'r1': {'heat': 'hot', 'air': 'stale', 'wing': 'north'}})
    alone = Grounder(home, mind, person=None, caps={})
    res = alone.obey([sym[1], sym[0]])
    st = home.observe(home.existing())
    assert res['acted'] == ['r0'] and st['r0']['heat'] == 'mild'
    assert res['withheld'] == ['r1'] and st['r1']['heat'] == 'hot' and not res['ok']
    assert alone.mem.claims.claims('need')
    old = Grounder(home, mind, person=None, caps={}, cases=False).obey([sym[1], sym[0]])
    assert 'r1' in old['acted']                            # without step F the hot bay is chilled too
