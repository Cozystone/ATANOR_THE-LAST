"""Single exposed OLD-operation readiness run for the schema-bound candidate.

Reuses the archived 480 actual transitions, independently native-replays them,
then trains once. No rename result is learned, planned, scored, or selected here.
All four arms can access the identical historical observations. The embedding
format is explicitly retrained; historical checkpoints are not silently loaded.
"""
from __future__ import annotations

import os
for _key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[_key] = '1'

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import tempfile
import time

from .dev import make_case
from .episode import Episode, canonical, digest, verify_episode
from .fresh_eval import process_cpu, sources, write_new
from .model import Learner
from .retrieval import Retrieval
from .schema import BASE_SCHEMA, TRANSFER_SCHEMA
from .worker import Client
from .world import Action, Frame, Sandbox

ARMS = ('warm', 'retrieval', 'cold_memory', 'warm_frozen')
PLAN = {'horizon': 2, 'width': 2, 'limit': 4096, 'cover_root': True, 'uncertainty_weight': 0}


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def training_rows(path, expected_sha):
    if file_hash(path) != expected_sha:
        raise ValueError('training file differs from independently bound archive')
    rows = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]
    if len(rows) != 480:
        raise ValueError('expected exactly archived 480 old-operation transitions')
    for i, row in enumerate(rows):
        if set(row) != {'id', 'before', 'action', 'success', 'after', 'history'}:
            raise ValueError('unexpected training fields')
        if row['id'] != f'dev-train-{i // 12}-{i % 12}' or type(row['success']) is not bool:
            raise ValueError('historical record identity or status mismatch')
        BASE_SCHEMA.index(Action.from_dict(row['action']))
        for _, action in row['history']:
            BASE_SCHEMA.index(Action.from_dict(action))
    return rows


def replay_training(rows):
    """Before fitting, re-execute old native transitions, including failed calls."""
    with tempfile.TemporaryDirectory(prefix='atanor-transfer-old-replay-') as temp:
        for episode in range(40):
            config, _ = make_case(10000 + episode, training=True)
            body = Sandbox(Path(temp) / f'old-{episode}', **config)
            rng, history = random.Random(20000 + episode), []
            for step in range(12):
                row = rows[episode * 12 + step]
                before, action = body.observe(), rng.choice(body.actions())
                if (row['before'] != before.to_dict() or row['action'] != action.to_dict() or
                        row['history'] != [[f.to_dict(), a.to_dict()] for f, a in history]):
                    raise ValueError('old training observation/action/history native mismatch')
                success = body.step(action)
                after = body.observe()
                if success != row['success'] or after.to_dict() != row['after']:
                    raise ValueError('old training consequence native mismatch')
                history = (history + [(before, action)])[-3:]
    return len(rows)


def make_checkpoints(rows):
    model = Learner(seed=2101, updates=3, change_balanced=True, latest_update=True,
                    schema=TRANSFER_SCHEMA)
    initial = model.snapshot()
    retrieval = Retrieval(schema=TRANSFER_SCHEMA)
    cpu = {'warm': 0., 'retrieval': 0.}
    for row in rows:
        BASE_SCHEMA.index(Action.from_dict(row['action']))
        args = (row['id'], Frame.from_dict(row['before']), Action.from_dict(row['action']),
                Frame.from_dict(row['after']),
                [(Frame.from_dict(f), Action.from_dict(a)) for f, a in row['history']])
        for name, learner in (('warm', model), ('retrieval', retrieval)):
            started = time.process_time()
            learner.learn(*args)
            cpu[name] += time.process_time() - started
    warm = model.snapshot()
    # No gradients ever addressed the new row: the new effect remains unlearned.
    row_keys = [k for k in warm['weights'] if k.endswith('operation.weight')]
    if any(warm['weights'][key][4] != initial['weights'][key][4] for key in row_keys):
        raise ValueError('unexperienced operation embedding changed during base training')
    # Exactly the same actual replay/seen/revision and sampling RNG, but no base
    # weight fitting. This is NOT a no-experience cold baseline.
    cold = copy.deepcopy(warm)
    cold['weights'] = copy.deepcopy(initial['weights'])
    frozen = copy.deepcopy(warm)
    frozen['updates'] = 0
    states = {'warm': warm, 'retrieval': retrieval.snapshot(),
              'cold_memory': cold, 'warm_frozen': frozen}
    return states, {'base_training_cpu_seconds': cpu,
                    'parameters': sum(p.numel() for p in model.members.parameters()),
                    'new_operation_embedding_unchanged': True,
                    'actual_base_records': len(rows)}


