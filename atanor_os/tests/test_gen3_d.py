"""GEN3_D_PROTOCOL.md: the learner keeps a bundle per own act and compares same-action same-start bundles before acting
alone. A locked message failed to be read during a lesson (the person there); later, alone, another locked message
is left and reported, not tried, and the action claim gets no counter-example. A constructed development case."""
from atanor_os.agent.grounding import Grounder
from atanor_os.teach.tutor import DeskSpec, Tutor, symbols
from atanor_os.world.desk_world import DeskWorkspace


def test_a_start_seen_to_fail_is_left_alone(tmp_path):
    ws = DeskWorkspace(tmp_path / 'desk', seed=3)
    tags = ['red', 'blue', 'none', 'green']
    ws.add_items({f'm{i}': {'kind': 'message', 'tag': tags[i]} for i in range(4)} | {'n0': {'kind': 'note'}}
                 | {'r0': {'kind': 'message', 'tag': 'red', 'status': 'read'}, 'r1': {'kind': 'message', 'tag': 'blue', 'status': 'read'}})
    tut = Tutor(ws, DeskSpec, 1)
    tut.start({'kind': 'message'}, {'tool': 'read'})
    g = Grounder(ws, tmp_path / 'mind', person=tut)
    sc, ac = g.learn_selection('L'), g.learn_action('L')
    spec = ws._read()
    spec['items']['m3']['locked'] = True                   # one meant message gets locked during the lesson
    ws._write(spec)
    g.apply(sc['content'], ac['content'], 'L')
    g.reply(tut.confirm())
    sym = symbols(1)
    g.bind(sym[0], sc['content']['concept'], 'L')
    g.bind(sym[1], ac['content']['action'], 'L')
    ws.add_items({'xa': {'kind': 'message', 'tag': 'red'}, 'xb': {'kind': 'message', 'tag': 'blue'}})
    spec = ws._read()
    spec['items']['xb']['locked'] = True
    ws._write(spec)
    res = Grounder(ws, tmp_path / 'mind', person=None, caps={}).obey([sym[1], sym[0]])
    assert 'xb' in res['withheld'] and 'xb' not in res.get('failed', []) and 'xa' in res['acted']
    effect = Grounder(ws, tmp_path / 'mind').mem.claims.current(ac['id'])
    assert effect['status'] == 'active' and not effect['counter']
