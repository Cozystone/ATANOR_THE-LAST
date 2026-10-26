"""DESK_EVAL5_PROTOCOL.md: when objects last handled by another action moved to the same value too, the change is the
whole world's (as a screen set up anew), not this action's later outcome. A constructed development case: every note
was tagged by action A, some later by action B, then everything was set up anew with a fresh value. The frozen
round-4 learner reads the fresh value as A's later outcome and thinks the work done."""
from atanor_os.agent.grounding import Grounder
from atanor_os.agent.grounding_g38 import Grounder as Grounder38
from atanor_os.teach.tutor import DeskSpec, Tutor, symbols
from atanor_os.world.desk_world import DeskWorkspace


def _taught_then_set_up_anew(tmp_path):
    ws = DeskWorkspace(tmp_path / 'desk', seed=3)
    ws.add_items({f'n{i}': {'kind': 'note', 'tag': 'none'} for i in range(6)} | {'n6': {'kind': 'note', 'tag': 'red'}, 'n7': {'kind': 'note', 'tag': 'red'}})
    sym = symbols(1)
    tut = Tutor(ws, DeskSpec, 1)                           # A: tag the notes red
    tut.start({'kind': 'note'}, {'tool': 'tag', 'second': 't.red'})
    g = Grounder(ws, tmp_path / 'mind', person=tut)
    sc, ac = g.learn_selection('A'), g.learn_action('A')
    g.apply(sc['content'], ac['content'], 'A')
    g.bind(sym[0], sc['content']['concept'], 'A')
    g.bind(sym[1], ac['content']['action'], 'A')
    for o in ('n3', 'n4', 'n5'):
        ws.execute('pin', (o,), {})
    tut = Tutor(ws, DeskSpec, 2)                           # B: tag the pinned notes green (another constant)
    tut.start({'kind': 'note', 'status': 'pinned'}, {'tool': 'tag', 'second': 't.green'})
    g = Grounder(ws, tmp_path / 'mind', person=tut)
    sc2, ac2 = g.learn_selection('B'), g.learn_action('B')
    g.apply(sc2['content'], ac2['content'], 'B')
    spec = ws._read()                                      # the next day all is set up anew, with a fresh value
    for i in range(6):
        spec['items'][f'n{i}'].update(tag='blue', status='plain')
    ws._write(spec)
    return ws, [sym[1], sym[0]]


def test_a_world_wide_change_is_not_a_later_outcome(tmp_path):
    ws, words = _taught_then_set_up_anew(tmp_path)
    res = Grounder(ws, tmp_path / 'mind', person=None, caps={}).obey(words)
    assert res['ok'] and len(res['acted']) == 6


def test_the_round_4_learner_reads_it_as_done(tmp_path):
    ws, words = _taught_then_set_up_anew(tmp_path)
    res = Grounder38(ws, tmp_path / 'mind', person=None, caps={}).obey(words)
    assert res['ok'] and len(res['acted']) < 6
