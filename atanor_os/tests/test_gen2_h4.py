"""GEN2_H4_PROTOCOL.md: with the person there, ATANOR asks before acting on an object in a state never confirmed
('this one too?'); a 'no' is kept, and alone later an object in that state is left alone and reported, while the
rest of the command is done. A constructed development case on the climate bays."""
from atanor_os.agent.grounding import Grounder
from atanor_os.teach.tutor import ClimeSpec, Tutor, symbols_clime
from atanor_os.world.clime_world import ClimeWorkspace


def test_a_refused_state_is_asked_once_and_then_left_alone(tmp_path):
    ws = ClimeWorkspace(tmp_path / 'clime', seed=3)
    ws.add_bays({'b0': {'heat': 'chill', 'air': 'stale', 'wing': 'north'}, 'b1': {'heat': 'chill', 'air': 'fresh', 'wing': 'south'},
                 'b2': {'heat': 'chill', 'air': 'stale', 'wing': 'east'}, 'b3': {'heat': 'mild', 'air': 'fresh', 'wing': 'north'}})
    sym = symbols_clime(1)
    tut = Tutor(ws, ClimeSpec, 1)
    tut.start({'kind': 'bay', 'heat': 'chill'}, {'tool': 'heat'})
    g = Grounder(ws, tmp_path / 'mind', person=tut)
    sc, ac = g.learn_selection('L'), g.learn_action('L')
    g.apply(sc['content'], ac['content'], 'L')
    g.reply(tut.confirm())
    g.bind(sym[1], ac['content']['action'], 'L')
    tut.start({'kind': 'bay', 'air': 'stale'}, {'tool': 'vent'})
    g.bind(sym[0], g.learn_selection('M')['content']['concept'], 'M')
    ws.add_bays({'h0': {'heat': 'hot', 'air': 'stale', 'wing': 'south'}})
    tut.start({'kind': 'bay', 'air': 'stale'}, {'tool': 'heat'})   # the person is there and means the stuffy bays
    res = Grounder(ws, tmp_path / 'mind', person=tut).obey([sym[1], sym[0]])
    assert tut.help['prior'] >= 1 and 'h0' in res['withheld'] and ws.observe(ws.existing())['h0']['heat'] == 'hot'
    ws.add_bays({'h1': {'heat': 'hot', 'air': 'stale', 'wing': 'north'}})
    alone = Grounder(ws, tmp_path / 'mind', person=None, caps={})
    st = alone.feats()
    effect = alone.mem.claims.current(ac['id'])['content']
    unknown, refused = alone._prior_split(effect, ['h1'], st)
    assert refused == ['h1'] and not unknown              # the 'no' carries to another bay in the same state
