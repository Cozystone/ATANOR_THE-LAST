"""One observed-revisit DEV candidate; uses already exposed data, never fresh."""
import os
for _variable in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[_variable] = '1'

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import time
import zipfile

from .dev import make_case, source_hashes
from .episode import canonical, digest, encode_config
from .fresh_eval import decode
from .life_dev import load_base, PLANNING
from .model import Learner
from .planner import Goal, choose
from .storage import require_space
from .world import Sandbox, Action


def hash_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(source, exposed, output):
    source, exposed, output = Path(source), Path(exposed), Path(output)
    require_space(output)
    output.mkdir(parents=True, exist_ok=False)
    sources = source_hashes()
    base = load_base(source / 'model.json')
    exposed_hash = hash_file(exposed)
    cohort = []
    for index in range(8):
        config, goal = make_case(30000 + index)
        cohort.append(('original_dev', index, config, goal))
    for row in json.loads(exposed.read_text())['cases']:
        cohort.append(('exposed_v2', row['case'], decode(row['config']), Goal.from_dict(row['goal'])))
    assert len(cohort) == 72
    with (output / 'prerun.json').open('x') as file:
        file.write(canonical({'status': 'EXPOSED_DEV_ONLY', 'base_digest': digest(base),
            'sources': sources, 'exposed_dataset_sha256': exposed_hash,
            'conditions': [0, .1], 'planning': PLANNING, 'actual_budget': 8,
            'cohort': [{'cohort': c, 'case': i, 'config': encode_config(config), 'goal': goal.to_dict()}
                       for c, i, config, goal in cohort]}))
    rows = []
    with tempfile.TemporaryDirectory(prefix='atanor-revisit-dev-') as temp, (output / 'raw.jsonl').open('x') as raw:
        for ordinal, (label, index, config, goal) in enumerate(cohort):
            for weight in ((0, .1) if ordinal % 2 == 0 else (.1, 0)):
                cpu, wall = time.process_time(), time.perf_counter()
                model = Learner.restore(base)
                body = Sandbox(Path(temp) / f'{label}-{index}-{weight}', **config)
                initial = body.evidence()
                events, history = [], []
                for step in range(8):
                    if goal.holds(body.evidence()):
                        break
                    before = body.observe()
                    action, forecast, nodes = choose(model, before, goal, body.actions(), history,
                        revisit_weight=weight, **PLANNING)
                    operated = body.step(action)
                    after, evidence = body.observe(), body.evidence()
                    assert model.learn(f'{label}-{index}-{step}', before, action, after, history)
                    events.append({'before': before.to_dict(), 'action': action.to_dict(),
                        'forecast': forecast.to_dict(), 'nodes': nodes,
                        'operation_success': operated, 'after': after.to_dict(), 'evidence': evidence,
                        'no_change': before == after})
                    history = (history + [(before, action)])[-3:]
                success = goal.holds(body.evidence())
                assert all(body.evidence()[h] == initial[h] for h in config['protected'])
                cpu_elapsed, wall_elapsed = time.process_time() - cpu, time.perf_counter() - wall
                replay = Sandbox(Path(temp) / f'replay-{label}-{index}-{weight}', **config)
                for event in events:
                    assert replay.observe().to_dict() == event['before']
                    assert replay.step(Action.from_dict(event['action'])) is event['operation_success']
                    assert replay.observe().to_dict() == event['after']
                    assert replay.evidence() == event['evidence']
                assert goal.holds(replay.evidence()) is success
                row = {'cohort': label, 'case': index, 'weight': weight, 'success': success,
                    'actual_steps': len(events), 'charged_steps': len(events) if success else 8,
                    'no_change_actions': sum(e['no_change'] for e in events),
                    'cpu_seconds': cpu_elapsed, 'wall_seconds': wall_elapsed,
                    'native_replay': True, 'events': events}
                raw.write(canonical(row) + '\n')
                raw.flush()
                rows.append(row)
            if (ordinal + 1) % 8 == 0:
                require_space(output, minimum_bytes=4 * 1024**3)
                print(f'observed-revisit DEV {ordinal + 1}/72', flush=True)
    assert sources == source_hashes() and exposed_hash == hash_file(exposed)
    totals = {}
    for label in ('original_dev', 'exposed_v2'):
        totals[label] = {}
        for weight in (0, .1):
            selected = [r for r in rows if r['cohort'] == label and r['weight'] == weight]
            totals[label][str(weight)] = {'cases': len(selected),
                'successes': sum(r['success'] for r in selected),
                'charged_steps': sum(r['charged_steps'] for r in selected),
                'no_change_actions': sum(r['no_change_actions'] for r in selected),
                'cpu_seconds': sum(r['cpu_seconds'] for r in selected)}
    old, new = totals['original_dev'], totals['exposed_v2']
    ready = (old['0.1']['successes'] >= old['0']['successes'] and
             new['0.1']['successes'] >= new['0']['successes'] and
             new['0.1']['charged_steps'] <= .9 * new['0']['charged_steps'])
    report = {'status': 'DEV_READY' if ready else 'DEV_NO_GO', 'capability_claim': False,
        'totals': totals, 'native_replays_verified': len(rows), 'source_bindings_unchanged': True,
        'raw_sha256': hash_file(output / 'raw.jsonl'),
        'limitations': ['both cohorts are exposed development data', 'one preselected soft-cost candidate',
            'in-process CPU, not comparable to whole-worker fresh CPU',
            'no new mechanics, learned law, stochastic-retry guarantee, or fresh capability claim']}
    with (output / 'report.json').open('x') as file:
        json.dump(report, file, indent=2)
    with zipfile.ZipFile(output / 'source.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(Path(__file__).parent.rglob('*.py')):
            archive.write(path, path.relative_to(Path(__file__).resolve().parents[2]))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--exposed', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.source, args.exposed, args.output)
