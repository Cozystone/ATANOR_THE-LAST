"""DESK_EVAL4_PROTOCOL.md: a return to the value the objects had right before the action is an undoing or a
re-setup (as a screen set up anew each day), not the action's later outcome. A constructed development case; the
frozen round-3 learner reads the reset as a later outcome and then thinks the work done."""
from atanor_os.agent.grounding import Grounder
from atanor_os.agent.grounding_g37 import Grounder as Grounder37
from atanor_os.teach.tutor import DeskSpec, Tutor, symbols
from atanor_os.world.desk_world import DeskWorkspace


def _taught_then_reset(tmp_path):
    ws = DeskWorkspace(tmp_path / 'desk', seed=3)
    tags = ['blue', 'green', 'none', 'green', 'blue', 'none']
    ws.add_items({f'n{i}': {'kind': 'note', 'tag': tags[i]} for i in range(6)} | {f'm{i}': {'kind': 'message', 'tag': 'red'} for i in range(4)})
    tut = Tutor(ws, DeskSpec, 1)
    tut.start({'kind': 'note'}, {'tool': 'tag', 'second': 't.red'})
    g = Grounder(ws, tmp_path / 'mind', person=tut)
    sc, ac = g.learn_selection('L'), g.learn_action('L')
    g.apply(sc['content'], ac['content'], 'L')
    sym = symbols(1)
    g.bind(sym[0], sc['content']['concept'], 'L')
    g.bind(sym[1], ac['content']['action'], 'L')
    spec = ws._read()                                      # the next day everything is set up as it was
    for i in range(6):
        spec['items'][f'n{i}']['tag'] = tags[i]
    ws._write(spec)
    return ws, [sym[1], sym[0]]


def test_a_reset_is_not_a_later_outcome(tmp_path):
    ws, words = _taught_then_reset(tmp_path)
    res = Grounder(ws, tmp_path / 'mind', person=None, caps={}).obey(words)
    assert res['ok'] and len(res['acted']) == 6
    assert all(ws.observe(ws.existing())[f'n{i}']['tag'] == 'red' for i in range(6))


def test_the_round_3_learner_reads_it_as_done(tmp_path):
    ws, words = _taught_then_reset(tmp_path)
    res = Grounder37(ws, tmp_path / 'mind', person=None, caps={}).obey(words)
    assert res['ok'] and len(res['acted']) < 6            # 'missed': it believes some notes are already done
