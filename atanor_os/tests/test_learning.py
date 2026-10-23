"""Spec tests for induction, retrieval, council and the vertical loop. Passing is NOT learning evidence."""
from atanor_os.agent.loop import run_episode
from atanor_os.agent.models import CouncilModel, DocModel, RetrievalModel, RuleModel
from atanor_os.agent.rule_learner import learn_operator
from atanor_os.core.journal import Journal
from atanor_os.core.types import Experience
from atanor_os.eval.explore import explore
from atanor_os.eval.generator import make_task
from atanor_os.eval.oracle import TrueModel, reachable


def O(kind, ext='txt', h='-', pk='dir'):
    return {'kind': kind, 'ext': ext, 'hash': h, 'parent_kind': pk}


def X(i, args, pre, post, ok):
    return Experience(f'x{i}', 'copy', args, pre, post, ok)


def test_precondition_induction_on_controlled_contrasts():
    s1 = {'a.txt': O('file', 'txt', 'h1'), 'd': O('dir', '-'), 'd/b.txt': O('absent', 'txt')}
    s2 = {'c.csv': O('file', 'csv', 'h2'), 'e.csv': O('absent', 'csv')}
    f1 = {'a.txt': O('file', 'txt', 'h1'), 'z.txt': O('file', 'txt', 'h3')}                    # target exists
    f2 = {'a.txt': O('file', 'txt', 'h1'), 'q': O('absent', '-'), 'q/b.txt': O('absent', 'txt', pk='absent')}  # no parent
    f3 = {'d': O('dir', '-'), 'x.txt': O('absent', 'txt')}                                       # source not a file
    exps = [X(1, ('a.txt', 'd/b.txt'), s1, {**s1, 'd/b.txt': O('file', 'txt', 'h1')}, True),
            X(2, ('c.csv', 'e.csv'), s2, {**s2, 'e.csv': O('file', 'csv', 'h2')}, True),
            X(3, ('a.txt', 'z.txt'), f1, f1, False), X(4, ('a.txt', 'q/b.txt'), f2, f2, False),
            X(5, ('d', 'x.txt'), f3, f3, False)]
    op = learn_operator('copy', 2, exps)
    assert op.pre == frozenset({('kind', (0,), 'file'), ('kind', (1,), 'absent'), ('parent_kind', (1,), 'dir')}), op.to_json()
    assert op.effects == [(1, 'hash', ('copy', 0)), (1, 'kind', ('const', 'file'))]
    assert op.status == 'supported' and op.counter == []
    assert ('ext', (0,), 'txt') not in op.pre                       # ext differed across successes: never required
    # one more failure the representation cannot separate -> flagged, not hidden
    f4 = {'a.txt': O('file', 'txt', 'h1'), 'd': O('dir', '-'), 'd/n.txt': O('absent', 'txt')}
    op2 = learn_operator('copy', 2, exps + [X(6, ('a.txt', 'd/n.txt'), f4, f4, False)])
    assert op2.status == 'unseparable' and op2.counter == ['x6'] and op2.pre == op.pre


def test_rule_from_real_exploration_has_true_effects(tmp_path):
    exps = explore(99, 300, tmp_path / 'x')
    op = learn_operator('copy', 2, [e for e in exps if e.tool == 'copy'])
    assert op.pre is not None and op.support >= 1, op.to_json()
    assert ('kind', (0,), 'file') in op.pre and ('kind', (1,), 'absent') in op.pre, op.to_json()
    assert (1, 'kind', ('const', 'file')) in op.effects and (1, 'hash', ('copy', 0)) in op.effects


def test_oracle_solves_dev_task_and_models_run(tmp_path):
    exps = explore(7, 120, tmp_path / 'x')
    ws, goal, meta = make_task(0, 'dev', tmp_path / 'ws')
    assert reachable(ws, goal) is not None
    j = Journal(tmp_path / 'j.sqlite')
    rec = run_episode(ws, goal, TrueModel(), j, 'oracle')
    assert goal.satisfied(ws.observe(goal.universe)) and not rec['keep_violated'] and rec['noops'] == 0
    assert j.unresolved() == []
    ws2, goal2, _ = make_task(1, 'dev', tmp_path / 'ws2')
    st = ws2.observe(goal2.universe)
    absent = next(p for p in sorted(st) if st[p]['kind'] == 'absent' and st[p]['parent_kind'] == 'dir')
    for M in (DocModel, RetrievalModel, RuleModel, CouncilModel):
        post, status = M(exps).predict(st, 'mkdir', (absent,))
        assert post is not None and post[absent]['kind'] == 'dir', (M.name, status)
    assert rec['plan_stops'] and all(k == 'found' for k in rec['plan_stops'])
    j.close()
