"""One locked fresh-configuration utility evaluation; no external-judge claim."""
from __future__ import annotations

import os
for _key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[_key] = '1'

import argparse
import copy
import hashlib
import json
from pathlib import Path
import platform
import random
import secrets
import sqlite3
import tempfile
import time
import zipfile

import numpy as np
import psutil
import torch

from .ablate import retrieval_from
from .episode import Episode, canonical, digest, encode_config, verify_episode
from .eval_metrics import summarize
from .model import Learner
from .planner import Goal
from .worker import Client
from .world import Sandbox

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / 'docs/ATANOR_ACTION_CORE_FRESH_PROTOCOL_2026-09-11.md'
ARMS = ('neural', 'retrieval', 'cold', 'frozen')


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    return {p.relative_to(ROOT).as_posix(): file_hash(p)
            for p in sorted(Path(__file__).parent.rglob('*.py'))}


def write_new(path, obj):
    with Path(path).open('x', encoding='utf-8') as out:
        out.write(canonical(obj))


def decode(config):
    return {'paths': config['paths'], 'initial': {k: bytes.fromhex(v) if v is not None else None
            for k, v in config['initial'].items()}, 'protected': set(config['protected'])}


def new_cases(seed):
    rng, result = random.Random(seed), []
    for index in range(64):
        stratum = index // 16
        n = rng.randrange(6, 8) if stratum in (1, 3) else rng.randrange(4, 6)
        size = rng.randrange(64, 1025) if stratum in (2, 3) else rng.randrange(3, 26)
        names = [f'x{rng.getrandbits(64):016x}' for _ in range(n)]
        ref, parent, target = names[0], names[1], names[1] + '/' + names[2]
        paths = [ref, parent, target] + names[3:]
        rng.shuffle(paths)
        payload = rng.randbytes(size)
        initial = {ref: payload}
        if index % 2:
            initial[parent] = None
            if rng.random() < .5:
                initial[target] = b'not-the-reference:' + payload
        for name in names[3:]:
            if rng.random() < .5:
                initial[name] = rng.choice((None, b'', payload[:1]))
        source_handle, target_handle = f'n{paths.index(ref)}', f'n{paths.index(target)}'
        config = {'paths': paths, 'initial': initial, 'protected': {source_handle}}
        goal = Goal(f'fresh-{index}', ((target_handle, 1),), ((source_handle, target_handle),))
        result.append({'case': index, 'stratum': stratum, 'missing_parent': not index % 2,
                       'config': encode_config(config), 'goal': goal.to_dict()})
    return result


