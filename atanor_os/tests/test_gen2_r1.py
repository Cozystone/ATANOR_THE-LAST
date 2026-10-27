"""GEN2_R1_PROTOCOL.md: demonstrations of the same tool and roles changing the same attribute are one action, whatever
value each ends in; the claim gathers the observed transitions, so one phrase names one action node."""
from atanor_os.agent.grounding import Grounder
from atanor_os.teach.tutor import ClimeSpec, Tutor
from atanor_os.world.clime_world import ClimeWorkspace


def test_relative_demonstrations_make_one_action(tmp_path):
    ws = ClimeWorkspace(tmp_path / 'clime', seed=3)
    ws.add_bays({'b0': {'heat': 'mild', 'air': 'stale', 'wing': 'north'}, 'b1': {'heat': 'warm', 'air': 'fresh', 'wing': 'south'}})
    actions = []
    for k, o in enumerate(('b0', 'b1')):
        tut = Tutor(ws, ClimeSpec, k)
        tut.start({'kind': 'bay', 'heat': ws.observe(ws.existing())[o]['heat']}, {'tool': 'chill'})
        g = Grounder(ws, tmp_path / 'mind', person=tut)
        actions.append(g.learn_action(f'L{k}'))
    assert actions[0]['id'] == actions[1]['id']            # one action node
    content = actions[1]['content']
    assert len(content['transitions']) == 2 and g._relative(content)
    assert not g._done(content, g.feats(), g.feats(), 'b0')   # a relative change: each command is one step
