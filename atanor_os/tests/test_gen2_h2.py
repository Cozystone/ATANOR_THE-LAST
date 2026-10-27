"""GEN2_H2_PROTOCOL.md: success is what the person confirmed, not what the tool reported. A hot bay was heated once
(the tool said ok, the bay scorched) and the person said the result was wrong; that prior state is no evidence, so
alone the learner holds a later command that would heat a hot bay again. A constructed development case."""
from atanor_os.agent.grounding import Grounder
from atanor_os.teach.tutor import ClimeSpec, Tutor, symbols_clime
from atanor_os.world.clime_world import ClimeWorkspace


def test_a_harm_the_person_rejected_is_no_evidence(tmp_path):
    ws = ClimeWorkspace(tmp_path / 'clime', seed=3)
    ws.add_bays({'b0': {'heat': 'chill', 'air': 'stale', 'wing': 'north'}, 'b1': {'heat': 'chill', 'air': 'fresh', 'wing': 'south'},
                 'b2': {'heat': 'mild', 'air': 'stale', 'wing': 'east'}})
    sym = symbols_clime(1)
    tut = Tutor(ws, ClimeSpec, 1)
    tut.start({'kind': 'bay', 'heat': 'chill'}, {'tool': 'heat'})
    g = Grounder(ws, tmp_path / 'mind', person=tut)
    sc, ac = g.learn_selection('L'), g.learn_action('L')
    g.apply(sc['content'], ac['content'], 'L')
    g.reply(tut.confirm())                                 # the person confirms the lesson
    tut.start({'kind': 'bay', 'air': 'stale'}, {'tool': 'vent'})
    sc2 = g.learn_selection('M')
    g.bind(sym[0], sc2['content']['concept'], 'M')
    g.bind(sym[1], ac['content']['action'], 'L')
    ws.add_bays({'h0': {'heat': 'hot', 'air': 'stale', 'wing': 'south'}})
    g.mem.events.append('say', task='C1', symbols=[sym[1], 'h0'])
    g.apply({'atoms': ["('U', 0, 'a2', 'stale')"]}, ac['content'], 'C1')   # done with the person there: scorches h0
    assert ws.observe(ws.existing())['h0']['heat'] == 'scorch'
    g.reply(False, used=[], reason='result')                # the person: that result is wrong
    ws.add_bays({'h1': {'heat': 'hot', 'air': 'stale', 'wing': 'north'}, 'c9': {'heat': 'chill', 'air': 'stale', 'wing': 'east'}})
    alone = Grounder(ws, tmp_path / 'mind', person=None, caps={})
    effect = alone.mem.claims.current(ac['id'])['content']
    assert alone._unseen_prior(effect, ['h1', 'c9'], alone.feats()) == ['h1']   # the rejected harm taught nothing
