"""GEN2_H5_PROTOCOL.md: the 'this one too?' confirmation has three answers. 'Leave it as it is' refuses the state, so
alone later another object in that state is left; 'not one I meant' says nothing about the state. A constructed
development case on the climate bays."""
from atanor_os.agent.grounding import Grounder
from atanor_os.teach.tutor import ClimeSpec, Tutor, symbols_clime
from atanor_os.world.clime_world import ClimeWorkspace


class _Person(Tutor):
    def __init__(self, *a, answers=None, **k):
        super().__init__(*a, **k)
        self.answers = answers or {}

    def prior(self, obj, effect=None):
        self.help['prior'] += 1
        return self.answers.get(obj) or super().prior(obj, effect)


def _taught(tmp_path, answers):
    ws = ClimeWorkspace(tmp_path / 'clime', seed=3)
    ws.add_bays({'b0': {'heat': 'chill', 'air': 'stale', 'wing': 'north'}, 'b1': {'heat': 'chill', 'air': 'fresh', 'wing': 'south'},
                 'b2': {'heat': 'chill', 'air': 'stale', 'wing': 'east'}, 'b3': {'heat': 'mild', 'air': 'fresh', 'wing': 'north'}})
    sym = symbols_clime(1)
    tut = _Person(ws, ClimeSpec, 1, answers=answers)
    tut.start({'kind': 'bay', 'heat': 'chill'}, {'tool': 'heat'})
    g = Grounder(ws, tmp_path / 'mind', person=tut)
    sc, ac = g.learn_selection('L'), g.learn_action('L')
    g.apply(sc['content'], ac['content'], 'L')
    g.reply(tut.confirm())
    g.bind(sym[1], ac['content']['action'], 'L')
    tut.start({'kind': 'bay', 'air': 'stale'}, {'tool': 'vent'})
    g.bind(sym[0], g.learn_selection('M')['content']['concept'], 'M')
    ws.add_bays({'h0': {'heat': 'hot', 'air': 'stale', 'wing': 'south'}})
    tut.start({'kind': 'bay', 'air': 'stale'}, {'tool': 'heat'})
    res = Grounder(ws, tmp_path / 'mind', person=tut).obey([sym[1], sym[0]])
    ws.add_bays({'h1': {'heat': 'hot', 'air': 'stale', 'wing': 'north'}})
    alone = Grounder(ws, tmp_path / 'mind', person=None, caps={})
    return ws, res, alone._prior_split(alone.mem.claims.current(ac['id'])['content'], ['h1'], alone.feats())


def test_leave_refuses_the_state(tmp_path):
    ws, res, (unknown, refused) = _taught(tmp_path, {})
    assert 'h0' in res['withheld'] and ws.observe(ws.existing())['h0']['heat'] == 'hot'
    assert refused == ['h1'] and not unknown


def test_not_meant_says_nothing_about_the_state(tmp_path):
    ws, res, (unknown, refused) = _taught(tmp_path, {'h0': 'not_meant'})
    assert 'h0' in res['withheld'] and ws.observe(ws.existing())['h0']['heat'] == 'hot'
    assert unknown == ['h1'] and not refused
