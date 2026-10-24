"""Read-only independent recomputation of R0 raw evidence; no candidate imports."""
import argparse
import hashlib
import json
from pathlib import Path


def check(output, prereg):
    p = json.loads(prereg.read_text())
    report = json.loads((output / 'report.json').read_text())
    rows = json.loads((output / 'rows.json').read_text())
    events = [json.loads(line) for line in (output / 'events.jsonl').read_text().splitlines()]
    assert len(rows) == 2 * (p['train_pairs'] + p['fresh_pairs'])
    assert len(events) == 2 * len(rows) + 1
    for filename, key in [('rows.json', 'rows_sha256'), ('events.jsonl', 'events_sha256')]:
        assert hashlib.sha256((output / filename).read_bytes()).hexdigest() == report[key]
    assert hashlib.sha256(prereg.read_bytes()).hexdigest() == report['prereg_sha256']
    trained = json.loads((output / 'trained.json').read_text())
    freeze_index = 4 * p['train_pairs']
    assert events[freeze_index]['event'] == 'training_frozen'
    assert events[freeze_index]['rule'] == trained['rule'] == report['selected_rule']
    mapping = report['supervisor_channel_mapping']
    train_ids, fresh_ids = set(), set()
    scores = {arm: 0 for arm in ('search', 'old_frame', 'selected_channel_removed')}
    for i, row in enumerate(rows):
        offset = 2 * i + (i >= 2 * p['train_pairs'])
        pre, post = events[offset:offset + 2]
        assert pre['event'] == 'pre_dispatch' and post['event'] == 'post_dispatch'
        assert pre['id'] == post['id'] == row['id']
        assert pre['raw'] == row['raw'] and pre['before'] == row['before']
        assert pre['prediction'] == row['prediction']
        assert {k: v for k, v in post.items() if k != 'event'} == row
        other = f"n{1-row['target']}"
        actual = row['before'][other]['sha256'] != row['after'][other]['sha256']
        assert actual == row['observed'] == row['setup_linked']
        for role, path in enumerate(row['native_paths']):
            payload = Path(path).read_bytes()
            assert hashlib.sha256(payload).hexdigest() == row['after'][f'n{role}']['sha256']
            assert len(payload) == row['after'][f'n{role}']['size_bytes']
        identifiers = train_ids if row['phase'] == 'train' else fresh_ids
        for values in row['raw']:
            identifiers.add((values[mapping.index('st_dev')], values[mapping.index('st_ino')]))
        if row['phase'] == 'fresh':
            for arm, rule_key in [('search', 'rule'), ('selected_channel_removed', 'ablated')]:
                rule = trained[rule_key]
                a, b = [v[rule['column']] for v in row['raw']]
                bit = {'eq': a == b, 'lt': a < b, 'le': a <= b}[rule['operator']]
                predicted = rule['predictions'][int(bit)]
                assert predicted == row['prediction'][arm]
            assert row['prediction']['old_frame'] == trained['old_default']
            for arm in scores:
                scores[arm] += row['prediction'][arm] == actual
        else:
            assert row['prediction'] is None
    for a, b in zip(rows[::2], rows[1::2]):
        assert (a['phase'], a['pair'], a['target']) == (b['phase'], b['pair'], b['target'])
        assert a['old_frame'] == b['old_frame'] and a['observed'] != b['observed']
    assert not train_ids & fresh_ids
    assert trained['rule']['column'] != trained['ablated']['column']
    assert scores == report['correct']
    assert report['fresh_n'] == 2 * p['fresh_pairs']
    acc = {key: n / report['fresh_n'] for key, n in scores.items()}
    assert acc == report['accuracy']
    root = Path(__file__).resolve().parents[1]
    for name, expected in report['source_hashes'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
    metric_pass = (acc['search'] >= p['min_accuracy'] and
                   acc['search'] - acc['old_frame'] >= p['min_lift'] and
                   acc['search'] - acc['selected_channel_removed'] >= p['min_lift'])
    assert (report['verdict'] == 'R0_FEASIBILITY_GREEN') == (metric_pass and all(report['gates'].values()))
    assert report['capability_claim'] is False and report['planning_integration'] is False
    return {'independent_raw_recomputation': 'PASS', 'rows': len(rows), 'correct': scores}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prereg', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.output, args.prereg), indent=2))
