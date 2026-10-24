"""P4 spec tests: the supervisor survives a crash between a real action and its record, reconciles intent
against the real workspace, resumes from the real state, and the evaluator confirms it from disk."""
import json

import pytest

from atanor_os.agent.loop import SimulatedCrash
from atanor_os.agent.models import RuleModel
from atanor_os.agent.supervisor import Supervisor
from atanor_os.core.journal import Journal
from atanor_os.eval.explore import explore
from atanor_os.eval.supervise import crash_test, reopen_fs, run_supervisor, task_stream, verify_from_disk
from atanor_os.eval.view_tasks import view_block


class CrashOnce:
    """Raises SimulatedCrash the first time `episode` reaches `step`, right after the real action."""

    def __init__(self, episode, step):
        self.episode, self.step, self.fired, self.current = episode, step, False, None

    def arm(self, eid):
        self.current = eid

    def __call__(self, step):
        if not self.fired and self.current == self.episode and step == self.step:
            self.fired = True
            raise SimulatedCrash()


def _base(tmp_path):
    return explore(1, 120, tmp_path / 'x', policy='contrast')


@pytest.mark.fs
def test_supervisor_reconciles_and_resumes_after_crash(tmp_path):
    base = _base(tmp_path)
    root = tmp_path / 'sup'
    crash = CrashOnce('sup-0', 1)
    sup = Supervisor(root, lambda e: RuleModel(e), base, task_stream('fs'), reopen_fs)
    try:
        with pytest.raises(SimulatedCrash):
            sup.run(2, fault=crash)
    finally:
        sup.close()
    j = Journal(root / 'journal.sqlite')
    assert j.unresolved() and j.unresolved()[0][5] == 'intended'          # the action happened, its verification did not
    assert j.open_episodes()[0]['id'] == 'sup-0'
    j.close()
    sup2 = Supervisor(root, lambda e: RuleModel(e), base, task_stream('fs'), reopen_fs)
    try:
        rec = dict(sup2.stats['reconciled'])
        assert sum(rec.values()) == 1 and rec['unknown'] == 0, rec          # judged from disk: done or not_done, never guessed
        sup2.run(2)
        s = sup2.summary()
    finally:
        sup2.close()
    assert s['resumed_episodes'] == 1 and s['episodes_finished'] == 2 and s['unresolved'] == 0, s
    v = verify_from_disk(root, 'fs')
    assert v['false_done'] == [] and v['unresolved_actions'] == 0 and v['duplicate_action_ids'] == 0, v
    assert v['claimed_done'] == v['really_done'] >= 1, v
    j = Journal(root / 'journal.sqlite')
    statuses = dict(j.db.execute("SELECT id, error FROM actions WHERE status='reconciled'").fetchall())
    j.close()
    assert len(statuses) == 1 and list(statuses.values())[0].startswith('reconciled:'), statuses


@pytest.mark.view
def test_supervisor_runs_the_view_body(tmp_path):
    exps = explore(1, 150, tmp_path / 'xv', policy='contrast-kind', block=view_block)
    p = tmp_path / 'view.jsonl'
    p.write_text('\n'.join(json.dumps(e.to_json()) for e in exps), encoding='utf-8')
    s = run_supervisor(tmp_path / 'supv', 'view', p, 2)
    assert s['episodes_finished'] == 2 and s['unresolved'] == 0, s
    v = verify_from_disk(tmp_path / 'supv', 'view')
    assert v['false_done'] == [], v


@pytest.mark.timing
def test_process_level_crash_test(tmp_path):
    base = _base(tmp_path)
    p = tmp_path / 'fs.jsonl'
    p.write_text('\n'.join(json.dumps(e.to_json()) for e in base), encoding='utf-8')
    r = crash_test(tmp_path / 'crash', 'fs', p, n_episodes=10, kill_min=0.4, kill_max=0.9, seed=2, max_restarts=120, pace_s=0.25)
    assert r['ok'], json.dumps(r, default=str)[:2000]
    assert r['crash_log']['kills'] >= 1, r['crash_log']                   # the test must actually have killed it
