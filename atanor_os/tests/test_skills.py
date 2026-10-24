"""Spec tests for macro extraction and macro planning (H2 machinery). Passing is not learning evidence."""
from atanor_os.agent.loop import run_episode
from atanor_os.agent.planner import plan
from atanor_os.agent.skills import SkillModel, extract_macros, relations
from atanor_os.core.journal import Journal
from atanor_os.eval.explore import explore
from atanor_os.eval.generator import make_task
from atanor_os.eval.oracle import TrueModel
from atanor_os.world.fs_world import Workspace

import pytest


@pytest.mark.fs
def test_relations_and_extraction():
    assert relations(('d',), ('a.txt', 'd/a.txt')) == (None, ('child', 0))
    assert relations(('out',), ('out/bins',)) == (('child', 0),)
    assert relations(('x',), ('y', 'z')) == (None, None)
    t1 = [('mkdir', ('d',)), ('move', ('a.txt', 'd/a.txt')), ('move', ('b.csv', 'd/b.csv'))]
    t2 = [('mkdir', ('e',)), ('move', ('q.txt', 'e/q.txt'))]
    t3 = [('copy', ('a.txt', 'z.txt')), ('delete', ('a.txt',))]
    ms = extract_macros([t1, t2, t3], min_support=2)
    assert [m.key() for m in ms] == [('mkdir', 'move', (None, ('child', 0)))]
    assert ms[0].support == 2
    inst = ms[0].instances([('mkdir', ('d',)), ('move', ('a.txt', 'd/a.txt')), ('move', ('a.txt', 'x/a.txt'))])
    assert inst == [('macro', (('mkdir', ('d',)), ('move', ('a.txt', 'd/a.txt'))))]


@pytest.mark.fs
def test_macro_plan_is_executed_primitive_by_primitive(tmp_path):
    for i in range(20):                                            # first dev task that is a sort (chain + moves)
        ws, goal, meta = make_task(i, 'dev', tmp_path / f'w{i}')
        if meta['template'] == 'sort':
            break
    assert meta['template'] == 'sort'
    exps = explore(5, 300, tmp_path / 'x')
    m = SkillModel(exps)
    m.learn_traces([[('mkdir', ('sorted',)), ('mkdir', ('sorted/txt',))],
                    [('mkdir', ('bak',)), ('mkdir', ('bak/txt',))],
                    [('mkdir', ('sorted/txt',)), ('move', ('a.txt', 'sorted/txt/a.txt'))],
                    [('mkdir', ('sorted/csv',)), ('move', ('b.csv', 'sorted/csv/b.csv'))]])
    assert {x.key() for x in m.macros} == {('mkdir', 'mkdir', (('child', 0),)), ('mkdir', 'move', (None, ('child', 0)))}
    state = ws.observe(goal.universe)
    acts = m.expand_actions(Workspace.actions(sorted(state)))
    assert any(a[0] == 'macro' for a in acts)
    p, st = plan(state, goal, TrueModel(), acts)
    assert p is not None and st['stop'] == 'found'
    j = Journal(tmp_path / 'j.sqlite')
    rec = run_episode(ws, goal, TrueModel(), j, 'e')
    assert rec['agent_believes_done'] and goal.satisfied(ws.observe(goal.universe))
    j.close()