def run(training, expected_training_sha, output):
    # No fresh new-operation function exists in this development module.
    rows = training_rows(training, expected_training_sha)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    frozen_sources = sources()
    write_new(output / 'attempt.lock', {'scope': 'old-operation DEV only',
                                      'training_sha256': expected_training_sha})
    replayed = replay_training(rows)
    states, info = make_checkpoints(rows)
    for arm, state in states.items():
        write_new(output / (arm + '.json'), state)
    results, clients, startup = [], {}, {}
    try:
        for arm in ARMS:
            p, w = time.process_time(), time.perf_counter()
            client = Client(seed=2101, schema=TRANSFER_SCHEMA, **PLAN)
            clients[arm] = client
            startup[arm] = {'cpu_seconds': time.process_time() - p + process_cpu(client),
                            'wall_seconds': time.perf_counter() - w}
        with tempfile.TemporaryDirectory(prefix='atanor-transfer-old-dev-') as temp:
            for case in range(8):
                config, goal = make_case(30000 + case)
                order = ARMS[case % 4:] + ARMS[:case % 4]
                for arm in order:
                    client = clients[arm]
                    p, worker, w = time.process_time(), process_cpu(client), time.perf_counter()
                    client.restore(states[arm])
                    if digest(client.snapshot()) != digest(states[arm]):
                        raise ValueError('checkpoint restore changed state')
                    body = Sandbox(Path(temp) / f'{case}-{arm}', **config)
                    if any(a.op == 'rename' for a in body.actions()):
                        raise ValueError('DEV may not expose new-operation outcomes')
                    db = output / f'case-{case:02d}-{arm}.sqlite'
                    episode = Episode(db, body, goal, client, config=config, budget=8)
                    try:
                        stop = episode.run()
                    finally:
                        episode.close()
                    after = client.snapshot()
                    if arm == 'warm_frozen' and after['weights'] != states[arm]['weights']:
                        raise ValueError('frozen weights changed')
                    verified = verify_episode(db, expected_config=config, expected_goal=goal, expected_budget=8)
                    if not verified['green'] or verified['completed'] != stop['completed']:
                        raise ValueError('native DEV replay failed')
                    results.append({'case': case, 'arm': arm, 'success': bool(stop['completed']),
                        'charged_steps': stop['steps'] if stop['completed'] else 8,
                        'cpu_seconds': time.process_time() - p + process_cpu(client) - worker,
                        'wall_seconds': time.perf_counter() - w, 'replay': verified,
                        'stop': stop, 'sqlite_sha256': file_hash(db)})
                print(f'old-operation DEV {case + 1}/8 (no new effects)', flush=True)
    finally:
        for client in clients.values():
            client.close()
    if sources() != frozen_sources or file_hash(training) != expected_training_sha:
        raise ValueError('source or historical training mutated during DEV')
    totals = {arm: {'successes': sum(r['success'] for r in results if r['arm'] == arm),
                    'charged_steps': sum(r['charged_steps'] for r in results if r['arm'] == arm),
                    'cpu_seconds': sum(r['cpu_seconds'] for r in results if r['arm'] == arm) + startup[arm]['cpu_seconds']}
              for arm in ARMS}
    receipt = {'status': 'DEV_ONLY', 'capability_claim': False, 'new_effects_exposed': 0,
               'native_old_training_replayed': replayed, 'sources': frozen_sources,
               'training_sha256': expected_training_sha, 'base': info,
               'checkpoint_sha256': {arm: file_hash(output / (arm + '.json')) for arm in ARMS},
               'startup': startup, 'totals': totals, 'rows': results}
    receipt['readiness'] = bool(totals['warm']['successes'] >= 6 and len(results) == 32 and
                               all(r['replay']['green'] for r in results))
    write_new(output / 'receipt.json', receipt)
    print(canonical({k: receipt[k] for k in ('status', 'capability_claim', 'new_effects_exposed', 'base', 'totals')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--training', required=True)
    parser.add_argument('--expected-training-sha', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.training, args.expected_training_sha, args.output)
