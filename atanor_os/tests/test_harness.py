"""Harness integrity after magi-review-02: frozen protocol parameters bind the run; the validity gate excludes
learner-performance, timing and other-body tests; a supervisor killed between its episode row and its
workspace does not wedge on restart."""
import argparse
import json

import pytest

from atanor_os.agent.models import RuleModel
from atanor_os.agent.supervisor import Supervisor
from atanor_os.core.journal import Journal
from atanor_os.eval.explore import explore
from atanor_os.eval.generator import BUDGET
from atanor_os.eval.run import TRAIN_TASKS, protocol_mismatch, validity_gate
from atanor_os.eval.supervise import reopen_fs, task_stream


def _args(**kw):
    base = dict(split='test', steps=300, tasks=20, policy='contrast', body='fs', conditions='A,B,C')
    base.update(kw)
    return argparse.Namespace(**base)


def test_protocol_parameters_bind_the_run():
    proto = {'split': 'test', 'explore_steps': 300, 'tasks': 20, 'seeds': [1, 2, 3, 4, 5], 'budget': dict(BUDGET),
             'policy': 'contrast', 'body': 'fs', 'train_tasks': TRAIN_TASKS, 'conditions_list': ['A', 'B', 'C']}
    assert protocol_mismatch(proto, _args(), [1, 2, 3, 4, 5]) == []
    bad = protocol_mismatch(proto, _args(split='dev', policy='novelty'), [1, 2, 3, 4, 5])
    assert {m['field'] for m in bad} == {'split', 'policy'}, bad
    assert protocol_mismatch(proto, _args(), [1, 2])[0]['field'] == 'seeds'
    assert protocol_mismatch(proto, _args(conditions='A,B,C,CT,E'), [1, 2, 3, 4, 5])[0]['field'] == 'conditions'
    v3 = {k: v for k, v in proto.items() if k not in ('policy', 'body', 'conditions_list', 'train_tasks')}   # v1-v3 shape
    assert protocol_mismatch(v3, _args(policy='scarce'), [1, 2, 3, 4, 5]) == []                             # absent keys do not bind
    assert protocol_mismatch(None, _args(), [1]) == []


def test_validity_gate_is_body_aware():
    assert validity_gate('fs') == 'not learning and not timing and not view'
    assert validity_gate('view') == 'not learning and not timing and not fs'


@pytest.mark.fs
def test_supervisor_survives_a_kill_before_the_workspace_exists(tmp_path):
    base = explore(1, 80, tmp_path / 'x', policy='contrast')
    root = tmp_path / 'sup'
    root.mkdir()
    j = Journal(root / 'journal.sqlite')
    task_root = root / 'ws' / 'ep0'
    j.begin_episode('sup-0', '{}', str(task_root), '{}', status='preparing')        # the row was written ...
    task_root.mkdir(parents=True)
    (task_root / 'half.txt').write_text('made before the kill')                      # ... the workspace half-made ...
    j.close()                                                                        # ... then the process died
    sup = Supervisor(root, lambda e: RuleModel(e), base, task_stream('fs'), reopen_fs)
    try:
        assert sup.stats['discarded_preparing'] == 1
        sup.run(1)
        s = sup.summary()
    finally:
        sup.close()
    assert s['episodes_finished'] == 1 and s['discarded_preparing'] == 1 and s['unresolved'] == 0, s
    assert not (task_root / 'half.txt').exists()                                     # the half-made workspace was replaced
    rows = [json.loads(l) for l in (root / 'episodes.jsonl').read_text(encoding='utf-8').splitlines()]
    assert rows[0]['episode'] == 'sup-0' and rows[0]['actions_total'] == rows[0]['actions']
