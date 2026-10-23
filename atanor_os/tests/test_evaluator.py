"""Evaluator validity tests (v2, after review): task definitions, budgets, council vote, semantics coverage."""
from atanor_os.agent.loop import run_episode
from atanor_os.agent.models import CouncilModel
from atanor_os.agent.planner import plan
from atanor_os.core.journal import Journal
from atanor_os.core.types import Goal
from atanor_os.eval.generator import EXT, make_task
from atanor_os.eval.oracle import TrueModel, reachable, semantic_check
from atanor_os.world.fs_world import Workspace, name_ext


def test_convert_tasks_cannot_be_completed_by_copying(tmp_path):
    """Review finding: v1 convert goals were satisfied by copying any file. v2 goals must reject that."""
    seen = 0
    for split, idx in (('test', 2), ('test', 5), ('test', 8), ('dev', 0), ('dev', 3)):
        ws, goal, meta = make_task(idx, split, tmp_path / f'{split}{idx}')
        if meta['template'] != 'convert':
            continue
        seen += 1
        plan_len = reachable(ws, goal)
        assert plan_len is not None
        state = ws.observe(goal.universe)
        p, _ = plan(state, goal, TrueModel(), Workspace.actions(sorted(state)))
        assert any(t == 'convert' for t, _ in p), p              # the true-model plan needs convert
        target = next(x for x in goal.universe if x.endswith('.md') and state[x]['kind'] == 'absent')
        for anc in [a for a in sorted(state) if state[a]['kind'] == 'absent' and name_ext(a) == '-']:
            ws.execute('mkdir', (anc,), {})
        src = meta['files'][-1]                                  # any observable file, txt or not
        assert ws.execute('copy', (src, target), {})['ok'] is True
        assert not goal.satisfied(ws.observe(goal.universe)), 'copy must not complete a convert task'
    assert seen >= 2


def test_test_split_actually_uses_new_extensions(tmp_path):
    exts = set()
    for i in range(20):
        _, goal, meta = make_task(i, 'test', tmp_path / f't{i}')
        exts |= {name_ext(f) for f in meta['files']}
    assert {'log', 'json', 'md'} <= exts, exts
    assert set(EXT['test']) == {'txt', 'csv', 'md', 'log', 'json'}


def test_planner_reports_budget_stop_reasons(tmp_path):
    ws, goal, _ = make_task(1, 'dev', tmp_path / 'w')
    state = ws.observe(goal.universe)
    g = Goal(goal.id, goal.must, goal.keep, goal.capabilities,
             {'actions': 20, 'predictions': 5, 'nodes': 600, 'depth': 12, 'seconds': 60.0}, goal.universe)
    p, st = plan(state, g, TrueModel(), Workspace.actions(sorted(state)))
    assert p is None and st['stop'] == 'predictions' and st['predicted'] == 5
    g2 = Goal(goal.id, goal.must, goal.keep, goal.capabilities,
              {'actions': 20, 'predictions': 10 ** 6, 'nodes': 1, 'depth': 12, 'seconds': 60.0}, goal.universe)
    p2, st2 = plan(state, g2, TrueModel(), Workspace.actions(sorted(state)))
    assert st2['stop'] in ('nodes', 'found')
    j = Journal(tmp_path / 'j.sqlite')
    rec = run_episode(ws, g, TrueModel(), j, 'e')
    assert rec['planner_budget_exceeded'] and not rec['abstained'] and rec['plan_stops'] == {'predictions': 1}
    j.close()


def test_council_votes_only_with_evidence():
    from atanor_os.tests.test_learning import O, X
    s1 = {'a.txt': O('file', 'txt', 'h1'), 'd': O('dir', '-'), 'd/b.txt': O('absent', 'txt')}
    f1 = {'a.txt': O('file', 'txt', 'h1'), 'z.txt': O('file', 'txt', 'h3')}
    exps = [X(1, ('a.txt', 'd/b.txt'), s1, {**s1, 'd/b.txt': O('file', 'txt', 'h1')}, True),
            X(2, ('a.txt', 'z.txt'), f1, f1, False), X(3, ('a.txt', 'z.txt'), f1, f1, False)]
    m = CouncilModel(exps)                       # members get exps[0::3], [1::3], [2::3]: one success, two failures
    post, status = m.predict(s1, 'copy', ('a.txt', 'd/b.txt'))
    assert post is not None and status.startswith('council_')
    post2, status2 = m.predict(f1, 'copy', ('a.txt', 'z.txt'))
    assert post2 is None and status2 == 'council_fail'
    post3, status3 = m.predict(s1, 'mkdir', ('d/b.txt',))
    assert status3 == 'council_documented' and m.stats()['no_evidence'] == 1


def test_semantic_check_covers_every_tool_and_outcome(tmp_path):
    r = semantic_check(5, seed=11, root=tmp_path / 'sem')
    assert r['ok'], r
    assert all(v >= 5 for v in r['cells'].values()), r['cells']
