"""P8b: stored evidence survives revision; a conflicting new success leads to revise / keep / hold depending on
re-verification and evidence strength; drift worlds and drift tasks really need the changed capability."""
import copy

import pytest

from atanor_os.agent.concepts import Representation, build, revise_b, uncertain_atoms
from atanor_os.eval.explore import explore
from atanor_os.eval.p8b import DRIFT, DriftOracle, _run, _set_drift, drift_task


def _dir_move(exps):
    """A new experience in a changed world: the source of a successful move is a directory."""
    e = next(x for x in exps if x.tool == 'move' and x.succeeded and not x.blocked)
    e = copy.deepcopy(e)
    e.pre[e.args[0]] = {'kind': 'dir', 'ext': '-', 'hash': '-', 'parent_kind': e.pre[e.args[0]]['parent_kind']}
    return e


@pytest.fixture(scope='module')
def r1(tmp_path_factory):
    es = explore(2, 400, tmp_path_factory.mktemp('x'), policy='contrast-kind')
    return build('fs', es, 8192), es


def _move_evidence(rep):
    return [g.get('ev', {}) for g in rep.rules.get('move', [])]


@pytest.mark.fs
def test_evidence_survives_a_revision_without_conflict(r1):
    rep, es = r1
    assert any(any(v >= 2 for v in ev.values()) for ev in _move_evidence(rep)), rep.rules.get('move')
    only_success = [e for e in es if e.tool != 'move' or e.succeeded][:50]      # new experience that never tests move's conditions
    out, change = revise_b(rep, only_success, 8192)
    assert out.size() <= 8192 and change['counts'] == {}
    assert out.rules.get('move'), 'move rule lost without contradicting evidence'
    rt = Representation.loads(out.dumps())
    assert rt.rules['move'][0].get('ev') == out.rules['move'][0].get('ev')


@pytest.mark.fs
@pytest.mark.parametrize('outcome,decision', [(True, 'revise'), (False, 'keep'), (None, 'hold')])
def test_conflict_decisions(r1, outcome, decision):
    rep, es = r1
    calls = []

    def verifier(body, tool, required, forbidden, concepts):
        calls.append((tool, forbidden))
        return outcome
    out, change = revise_b(rep, [_dir_move(es)] * 3, 8192, verifier)
    move_decisions = [d['decision'] for d in change['decisions'] if d['tool'] == 'move']
    assert move_decisions and set(move_decisions) == {decision}, change['decisions']
    assert calls and all(t == 'move' for t, _ in calls)
    if decision == 'hold':
        assert any(g.get('held') for g in out.rules.get('move', [])) or any(uncertain_atoms(g) for g in out.rules.get('move', []))


@pytest.mark.fs
@pytest.mark.parametrize('body', ['fs', 'view'])
def test_drift_tasks_need_the_changed_world(tmp_path, body):
    for t in range(3):
        ws, goal, meta = drift_task(body, t, tmp_path / f'n{t}')
        assert _run(ws, goal, DriftOracle(body, DRIFT[body]), tmp_path / f'n{t}.sqlite', t, meta)['completed']
        ws, goal, meta = drift_task(body, t, tmp_path / f'o{t}')
        _set_drift(ws, frozenset())
        assert not _run(ws, goal, DriftOracle(body, frozenset()), tmp_path / f'o{t}.sqlite', t, meta)['completed']