def prepare(source, output):
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    frozen_sources = sources()
    neural = json.loads((source / 'model.json').read_text(encoding='utf-8'))
    neural['algorithm'] = 'neural'  # Metadata only; weights identical to DEV4.
    cold = Learner(seed=2101, change_balanced=True, latest_update=True).snapshot()
    frozen = copy.deepcopy(neural)
    frozen['updates'] = 0
    checkpoints = {'neural': neural, 'retrieval': retrieval_from(source / 'training.jsonl').snapshot(),
                   'cold': cold, 'frozen': frozen}
    for name, state in checkpoints.items():
        write_new(output / (name + '.json'), state)
    seed = secrets.randbits(63)
    write_new(output / 'dataset.json', {'seed': seed, 'cases': new_cases(seed)})
    with zipfile.ZipFile(output / 'source.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in frozen_sources:
            archive.write(ROOT / relative, relative)
        archive.write(PROTOCOL, PROTOCOL.relative_to(ROOT).as_posix())
    bindings = {name: file_hash(output / name) for name in
                ('dataset.json', 'source.zip', *(arm + '.json' for arm in ARMS))}
    prereg = {'schema': 1, 'cases': 64, 'arms': list(ARMS), 'seed': seed,
        'sources': frozen_sources, 'bindings': bindings, 'protocol_sha256': file_hash(PROTOCOL),
        'original_checkpoint_sha256': file_hash(source / 'model.json'),
        'original_training_sha256': file_hash(source / 'training.jsonl'),
        'budget': {'horizon': 2, 'width': 2, 'limit': 4096, 'cover_root': True, 'uncertainty_weight': 0},
        'actual_step_budget': 8, 'bootstrap_seed': 44113, 'bootstrap_draws': 4000,
        'versions': {'python': platform.python_version(), 'torch': torch.__version__, 'numpy': np.__version__}}
    if sources() != frozen_sources:
        raise ValueError('source changed during preparation')
    write_new(output / 'preregistration.json', prereg)
    print(json.dumps({'prepared': str(output.resolve()), 'prereg_sha256': file_hash(output / 'preregistration.json'),
                      'cases': 64, 'capability_run_started': False}))


def check_binding(output, prereg):
    if sources() != prereg['sources'] or file_hash(PROTOCOL) != prereg['protocol_sha256']:
        raise ValueError('source/protocol binding mismatch')
    for name, sha in prereg['bindings'].items():
        if name not in ('dataset.json', 'source.zip', *(arm + '.json' for arm in ARMS)):
            raise ValueError('unexpected bound artifact')
        if file_hash(output / name) != sha:
            raise ValueError('artifact binding mismatch: ' + name)
    with zipfile.ZipFile(output / 'source.zip') as archive:
        for relative, sha in prereg['sources'].items():
            if hashlib.sha256(archive.read(relative)).hexdigest() != sha:
                raise ValueError('source archive binding mismatch')


def process_cpu(client):
    cpu = psutil.Process(client.process.pid).cpu_times()
    return cpu.user + cpu.system


def run(output, expected_prereg_sha):
    output = Path(output).resolve()
    prereg = json.loads((output / 'preregistration.json').read_text(encoding='utf-8'))
    prereg_sha = file_hash(output / 'preregistration.json')
    if prereg_sha != expected_prereg_sha:
        raise ValueError('out-of-band preregistration digest mismatch')
    check_binding(output, prereg)
    # Irreversible attempt marker, even if execution later errors. No retry.
    write_new(output / 'attempt.lock', {'started_unix': time.time(), 'prereg_sha256': prereg_sha})
    clients, startup, rows = {}, {}, []
    started = time.perf_counter()
    receipt = {'status': 'INVALID', 'capability_claim': False, 'prereg_sha256': prereg_sha}
    try:
        dataset = json.loads((output / 'dataset.json').read_text(encoding='utf-8'))['cases']
        if len(dataset) != 64 or [r['case'] for r in dataset] != list(range(64)):
            raise ValueError('wrong cohort')
        bases = {a: json.loads((output / (a + '.json')).read_text(encoding='utf-8')) for a in ARMS}
        for arm in ARMS:
            p, w = time.process_time(), time.perf_counter()
            clients[arm] = Client(seed=2101, timeout=60, **prereg['budget'])
            startup[arm] = {'parent_cpu': time.process_time() - p, 'worker_cpu': process_cpu(clients[arm]),
                            'wall': time.perf_counter() - w}
        with tempfile.TemporaryDirectory(prefix='atanor-fresh-eval-') as temp, (output / 'raw.jsonl').open('x', encoding='utf-8') as raw:
            for case in dataset:
                order = ARMS[case['case'] % 4:] + ARMS[:case['case'] % 4]
                for arm in order:
                    client = clients[arm]
                    p, w, wall = time.process_time(), process_cpu(client), time.perf_counter()
                    client.restore(bases[arm])
                    restored = client.snapshot()
                    if digest(restored) != digest(bases[arm]):
                        raise ValueError('base checkpoint restoration mismatch')
                    config, goal = decode(case['config']), Goal.from_dict(case['goal'])
                    body = Sandbox(Path(temp) / f'{case["case"]}-{arm}', **config)
                    if goal.holds(body.evidence()):
                        raise ValueError('initially solved case')
                    db = output / f'case-{case["case"]:03d}-{arm}.sqlite'
                    episode = Episode(db, body, goal, client, config=config, budget=8)
                    try:
                        stop = episode.run()
                    finally:
                        episode.close()
                    checkpoint = client.snapshot()
                    elapsed_cpu = time.process_time() - p + process_cpu(client) - w
                    elapsed_wall = time.perf_counter() - wall
                    if stop['reason'] not in ('goal_reached', 'step_budget_exceeded'):
                        raise ValueError('invalid execution termination: ' + stop['reason'])
                    if arm == 'frozen' and checkpoint['weights'] != bases[arm]['weights']:
                        raise ValueError('frozen weights changed')
                    verified = verify_episode(db, expected_config=config, expected_goal=goal, expected_budget=8)
                    if not verified['green'] or verified['completed'] != stop['completed']:
                        raise ValueError('independent native replay failed: ' + str(verified))
                    row = {'case': case['case'], 'arm': arm, 'success': bool(stop['completed']),
                        'charged_steps': stop['steps'] if stop['completed'] else 8, 'cpu_seconds': elapsed_cpu,
                        'stratum': case['stratum'], 'missing_parent': case['missing_parent'],
                        'wall_seconds': elapsed_wall, 'stop': stop, 'replay': verified,
                        'checkpoint_before': digest(restored), 'checkpoint_after': digest(checkpoint),
                        'worker_sampled_rss_bytes': psutil.Process(client.process.pid).memory_info().rss,
                        'sqlite_sha256': file_hash(db)}
                    raw.write(canonical(row) + '\n')
                    raw.flush()
                    rows.append(row)
                if (case['case'] + 1) % 8 == 0:
                    print(f'fresh evaluation {case["case"] + 1}/64 (results withheld)', flush=True)
        check_binding(output, prereg)
        if file_hash(output / 'preregistration.json') != prereg_sha:
            raise ValueError('preregistration changed')
        metric_rows = [{k: row[k] for k in ('case', 'arm', 'success', 'charged_steps', 'cpu_seconds')} for row in rows]
        metrics = summarize(metric_rows, seed=44113, draws=4000)
        strata = {str(s): {a: {'successes': sum(r['success'] for r in rows if r['stratum'] == s and r['arm'] == a),
                              'cases': 16} for a in ARMS} for s in range(4)}
        receipt.update(status=metrics['verdict'], metrics=metrics, strata=strata,
                       all_native_replays_verified=len(rows), bindings_unchanged=True,
                       raw_sha256=file_hash(output / 'raw.jsonl'),
                       capability_claim=metrics['verdict'] == 'LOCAL_UTILITY_CONFIRMED',
                       claim_scope='Fresh filesystem configurations: local learned-planning utility only; not new mechanics, AGI, or external E5')
    except Exception as error:
        receipt['error'] = type(error).__name__ + ': ' + str(error)
        receipt['completed_rows'] = len(rows)
    finally:
        for client in clients.values():
            client.close()
    receipt.update(startup=startup, wall_seconds=time.perf_counter() - started)
    write_new(output / 'receipt.json', receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k not in ('startup',)}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare', 'run'))
    parser.add_argument('--source')
    parser.add_argument('--output', required=True)
    parser.add_argument('--expected-prereg-sha')
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare(args.source, args.output)
    else:
        run(args.output, args.expected_prereg_sha)
