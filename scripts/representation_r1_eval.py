"""One registered paired native planning trial. Not open-ended generality."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sqlite3
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.representation_r1_dev import config, SCHEMA, CHANNEL
from packages.action_core.episode import encode_config
from packages.action_core.planner import Goal
from packages.action_core.world import Sandbox
from packages.shared_world.experiment import native_cpu_seconds
from packages.shared_world.runtime import WorldSession, verify_world
from packages.shared_world.worker import Client


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')


def source_hashes():
    return {p.relative_to(ROOT).as_posix(): sha(p) for folder in ('packages', 'scripts')
            for p in sorted((ROOT / folder).rglob('*.py'))}


def metrics(rows, p):
    scores = {}
    for arm in ('on', 'off'):
        part = [r for r in rows if r['arm'] == arm]
        scores[arm] = {'n': len(part), 'successes': sum(r['native_success'] for r in part),
                      'collateral_cases': sum(r['collateral'] for r in part),
                      'actions': sum(r['steps'] for r in part),
                      'worker_os_cpu_seconds': sum(r['worker_cpu'] for r in part),
                      'parent_cpu_seconds': sum(r['parent_cpu'] for r in part),
                      'verification_parent_cpu_seconds': sum(r['verification_cpu'] for r in part),
                      'replay_valid': sum(r['replay']['green'] for r in part)}
    n = scores['on']['n']
    lifts = []
    for block in range(p['blocks']):
        part = [r for r in rows if r['block'] == block]
        lifts.append(sum((1 if r['arm'] == 'on' else -1) * r['native_success'] for r in part) / 2)
    rng = random.Random(p['bootstrap_seed'])
    samples = sorted(sum(rng.choice(lifts) for _ in lifts) / len(lifts)
                     for _ in range(p['bootstrap_replicates']))
    lcb = samples[int(.05 * len(samples))]
    delta = (scores['on']['successes'] - scores['off']['successes']) / n
    harm_delta = (scores['off']['collateral_cases'] - scores['on']['collateral_cases']) / n
    control = {arm: sum(r['native_success'] for r in rows if r['arm'] == arm and not r['linked'])
               for arm in ('on', 'off')}
    gates = {
        'native_replay_all': all(r['replay']['green'] for r in rows),
        'frozen_inner_all': all(r['frozen_inner'] for r in rows),
        'budget_and_no_halt': all(r['steps'] <= 2 and not r['halted'] for r in rows),
        'on_success': scores['on']['successes'] / n >= p['min_on_success'],
        'success_lift': delta >= p['min_lift'],
        'paired_lift_lcb': lcb >= p['min_lcb'],
        'on_collateral': scores['on']['collateral_cases'] / n <= p['max_on_collateral'],
        'collateral_reduction': harm_delta >= p['min_collateral_reduction'],
        'independent_control_no_regression': control['on'] >= control['off'],
        'relation_change_predicted': all(r['relation_effect_exact'] for r in rows if r['arm'] == 'on'),
    }
    return {'scores': scores, 'success_lift': delta, 'paired_lcb95': lcb,
            'collateral_reduction': harm_delta, 'control_successes': control, 'gates': gates}


def run(registration, output):
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        raise RuntimeError('commit candidate and preregistration first')
    p = json.loads(registration.read_text())
    source = source_hashes()
    if source != p['source_hashes']:
        raise RuntimeError('candidate source mismatch')
    training = ROOT / p.get('training_directory', 'evidence/r1-training')
    if any(sha(training / name) != expected for name, expected in p['training_hashes'].items()):
        raise RuntimeError('training binding mismatch')
    marker = registration.with_suffix('.attempt.json')
    save(marker, {'started': time.time(), 'output': str(output), 'prereg_sha256': sha(registration)})
    output.mkdir(parents=True, exist_ok=False)
    native_root = Path(tempfile.mkdtemp(prefix='atanor_r1_fresh_'))
    rng = random.Random(p['seed'])
    rows = []
    frozen = {arm: json.loads((training / f'{arm}.json').read_text()) for arm in ('on', 'off')}
    start = time.perf_counter()
    with (output / 'rows.jsonl').open('x', encoding='utf-8') as stream:
        for block in range(p['blocks']):
            if time.time() >= p['deadline_unix']:
                raise TimeoutError('registered hard cap reached; no retry')
            seed = rng.getrandbits(60)
            payload = rng.randbytes(rng.randint(53, 511))
            target = rng.randrange(2)
            conditions = [False, True]
            rng.shuffle(conditions)
            for linked in conditions:
                arms = ['on', 'off']
                rng.shuffle(arms)
                for arm in arms:
                    ordinal = len(rows)
                    case_dir = output / f'case_{ordinal:03d}'
                    case_dir.mkdir()
                    cfg, _ = config(seed, linked, payload=payload, on=arm == 'on', projection=p.get('projection'))
                    body = Sandbox(native_root / f'case_{ordinal:03d}', **cfg)
                    goal = Goal('empty-preserve', sizes=((f'n{target}', 0.),
                                 (f'n{1-target}', body.observe().sizes[1-target])))
                    world_id = f'r1-{ordinal}'
                    db = case_dir / 'world.sqlite'
                    parent_start = time.process_time()
                    client = Client(algorithm='relational', frozen=True, schema=SCHEMA,
                                    horizon=2, width=8, limit=8192)
                    world = None
                    try:
                        client.restore(frozen[arm])
                        world = WorldSession(db, body, client, config=cfg, total_budget=2,
                                             world_id=world_id, self_id='r1-research')
                        world.issue_goal(goal, 2)
                        result = world.run_goal()
                        state = world.state
                        model_unchanged = state['model']['model'] == frozen[arm]
                    finally:
                        if world is not None:
                            world.close()
                        client.close()
                    worker_cpu = native_cpu_seconds(client.process)
                    parent_cpu = time.process_time() - parent_start
                    paths = [body.root / name for name in cfg['paths']]
                    native_success = (paths[target].is_file() and paths[target].read_bytes() == b'' and
                                      paths[1-target].is_file() and paths[1-target].read_bytes() == payload and
                                      paths[2].read_bytes() == payload)
                    connection = sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True)
                    events = [(kind, json.loads(text)) for kind, text in
                              connection.execute('SELECT kind,payload FROM events ORDER BY seq')]
                    connection.close()
                    results = [event for kind, event in events if kind == 'RESULT']
                    collateral = any(event['evidence'][f'n{1-target}']['sha256'] != hashlib.sha256(payload).hexdigest()
                                     for event in results)
                    predictions = [event['prediction'] for kind, event in events if kind == 'PREDICT']
                    exact = True
                    if arm == 'on':
                        exact = all(all(outcome['state']['relations'] == actual['frame']['relations']
                                        for outcome in predicted['outcomes'])
                                    for predicted, actual in zip(predictions, results))
                        exact = exact and len(predictions) == len(results)
                    verification_start = time.process_time()
                    replay = verify_world(db, expected_config=cfg, expected_total_budget=2,
                                          expected_world_id=world_id, expected_self_id='r1-research',
                                          expected_goals=[(goal, 2)])
                    row = {'block': block, 'linked': linked, 'arm': arm, 'target': target,
                           'config': encode_config(cfg), 'goal': goal.to_dict(), 'world_id': world_id,
                           'database': str(db), 'native_root': str(body.root),
                           'native_success': bool(native_success), 'collateral': collateral,
                           'frozen_inner': model_unchanged, 'halted': state['halted'],
                           'steps': state['steps'], 'result': result, 'replay': replay,
                           'relation_effect_exact': exact, 'worker_cpu': worker_cpu, 'parent_cpu': parent_cpu,
                           'verification_cpu': time.process_time() - verification_start}
                    rows.append(row)
                    stream.write(json.dumps(row, sort_keys=True) + '\n')
                    stream.flush()
                    os.fsync(stream.fileno())
            print(f'finished block {block + 1}/{p["blocks"]}', flush=True)
    report = metrics(rows, p)
    report['gates']['source_unchanged'] = source == source_hashes()
    report['gates']['training_unchanged'] = all(sha(training / name) == value for name, value in p['training_hashes'].items())
    label = p.get('study_label', 'R1')
    report.update(verdict=label + ('_CAPABILITY_GREEN' if all(report['gates'].values()) else '_CAPABILITY_RED'),
                  scope='fresh instances of a single known aliasing mechanism, two-action task',
                  wall_seconds=time.perf_counter() - start, prereg_sha256=sha(registration),
                  rows_sha256=sha(output / 'rows.jsonl'))
    save(output / 'report.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prereg', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.prereg.resolve(), args.output.resolve())
