"""Fresh larger-cardinality planning trial; partition ON/OFF, same experiences."""
import argparse
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
from scripts.representation_r3_dev import configuration, make_goal, native_success
from scripts.representation_r1_dev import SCHEMA
from scripts.representation_r1_eval import source_hashes, save, sha
from packages.action_core.episode import encode_config
from packages.action_core.world import Sandbox
from packages.shared_world.runtime import WorldSession, verify_world
from packages.shared_world.worker import Client
from packages.shared_world.experiment import native_cpu_seconds


def run(prereg, output):
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        raise RuntimeError('commit candidate and registration first')
    p = json.loads(prereg.read_text())
    if source_hashes() != p['source_hashes']:
        raise RuntimeError('source binding mismatch')
    training = ROOT / 'evidence/r3-training'
    if any(sha(training / name) != value for name, value in p['training_hashes'].items()):
        raise RuntimeError('training binding mismatch')
    save(prereg.with_suffix('.attempt.json'), {'output': str(output), 'started': time.time(), 'prereg_sha256': sha(prereg)})
    output.mkdir(parents=True, exist_ok=False)
    native_root = Path(tempfile.mkdtemp(prefix='atanor_r3_fresh_'))
    models = {arm: json.loads((training / f'{arm}.json').read_text()) for arm in ('on', 'off')}
    rng, rows = random.Random(p['seed']), []
    start = time.perf_counter()
    with (output / 'rows.jsonl').open('x') as stream:
        for block in range(p['blocks']):
            if time.time() >= p['deadline_unix']:
                raise TimeoutError('hard cap; no retry')
            count = 4 + block % 2
            seed = rng.getrandbits(60)
            payload = rng.randbytes(rng.randint(53, 511))
            goals = [False, True]
            rng.shuffle(goals)
            for collective in goals:
                arms = ['on', 'off']
                rng.shuffle(arms)
                for arm in arms:
                    ordinal = len(rows)
                    cfg, aliases, reference, _ = configuration(count, seed, payload=payload)
                    body = Sandbox(native_root / f'case_{ordinal:03d}', **cfg)
                    goal = make_goal(body, aliases, collective)
                    case = output / f'case_{ordinal:03d}'
                    case.mkdir()
                    db = case / 'world.sqlite'
                    world_id = f'r3-{ordinal}'
                    parent_start = time.process_time()
                    client = Client('relational', frozen=True, schema=SCHEMA, horizon=2, width=8, limit=32768)
                    world = None
                    try:
                        client.restore(models[arm])
                        world = WorldSession(db, body, client, config=cfg, total_budget=2,
                                             world_id=world_id, self_id='r3-research')
                        world.issue_goal(goal, 2)
                        result = world.run_goal()
                        state = world.state
                    finally:
                        if world is not None:
                            world.close()
                        client.close()
                    cpu = native_cpu_seconds(client.process)
                    parent_cpu = time.process_time() - parent_start
                    success = native_success(body, aliases, reference, payload, collective)
                    verifier_start = time.process_time()
                    verified = verify_world(db, expected_config=cfg, expected_total_budget=2,
                                            expected_world_id=world_id, expected_self_id='r3-research',
                                            expected_goals=[(goal, 2)])
                    row = {'block': block, 'arm': arm, 'collective': collective, 'aliases_count': count,
                           'config': encode_config(cfg), 'goal': goal.to_dict(), 'aliases': aliases,
                           'reference': reference, 'native_root': str(body.root), 'database': str(db),
                           'world_id': world_id, 'native_success': success, 'result': result,
                           'steps': state['steps'], 'halted': state['halted'], 'replay': verified,
                           'frozen_inner': state['model']['model'] == models[arm],
                           'worker_cpu': cpu, 'parent_cpu': parent_cpu,
                           'verification_cpu': time.process_time() - verifier_start}
                    rows.append(row)
                    stream.write(json.dumps(row, sort_keys=True) + '\n')
                    stream.flush()
                    os.fsync(stream.fileno())
            print(f'finished block {block+1}/{p["blocks"]}', flush=True)
    summary = {}
    for arm in ('on', 'off'):
        part = [r for r in rows if r['arm'] == arm]
        summary[arm] = {'n': len(part), 'successes': sum(r['native_success'] for r in part),
            'collective_successes': sum(r['native_success'] for r in part if r['collective']),
            'selective_successes': sum(r['native_success'] for r in part if not r['collective']),
            'actions': sum(r['steps'] for r in part), 'worker_cpu': sum(r['worker_cpu'] for r in part),
            'parent_cpu': sum(r['parent_cpu'] for r in part),
            'verification_cpu': sum(r['verification_cpu'] for r in part)}
    differences = [sum((1 if r['arm'] == 'on' else -1) * r['native_success']
                        for r in rows if r['block'] == b) / 2 for b in range(p['blocks'])]
    rng = random.Random(p['bootstrap_seed'])
    boot = sorted(sum(rng.choice(differences) for _ in differences) / len(differences)
                  for _ in range(10000))
    delta, lcb = sum(differences) / len(differences), boot[500]
    gates = {'native_replay_all': all(r['replay']['green'] for r in rows),
             'frozen_inner_all': all(r['frozen_inner'] for r in rows),
             'budget_no_halt': all(r['steps'] <= 2 and not r['halted'] for r in rows),
             'on_success': summary['on']['successes'] / summary['on']['n'] >= .9,
             'success_lift': delta >= .3, 'lcb95': lcb >= .2,
             'selective_no_regression': summary['on']['selective_successes'] >= summary['off']['selective_successes'],
             'action_count_not_worse': summary['on']['actions'] <= summary['off']['actions'],
             'source_unchanged': source_hashes() == p['source_hashes'],
             'training_unchanged': all(sha(training / name) == value for name, value in p['training_hashes'].items())}
    report = {'verdict': 'R3_CAPABILITY_GREEN' if all(gates.values()) else 'R3_CAPABILITY_RED',
              'gates': gates, 'scores': summary, 'success_lift': delta, 'paired_lcb95': lcb,
              'wall_seconds': time.perf_counter() - start, 'prereg_sha256': sha(prereg),
              'rows_sha256': sha(output / 'rows.jsonl'),
              'scope': 'larger cardinalities of the same native relation mechanics, not new mechanics'}
    save(output / 'report.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prereg', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.prereg.resolve(), args.output.resolve())
