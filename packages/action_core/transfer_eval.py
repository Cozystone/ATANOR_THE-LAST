"""One locked native-new-effect run; prepare/run require root approval.

No new effect is used for model selection. Configurations are fresh, but the
developer knows the native operation: NOT an external-blind evaluation.
"""
from __future__ import annotations

import os
for _key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[_key] = '1'

import argparse
import copy
from datetime import datetime
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
import torch

from .episode import Episode, canonical, digest, encode_config, verify_episode
from .fresh_eval import process_cpu, sources, write_new
from .model import Learner
from .planner import Goal
from .retrieval import Retrieval
from .schema import BASE_SCHEMA, TRANSFER_SCHEMA
from .storage import require_space
from .transfer_dev import ARMS, PLAN, file_hash
from .transfer_metrics import summarize
from .worker import Client
from .world import Action, Sandbox

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / 'docs/TRANSFER_PROTOCOL.md'
CORE = ('model.py', 'schema.py', 'world.py', 'planner.py', 'retrieval.py', 'worker.py', 'episode.py')
DEADLINE_UTC = '2026-09-14T11:19:00+00:00'
DEADLINE_UNIX = datetime.fromisoformat(DEADLINE_UTC).timestamp()
MINIMUM_FREE_BYTES = 8 * 1024**3


def check_deadline(now=None):
    """Parent-approved 48h wall boundary, independent of learner/caller status."""
    if (time.time() if now is None else now) >= DEADLINE_UNIX:
        raise TimeoutError('48-hour hard cap reached: ' + DEADLINE_UTC)


def advance_episode(episode):
    # Candidate unchanged: enforce time externally before every step invocation,
    # including repeated actions and the final stop. Worker calls have a timeout.
    while episode.state['stop'] is None:
        check_deadline()
        episode.step()
    return episode.state['stop']


def decode(config):
    return {'paths': config['paths'],
            'initial': {k: bytes.fromhex(v) if v is not None else None for k, v in config['initial'].items()},
            'protected': set(config['protected']), 'operations': config['operations']}


