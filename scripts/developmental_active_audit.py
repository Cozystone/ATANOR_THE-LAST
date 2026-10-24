"""Post-result diagnosis only: replay sealed actions, never rerun acquisition."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_active_eval import event
from scripts.developmental_task_eval import Adapter
from scripts.representation_r3_dev import configuration, native_success
from packages.action_core.world import Sandbox, Action, Frame


def linked_pairs(frame):
    return sum(v for matrix in frame['relations'].values()
               for i, row in enumerate(matrix) for j, v in enumerate(row) if i < j)


def run(source, output):
    raw = source.read_bytes()
    report = json.loads(raw)
    rows = []
    verified = 0
    with tempfile.TemporaryDirectory(prefix='atanor_active_audit_') as root:
        for row in report['lives']:
            life, arm = row['life'], row['arm']
            cfg, _, ref, payload = configuration(3, 95001 + life)
            body = Sandbox(Path(root) / f'{life}_{arm}', **cfg)
            records = row['bootstrap'] + row['acquisition']
            for record in records:
                replay = event(body, Action.from_dict(record['action']))
                assert all(replay[k] == record[k] for k in replay)
                assert body._paths[ref].read_bytes() == payload
                verified += 1
            for task in row['tasks']:
                ordinal = task['task']
                cfg, aliases, ref, payload = configuration(3 + ordinal % 2, 97001 + 20 * life + ordinal)
                test = Sandbox(Path(root) / f'{life}_{arm}_{ordinal}', **cfg)
                for record in task['trace']:
                    assert event(test, Action.from_dict(record['action'])) == record
                    assert test._paths[ref].read_bytes() == payload
                    verified += 1
                assert native_success(test, aliases, ref, payload, ordinal % 4 >= 2) == task['success']
            # Refit only sealed training; quantify repeated unresolved disagreement.
            history = list(row['bootstrap'])
            unresolved = resolved = missed = 0
            for record in row['acquisition']:
                before = Frame.from_dict(record['before'])
                action = Action.from_dict(record['action'])
                prior = Adapter(history).predict_cells(before, action)
                history.append(record)
                posterior = Adapter(history).predict_cells(before, action)
                old = {(f, tuple(a)): v for f, a, v in prior if len(v) > 1}
                new = {(f, tuple(a)): v for f, a, v in posterior}
                for key in old:
                    if len(new[key]) == 1:
                        resolved += 1
                    elif not new[key]:
                        missed += 1
                    else:
                        unresolved += 1
            rows.append({'life': life, 'arm': arm,
                         'success': sum(t['success'] for t in row['tasks']),
                         'coupling_after_bootstrap': linked_pairs(row['bootstrap'][-1]['after']),
                         'coupling_after_acquisition': linked_pairs(records[-1]['after']),
                         'first_zero_coupling_record': next((i for i,r in enumerate(records)
                                                           if linked_pairs(r['after']) == 0), None),
                         'changed_acquisition_actions': sum(r['before'] != r['after'] for r in row['acquisition']),
                         'disagreement_cells_resolved_at_same_input': resolved,
                         'disagreement_cells_still_multiple': unresolved,
                         'disagreement_cells_became_unsupported': missed})
    for arm, totals in report['summary'].items():
        selected = [r for r in report['lives'] if r['arm'] == arm]
        success = sum(t['success'] for r in selected for t in r['tasks'])
        actions = sum(len(r['bootstrap']) + len(r['acquisition']) + sum(len(t['trace']) for t in r['tasks']) for r in selected)
        assert success == totals['success'] and actions == totals['total_actions']
    assert source.read_bytes() == raw
    result = {'source_sha256': hashlib.sha256(raw).hexdigest(), 'native_transitions_verified': verified,
              'summary_verified': report['summary'], 'rows': rows,
              'scope': 'exposed post-result diagnosis; same adapters, not independent judge; no new capability trial'}
    with output.open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))


if __name__ == '__main__':
    run(Path(sys.argv[1]), Path(sys.argv[2]))
