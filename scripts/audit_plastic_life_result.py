"""Post-result raw readout only; no candidate rerun, tuning or revised thresholds."""
import hashlib
import json
from pathlib import Path
import sys


def audit(path):
    report = json.loads((path/'report.json').read_text())
    rows = [json.loads(line) for line in (path/'tasks.jsonl').read_text().splitlines()]
    assert len(rows) == 144
    seen = set()
    totals, diagnostics = {}, {}
    for row in rows:
        key = row['life'], row['age'], row['arm'], row['task']
        assert key not in seen
        seen.add(key)
        trace = row['trace']
        assert len(trace) == row['actions'] and len(trace) <= 32
        assert trace  # this realized cohort had no already-satisfied starts
        for left, right in zip(trace, trace[1:]):
            assert left['after'] == right['before']
        success = trace[-1]['after']['kinds'] == row['goal']
        assert success == row['success']
        assert row['penalized_actions'] == (len(trace) if success else 33)
    for arm in ('fresh', 'passive', 'developing'):
        for age in (0, 256, 1024):
            cohort = [r for r in rows if (r['arm'], r['age']) == (arm, age)]
            key = f'{arm}-{age}'
            assert len(cohort) == 16
            total = dict(success=sum(r['success'] for r in cohort), count=16,
                         mean_penalized_actions=sum(r['penalized_actions'] for r in cohort)/16,
                         actual_actions=sum(r['actions'] for r in cohort),
                         cpu_seconds=sum(r['cpu_seconds'] for r in cohort))
            assert total == report['totals'][key]
            totals[key] = total
            events = [e for r in cohort for e in r['trace']]
            diagnostics[key] = dict(
                unchanged=sum(e['before']['kinds']==e['after']['kinds'] for e in events),
                whole_state_argmax_correct=sum([max(range(3), key=lambda k:p[k]) for p in e['predicted_kinds']]
                                              == e['after']['kinds'] for e in events),
                transitions=len(events))
    training_count = sum(len(json.loads(p.read_text())) for p in path.glob('life-*.json'))
    assert training_count == 8192
    assert training_count+sum(r['actions'] for r in rows) == report['native_steps_verified']
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in report['hashes'].items())
    artifact_hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(path.iterdir()) if p.is_file() and p.name!='audit.json'}
    result = dict(raw_count_audit='PASS', totals=totals, diagnostics=diagnostics,
                  real_training_actions=training_count, native_verified=report['native_steps_verified'],
                  artifact_sha256=artifact_hashes,
                  caveat='Same mechanics across ages; improved learned model is not established improved learning algorithm.')
    with (path/'audit.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    print(json.dumps(dict(raw_count_audit='PASS', diagnostics=diagnostics)))


if __name__ == '__main__':
    audit(Path(sys.argv[1]))