def new_cases(seed):
    """Native filesystem initial conditions, no simulator or modeled effects."""
    rng, cases = random.Random(seed), []
    for index in range(64):
        stratum = index // 16
        n, missing_parent = 4 + (stratum // 2), bool(stratum % 2)
        names = [f'x{rng.getrandbits(64):016x}' for _ in range(n)]
        ref, source, parent = names[:3]
        target = parent + '/' + names[3]
        paths = [ref, source, parent, target] + names[4:]
        rng.shuffle(paths)
        payload = rng.randbytes(rng.randrange(32, 257))
        initial = {ref: payload, source: payload}
        if not missing_parent:
            initial[parent] = None
        if n == 5 and rng.random() < .5:
            initial[names[4]] = rng.choice((None, b'', b'unrelated'))
        rh, sh, th = (f'n{paths.index(p)}' for p in (ref, source, target))
        config = {'paths': paths, 'initial': initial, 'protected': {rh},
                  'operations': TRANSFER_SCHEMA.to_data()}
        goal = Goal(f'transfer-{index}', ((sh, 0), (th, 1)), ((rh, th),))
        cases.append({'case': index, 'stratum': stratum, 'objects': n, 'missing_parent': missing_parent,
                      'config': encode_config(config), 'goal': goal.to_dict()})
    order = list(range(64))
    rng.shuffle(order)
    rotations = [i % 4 for i in range(64)]
    rng.shuffle(rotations)
    schedule = [{'case': case, 'arms': list(ARMS[rotation:] + ARMS[:rotation])}
                for case, rotation in zip(order, rotations)]
    return {'seed': seed, 'cases': cases, 'schedule': schedule}


def checkpoint_controls(states):
    warm, cold, frozen, retrieval = (states[a] for a in ('warm', 'cold_memory', 'warm_frozen', 'retrieval'))
    for state in states.values():
        if state.get('schema') != TRANSFER_SCHEMA.to_data():
            raise ValueError('unequal or unknown public operation schema')
    for state in (warm, cold, frozen):
        restored = Learner.restore(state)
        if digest(restored.snapshot()) != digest(state):
            raise ValueError('base snapshot does not restore exactly')
    if digest(Retrieval.restore(retrieval).snapshot()) != digest(retrieval):
        raise ValueError('retrieval base does not restore exactly')
    initial = Learner(seed=2101, updates=3, change_balanced=True, latest_update=True,
                      schema=TRANSFER_SCHEMA).snapshot()
    if cold['weights'] != initial['weights']:
        raise ValueError('cold-memory weights are not the matched random initialization')
    if any(cold[k] != warm[k] for k in warm if k != 'weights'):
        raise ValueError('cold-memory actual replay, RNG or settings differ')
    if any(frozen[k] != warm[k] for k in warm if k != 'updates') or frozen['updates'] != 0:
        raise ValueError('warm-frozen is not an exact zero-update control')
    if (retrieval['rows'] != warm['replay'] or retrieval['seen'] != warm['seen'] or
            retrieval['revision'] != warm['revision'] or warm['revision'] != 480):
        raise ValueError('historical experience is not identical across arms')
    for row in warm['replay']:
        BASE_SCHEMA.index(Action.from_dict(row['action']))
        for _, action in row['history']:
            BASE_SCHEMA.index(Action.from_dict(action))
    for key in warm['weights']:
        if key.endswith('operation.weight') and warm['weights'][key][4] != cold['weights'][key][4]:
            raise ValueError('new operation was already fitted at base time')
    return {'matched_base_experience': True, 'cold_random_weights': True,
            'new_embedding_untrained': True, 'frozen_base_equal': True}


def prepare(dev, expected_dev_sha, output):
    """Freeze outputs once; caller must authorize before generating final inputs."""
    dev, output = Path(dev), Path(output)
    check_deadline()
    require_space(output, minimum_bytes=MINIMUM_FREE_BYTES)
    receipt_path = dev / 'receipt.json'
    if file_hash(receipt_path) != expected_dev_sha:
        raise ValueError('DEV receipt out-of-band digest mismatch')
    dev_receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    if (dev_receipt.get('readiness') is not True or dev_receipt['new_effects_exposed'] != 0 or
            dev_receipt['native_old_training_replayed'] != 480):
        raise ValueError('old-operation readiness was not established')
    frozen_sources = sources()
    for name in CORE:
        relative = 'packages/action_core/' + name
        if frozen_sources[relative] != dev_receipt['sources'][relative]:
            raise ValueError('candidate changed after OLD-only DEV: ' + name)
    states = {}
    for arm in ARMS:
        path = dev / (arm + '.json')
        if file_hash(path) != dev_receipt['checkpoint_sha256'][arm]:
            raise ValueError('DEV base checkpoint changed')
        states[arm] = json.loads(path.read_text(encoding='utf-8'))
    controls = checkpoint_controls(states)
    output.mkdir(parents=True, exist_ok=False)
    # Sources and learned bases fixed before random final configurations exist.
    with zipfile.ZipFile(output / 'source.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in frozen_sources:
            archive.write(ROOT / relative, relative)
        archive.write(PROTOCOL, 'docs/TRANSFER_PROTOCOL.md')
    for arm, state in states.items():
        write_new(output / (arm + '.json'), state)
    dataset = new_cases(secrets.randbits(63))
    write_new(output / 'dataset.json', dataset)
    bindings = {name: file_hash(output / name) for name in
                ('dataset.json', 'source.zip', *(arm + '.json' for arm in ARMS))}
    prereg = {'schema': 1, 'scope': 'developer-known native new effect, not external blind',
              'cases': 64, 'arms': list(ARMS), 'sources': frozen_sources,
              'bindings': bindings, 'protocol_sha256': file_hash(PROTOCOL),
              'dev_receipt_sha256': expected_dev_sha, 'base': dev_receipt['base'],
              'controls': controls, 'budget': PLAN, 'actual_step_budget': 8,
              'deadline_utc': DEADLINE_UTC, 'minimum_free_bytes': MINIMUM_FREE_BYTES,
              'bootstrap_seed': 58319, 'bootstrap_draws': 4000,
              'versions': {'python': platform.python_version(), 'torch': torch.__version__,
                           'numpy': np.__version__, 'platform': platform.platform()}}
    if sources() != frozen_sources:
        raise ValueError('source changed during preparation')
    write_new(output / 'preregistration.json', prereg)
    print(canonical({'prepared': str(output.resolve()), 'prereg_sha256': file_hash(output / 'preregistration.json'),
                     'capability_run_started': False}))


def check_binding(output, prereg):
    expected_names = {'dataset.json', 'source.zip', *(arm + '.json' for arm in ARMS)}
    if (prereg['cases'] != 64 or prereg['arms'] != list(ARMS) or prereg['budget'] != PLAN or
            prereg['actual_step_budget'] != 8 or prereg['bootstrap_seed'] != 58319 or
            prereg.get('deadline_utc') != DEADLINE_UTC or prereg.get('minimum_free_bytes') != MINIMUM_FREE_BYTES or
            prereg['bootstrap_draws'] != 4000 or set(prereg['bindings']) != expected_names):
        raise ValueError('fixed protocol fields differ')
    if sources() != prereg['sources'] or file_hash(PROTOCOL) != prereg['protocol_sha256']:
        raise ValueError('source/protocol binding changed')
    for name, sha in prereg['bindings'].items():
        if file_hash(output / name) != sha:
            raise ValueError('artifact binding mismatch: ' + name)
    with zipfile.ZipFile(output / 'source.zip') as archive:
        for relative, sha in prereg['sources'].items():
            if hashlib.sha256(archive.read(relative)).hexdigest() != sha:
                raise ValueError('source archive mismatch')
        if hashlib.sha256(archive.read('docs/TRANSFER_PROTOCOL.md')).hexdigest() != prereg['protocol_sha256']:
            raise ValueError('archived protocol mismatch')


def native_operation_trace(db):
    conn = sqlite3.connect('file:' + Path(db).resolve().as_posix() + '?mode=ro', uri=True)
    rows = [(seq, kind, json.loads(payload)) for seq, kind, payload in
            conn.execute('SELECT seq,kind,payload FROM events ORDER BY seq')]
    conn.close()
    proposals, trace, observed = {}, [], None
    for seq, kind, payload in rows:
        if kind == 'BEGIN':
            observed = payload['frame']
        elif kind == 'FORECAST':
            proposals[seq] = payload
        elif kind == 'RESULT':
            proposal = proposals[payload['forecast']]
            trace.append({'step': proposal['step'] + 1, 'action': proposal['action'],
                          'before': observed, 'forecast_before_action': proposal['forecast'],
                          'reported_revision_before': proposal['reported_revision'],
                          'native_success': payload['operation_success'],
                          'completed': payload['completed'], 'after': payload['frame'],
                          'evidence': payload['evidence'], 'observed_result_event': seq})
            observed = payload['frame']
    for index, event in enumerate(trace):
        following = trace[index + 1] if index + 1 < len(trace) else None
        event['next_selected_action'] = following['action'] if following else None
        event['next_selected_forecast'] = following['forecast_before_action'] if following else None
        event['next_reported_revision'] = following['reported_revision_before'] if following else None
    return trace


def run(output, expected_prereg_sha):
    output = Path(output).resolve()
    check_deadline()
    require_space(output, minimum_bytes=MINIMUM_FREE_BYTES)
    sha = file_hash(output / 'preregistration.json')
    if sha != expected_prereg_sha:
        raise ValueError('out-of-band preregistration digest mismatch')
    prereg = json.loads((output / 'preregistration.json').read_text(encoding='utf-8'))
    check_binding(output, prereg)
    states = {a: json.loads((output / (a + '.json')).read_text(encoding='utf-8')) for a in ARMS}
    controls = checkpoint_controls(states)
    dataset = json.loads((output / 'dataset.json').read_text(encoding='utf-8'))
    if dataset != new_cases(dataset['seed']):
        raise ValueError('cohort/schedule does not match frozen generator')
    # The lock consumes the only attempt before any target body/model action.
    write_new(output / 'attempt.lock', {'started_unix': time.time(), 'prereg_sha256': sha})
    started, parent_start = time.perf_counter(), time.process_time()
    receipt = {'status': 'INVALID', 'capability_claim': False, 'prereg_sha256': sha,
               'claim_scope': 'Local online adaptation on developer-known new-action-present tasks under rich given observations and permissions',
               'rename_specific_learning_cause_identified': False}
    clients, startup, rows, worker_final_cpu = {}, {}, [], {}
    try:
        for arm in ARMS:
            p, w = time.process_time(), time.perf_counter()
            client = Client(seed=2101, schema=TRANSFER_SCHEMA, timeout=120, **PLAN)
            clients[arm] = client
            startup[arm] = {'cpu_seconds': time.process_time() - p + process_cpu(client),
                            'wall_seconds': time.perf_counter() - w}
        with tempfile.TemporaryDirectory(prefix='atanor-native-transfer-final-') as temp, \
                (output / 'raw.jsonl').open('x', encoding='utf-8') as raw:
            for presentation, scheduled in enumerate(dataset['schedule']):
                check_deadline()
                require_space(output, minimum_bytes=MINIMUM_FREE_BYTES)
                case = dataset['cases'][scheduled['case']]
                for arm in scheduled['arms']:
                    client = clients[arm]
                    p, worker, w = time.process_time(), process_cpu(client), time.perf_counter()
                    client.restore(states[arm])
                    restored = client.snapshot()
                    if digest(restored) != digest(states[arm]):
                        raise ValueError('task-local base restore mismatch')
                    config, goal = decode(case['config']), Goal.from_dict(case['goal'])
                    body = Sandbox(Path(temp) / f'{case["case"]}-{arm}', **config)
                    action_count = len(body.actions())
                    if action_count != 2 * case['objects'] * (case['objects'] - 1):
                        raise ValueError('permission-only action count changed')
                    if action_count * (1 + action_count) > PLAN['limit']:
                        raise ValueError('full root coverage exceeds unchanged budget')
                    if goal.holds(body.evidence()):
                        raise ValueError('initially solved configuration')
                    db = output / f'case-{case["case"]:03d}-{arm}.sqlite'
                    episode = Episode(db, body, goal, client, config=config, budget=8)
                    try:
                        stop = advance_episode(episode)
                    finally:
                        episode.close()
                    checkpoint = client.snapshot()
                    if stop['reason'] not in ('goal_reached', 'step_budget_exceeded'):
                        raise ValueError('invalid target termination: ' + stop['reason'])
                    if arm == 'warm_frozen' and checkpoint['weights'] != states[arm]['weights']:
                        raise ValueError('frozen control weights changed')
                    verified = verify_episode(db, expected_config=config, expected_goal=goal, expected_budget=8)
                    if not verified['green'] or verified['completed'] != stop['completed']:
                        raise ValueError('independent target native replay failed')
                    trace, sqlite_sha = native_operation_trace(db), file_hash(db)
                    measured_cpu = time.process_time() - p + process_cpu(client) - worker
                    row = {'case': case['case'], 'arm': arm, 'presentation': presentation,
                           'stratum': case['stratum'], 'success': bool(stop['completed']),
                           'charged_steps': stop['steps'] if stop['completed'] else 8,
                           'cpu_seconds': measured_cpu + startup[arm]['cpu_seconds'] / 64,
                           'cpu_excluding_startup': measured_cpu,
                           'startup_cpu_share': startup[arm]['cpu_seconds'] / 64,
                           'wall_seconds': time.perf_counter() - w,
                           'checkpoint_before': digest(restored), 'checkpoint_after': digest(checkpoint),
                           'action_count': action_count, 'stop': stop, 'replay': verified,
                           'sqlite_sha256': sqlite_sha, 'native_trace': trace}
                    raw.write(canonical(row) + '\n')
                    raw.flush()
                    rows.append(row)
                if (presentation + 1) % 8 == 0:
                    print(f'new-effect decision {presentation + 1}/64 (results withheld)', flush=True)
        check_binding(output, prereg)
        if file_hash(output / 'preregistration.json') != sha:
            raise ValueError('preregistration changed during attempt')
        metric_rows = [{k: row[k] for k in ('case', 'arm', 'success', 'charged_steps', 'cpu_seconds')} for row in rows]
        metrics = summarize(metric_rows)
        rename = {a: {'dispatches': sum(e['action']['op'] == 'rename' for r in rows if r['arm'] == a for e in r['native_trace']),
                       'native_successes': sum(e['action']['op'] == 'rename' and e['native_success']
                                               for r in rows if r['arm'] == a for e in r['native_trace'])}
                  for a in ARMS}
        verdict = metrics['verdict']
        if verdict == 'ADAPTATION_LIFT_CONFIRMED' and not rename['warm']['native_successes']:
            verdict = 'NO_NEW_MECHANIC_USE_DEMONSTRATED'
        receipt.update(status=verdict, capability_claim=verdict == 'ADAPTATION_LIFT_CONFIRMED',
                       metrics=metrics, controls=controls, all_native_replays_verified=len(rows),
                       source_and_data_unchanged=True, raw_sha256=file_hash(output / 'raw.jsonl'),
                       rename_diagnostics=rename,
                       first_rename_observations={arm: next(({'case': r['case'], 'event': e}
                           for r in rows if r['arm'] == arm for e in r['native_trace']
                           if e['action']['op'] == 'rename'), None) for arm in ARMS})
    except Exception as error:
        receipt.update(status='HARD_CAP_STOP' if isinstance(error, TimeoutError) else 'INVALID',
                       error=type(error).__name__ + ': ' + str(error), completed_rows=len(rows))
    finally:
        for arm, client in clients.items():
            try:
                worker_final_cpu[arm] = process_cpu(client)
            except Exception as error:
                receipt.update(status='INVALID', capability_claim=False,
                               cleanup_error='worker CPU unavailable: ' + type(error).__name__)
            try:
                client.close()
            except Exception as error:
                receipt.update(status='INVALID', capability_claim=False,
                               cleanup_error='worker cleanup failed: ' + type(error).__name__)
    receipt.update(startup=startup, base_training=prereg['base'],
                   all_arm_attempt_cpu_seconds=time.process_time() - parent_start + sum(worker_final_cpu.values()),
                   wall_seconds=time.perf_counter() - started,
                   lifecycle_efficiency_claim=False, retry_permitted=False)
    write_new(output / 'receipt.json', receipt)
    print(canonical(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare', 'run'))
    parser.add_argument('--dev')
    parser.add_argument('--expected-dev-sha')
    parser.add_argument('--output', required=True)
    parser.add_argument('--expected-prereg-sha')
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare(args.dev, args.expected_dev_sha, args.output)
    else:
        run(args.output, args.expected_prereg_sha)
