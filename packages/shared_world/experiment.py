"""Bounded DEV workbench. No automatic fresh retry or capability declaration.

The native adapter knows tool mechanics; learners/planner do not. Supplied
observations include kinds, equality and path-parent relations. New randomized
configurations of those SAME mechanics are not new mechanics or general transfer.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import random
import sqlite3
import tempfile
import time

from packages.action_core.episode import canonical, digest, encode_config
from packages.action_core.planner import Goal
from packages.action_core.retrieval import Retrieval
from packages.action_core.schema import TRANSFER_SCHEMA
from packages.action_core.world import Sandbox
from .full_context import FullContextLearner
from .relational import RelationalLearner
from .runtime import WorldSession, verify_world


ARMS = ('relational', 'full_context', 'retrieval', 'frozen')
DEFAULT_PLANNING = {'horizon': 2, 'width': 8, 'limit': 4096, 'revisit_penalty': .2}


def write_new(path, value):
    """Experiment artifact, never source rewrite or overwrite of an attempt."""
    with Path(path).open('x', encoding='utf-8') as out:
        out.write(canonical(value) + '\n')


def sources():
    root = Path(__file__).resolve().parents[2]
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for directory in ('packages/action_core', 'packages/shared_world')
            for p in sorted((root / directory).rglob('*.py'))}


def native_cpu_seconds(process):
    """OS counter including interpreter/import/startup and final process exit.

    Windows-only for this registered local workbench. Never trust a learner's
    claimed timing for the cost gate. Popen retains its handle after wait().
    """
    if os.name != 'nt':
        raise RuntimeError('OS CPU accounting not implemented on this platform')
    creation, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
    fn = ctypes.windll.kernel32.GetProcessTimes
    fn.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    fn.restype = wintypes.BOOL
    if not fn(wintypes.HANDLE(int(process._handle)), ctypes.byref(creation),
              ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
        raise OSError('cannot independently account worker CPU')
    return sum((v.dwHighDateTime << 32) + v.dwLowDateTime for v in (kernel, user)) / 10_000_000


def native_peak_memory(process):
    """Worker-only OS peak; parent memory shared across arms is not comparable."""
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
                'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
    info = Counters()
    info.cb = ctypes.sizeof(info)
    fn = ctypes.windll.psapi.GetProcessMemoryInfo
    fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    fn.restype = wintypes.BOOL
    if not fn(wintypes.HANDLE(int(process._handle)), ctypes.byref(info), info.cb):
        return None
    return info.PeakWorkingSetSize


def make_life(seed, *, training=False, ordinal=0):
    rng = random.Random(seed)
    reference, parent, child, spare, extra = [f'x{rng.getrandbits(48):012x}' for _ in range(5)]
    target = parent + '/' + child
    paths = [reference, parent, target, spare, extra]
    rng.shuffle(paths)
    content = rng.randbytes(rng.randrange(2, 40))
    initial = {reference: content}
    if ordinal % 2:
        initial[parent] = None
        if training and rng.random() < .5:
            initial[target] = rng.choice((None, b'', rng.randbytes(9), content))
    for name in (spare, extra):
        if training and rng.random() < .65:
            initial[name] = rng.choice((None, b'', rng.randbytes(13), content))
    handles = {name: f'n{paths.index(name)}' for name in paths}
    ref, dst, alt, aux = handles[reference], handles[target], handles[spare], handles[extra]
    config = {'paths': paths, 'initial': initial, 'protected': {ref}, 'operations': TRANSFER_SCHEMA}
    # Tasks are declarative conjunctions, not supplied plans. Initial states are
    # solvable; a learner can damage its own later reachability (e.g. filling
    # every locator with directories). Such failures remain in the denominator.
    goals = [Goal(f'{seed}:learn0', ((dst, 1),), ((ref, dst),)),
             Goal(f'{seed}:learn1', ((dst, 0), (alt, 1)), ((ref, alt),)),
             Goal(f'{seed}:eval0', ((dst, 1), (alt, 0)), ((ref, dst),)),
             Goal(f'{seed}:eval1', ((dst, 0), (alt, 1), (aux, 1)), ((ref, alt), (ref, aux)))]
    return config, goals


def prepare_training(output, *, cases=32, steps=16, seed=913100):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    initial_sources = sources()
    factories = {'relational': lambda: RelationalLearner(TRANSFER_SCHEMA),
        'full_context': lambda: FullContextLearner(seed=9131, updates=3,
            change_balanced=True, latest_update=True, schema=TRANSFER_SCHEMA),
        'retrieval': lambda: Retrieval(TRANSFER_SCHEMA)}
    models, cpu = {}, {}
    started_cpu = time.process_time()
    for arm, factory in factories.items():
        start = time.process_time()
        models[arm] = factory()
        cpu[arm] = time.process_time() - start
    native_cpu, rows, coverage = 0., [], {}
    with tempfile.TemporaryDirectory(prefix='shared_world_train_') as temp:
        for case in range(cases):
            start = time.process_time()
            config, _ = make_life(seed + case, training=True, ordinal=case)
            body = Sandbox(Path(temp) / f'body-{case}', **config)
            initial = body.evidence()
            native_cpu += time.process_time() - start
            history, rng = [], random.Random(seed * 3 + case)
            for step in range(steps):
                start = time.process_time()
                before, action = body.observe(), rng.choice(body.actions())
                success = body.step(action)
                after = body.observe()
                evidence = body.evidence()
                if any(evidence[h] != initial[h] for h in config['protected']):
                    raise ValueError('protected training source changed')
                row = {'event_id': f'train:{case}:{step}', 'case': case,
                       'config': encode_config(config) if step == 0 else None,
                       'before': before.to_dict(), 'action': action.to_dict(), 'after': after.to_dict(),
                       'succeeded': success, 'evidence': evidence,
                       'history': [[f.to_dict(), a.to_dict()] for f, a in history]}
                rows.append(row)
                key = action.op + (':changed' if before.to_dict() != after.to_dict() else ':unchanged')
                coverage[key] = coverage.get(key, 0) + 1
                native_cpu += time.process_time() - start
                for arm, model in models.items():
                    start = time.process_time()
                    model.learn(row['event_id'], before, action, after, history)
                    cpu[arm] += time.process_time() - start
                history = (history + [(before, action)])[-3:]
            if (case + 1) % 8 == 0:
                print(f'DEV training {case + 1}/{cases}', flush=True)
    verify_training(rows, cases=cases, steps=steps, seed=seed)
    write_new(output / 'observations.json', rows)
    for arm, model in models.items():
        start = time.process_time()
        write_new(output / f'{arm}.json', model.snapshot())
        cpu[arm] += time.process_time() - start
    manifest = {'status': 'DEV_TRAINING', 'capability_claim': False,
        'cases': cases, 'steps_per_case': steps, 'seed': seed, 'observations': len(rows),
        'coverage': coverage, 'training_cpu_seconds': cpu, 'native_acquisition_cpu_seconds': native_cpu,
        'common_cpu_seconds': max(0., time.process_time() - sum(cpu.values())),
        'common_cpu_policy': 'Common startup/acquisition/artifact cost is charged to every arm, not hidden.',
        'process_cpu_at_training_entry': started_cpu,
        'native_training_reexecution': True,
        'source_hashes': initial_sources,
        'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.glob('*.json'))},
        'strong_baseline': 'full_context:updates3/change_balanced/latest_update'}
    if initial_sources != sources():
        raise ValueError('source changed during training')
    write_new(output / 'manifest.json', manifest)
    print(canonical({'training': manifest['observations'], 'coverage': coverage, 'cpu': cpu}), flush=True)
    return manifest


def verify_training(rows, *, cases, steps, seed):
    """Reacquire actual outcomes from independently regenerated inputs/actions."""
    if len(rows) != cases * steps:
        raise ValueError('training count mismatch')
    with tempfile.TemporaryDirectory(prefix='shared_training_verify_') as temp:
        for case in range(cases):
            config, _ = make_life(seed + case, training=True, ordinal=case)
            body = Sandbox(Path(temp) / f'body-{case}', **config)
            history, rng = [], random.Random(seed * 3 + case)
            for step in range(steps):
                row = rows[case * steps + step]
                before, action = body.observe(), rng.choice(body.actions())
                succeeded = body.step(action)
                expected = {'event_id': f'train:{case}:{step}', 'case': case,
                    'config': encode_config(config) if step == 0 else None,
                    'before': before.to_dict(), 'action': action.to_dict(),
                    'after': body.observe().to_dict(), 'succeeded': succeeded,
                    'evidence': body.evidence(),
                    'history': [[f.to_dict(), a.to_dict()] for f, a in history]}
                if row != expected:
                    raise ValueError(f'training native replay mismatch:{case}:{step}')
                history = (history + [(before, action)])[-3:]
    return True


def run_life(output, arm, config, goals, checkpoint, *, life, planning, goal_budget=8):
    from .worker import Client
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    start_cpu, start_wall = time.process_time(), time.perf_counter()
    algorithm = 'relational' if arm == 'frozen' else arm
    client, world, events, errors = None, None, [], []
    decision_times, peak_memory = [], None
    verified = None
    with tempfile.TemporaryDirectory(prefix='shared_world_life_') as temp:
        try:
            body = Sandbox(Path(temp) / 'body', **config)
            client = Client(algorithm=algorithm, frozen=arm == 'frozen', schema=TRANSFER_SCHEMA,
                            timeout=180, **planning)
            client.restore(checkpoint)
            choose_bound = client.choose
            def timed_choose(*args, **kwargs):
                t0 = time.perf_counter()
                try:
                    return choose_bound(*args, **kwargs)
                finally:
                    decision_times.append(time.perf_counter() - t0)
            client.choose = timed_choose
            world = WorldSession(output / 'world.sqlite', body, client, config=config,
                total_budget=4 * goal_budget, world_id=f'life:{life}', self_id='shared-core')
            for index, goal in enumerate(goals):
                before = body.evidence()
                already = goal.holds(before)
                t0, c0, w0 = time.perf_counter(), time.process_time(), native_cpu_seconds(client.process)
                world.issue_goal(goal, goal_budget)
                result = world.run_goal()
                if 'completed' not in result:
                    raise ValueError('unclosed_goal:' + canonical(result))
                events.append({'index': index, 'phase': 'learning' if index < 2 else 'evaluation',
                    'goal': goal.to_dict(), 'initially_true': already, 'initial_evidence': before,
                    'result': result, 'charged_steps': result['steps'] if result['completed'] else goal_budget,
                    'cpu_seconds': time.process_time() - c0 + native_cpu_seconds(client.process) - w0,
                    'wall_seconds': time.perf_counter() - t0})
            state = world.state
            world.close()
            world = None
            verified = verify_world(output / 'world.sqlite', expected_config=config,
                expected_total_budget=4 * goal_budget, expected_world_id=f'life:{life}',
                expected_self_id='shared-core', expected_goals=[(g, goal_budget) for g in goals])
            if not verified['green']:
                errors.append('native_verification:' + canonical(verified['errors']))
        except Exception as exc:
            errors.append(type(exc).__name__ + ':' + str(exc))
            state = world.state if world is not None else None
        finally:
            if world is not None:
                world.close()
            if client is not None:
                peak_memory = native_peak_memory(client.process)
                client.close()
    # OS counter is read after exit, including imports and learner cleanup.
    child_cpu = native_cpu_seconds(client.process) if client is not None else 0.
    db = output / 'world.sqlite'
    sizes = sum(p.stat().st_size for p in output.glob('world.sqlite*'))
    result = {'arm': arm, 'life': life, 'episodes': events, 'errors': errors,
        'verified': verified, 'state_model_digest': digest(state['model']) if state else None,
        'actual_steps': state['steps'] if state else None,
        'observations': state['observations'] if state else None,
        'worker_cpu_seconds': child_cpu,
        'worker_peak_working_set_bytes': peak_memory,
        'decision_wall_seconds': decision_times,
        'wall_seconds': time.perf_counter() - start_wall, 'storage_bytes': sizes,
        'journal_sha256': hashlib.sha256(db.read_bytes()).hexdigest() if db.exists() else None,
        'capability_claim': False}
    # This immutable detail artifact (including full journal hashing) is sealed
    # before the cost cutoff. Only the final small timing/result record's own
    # serialization is excluded, explicitly; no recursive timing fiction.
    write_new(output / 'evidence.json', result)
    result['cpu_seconds'] = time.process_time() - start_cpu + child_cpu
    result['timing_exclusion'] = 'final result/timing record serialization only'
    write_new(output / 'result.json', result)
    return result


def run_dev(output, training, *, lives=4, seed=913900, planning=None):
    output, training = Path(output), Path(training)
    output.mkdir(parents=True, exist_ok=False)
    planning = planning or dict(DEFAULT_PLANNING)
    hashes = sources()
    manifest = json.loads((training / 'manifest.json').read_text(encoding='utf-8'))
    training_hashes = {name: hashlib.sha256((training / name).read_bytes()).hexdigest()
                       for name in manifest['files']}
    if training_hashes != manifest['files']:
        raise ValueError('training artifact integrity mismatch')
    models = {arm: json.loads((training / f'{arm}.json').read_text(encoding='utf-8'))
              for arm in ARMS if arm != 'frozen'}
    rows = []
    wall = time.perf_counter()
    for life in range(lives):
        config, goals = make_life(seed + life, ordinal=life)
        # Balanced cyclic order is fixed before observations, not chosen by speed.
        order = ARMS[life % 4:] + ARMS[:life % 4]
        for arm in order:
            model = models['relational' if arm == 'frozen' else arm]
            row = run_life(output / f'{life:03d}-{arm}', arm, config, goals, model,
                           life=life, planning=planning)
            rows.append(row)
            print(canonical({'dev_life': life, 'arm': arm, 'errors': row['errors'],
                'success': [r['result']['completed'] for r in row['episodes']],
                'steps': [r['result']['steps'] for r in row['episodes']],
                'cpu_seconds': row['cpu_seconds']}), flush=True)
    totals = {}
    for arm in ARMS:
        subset = [r for r in rows if r['arm'] == arm]
        evaluation = [e for r in subset for e in r['episodes'] if e['phase'] == 'evaluation']
        totals[arm] = {'evaluation_successes': sum(e['result']['completed'] for e in evaluation),
            'evaluation_count': len(evaluation), 'expected_count': lives * 2,
            'evaluation_charged_steps': sum(e['charged_steps'] for e in evaluation),
            'cpu_seconds': sum(r['cpu_seconds'] for r in subset),
            'all_native_verified': all(r['verified'] and r['verified']['green'] for r in subset),
            'invalid_proposals': sum(e['result']['reason'] == 'invalid_proposal' for r in subset for e in r['episodes'])}
    baseline = totals['full_context']
    ready = (not any(r['errors'] for r in rows)
        and all(t['all_native_verified'] and t['invalid_proposals'] == 0 for t in totals.values())
        and baseline['evaluation_count'] == lives * 2
        and baseline['evaluation_successes'] >= lives)
    report = {'status': 'DEV_READY' if ready else 'DEV_NOT_READY', 'capability_claim': False,
        'seed': seed, 'lives': lives, 'planning': planning, 'totals': totals,
        'rows': rows, 'source_hashes_before': hashes, 'source_hashes_after': sources(),
        'training_file_hashes': training_hashes,
        'wall_seconds': time.perf_counter() - wall,
        'limitations': ['Exposed DEV configurations of known native mechanics, not fresh capability',
            'One training seed/checkpoint per arm', 'Fixed parent/equality/role/program grammar',
            'Goal succession depends on earlier on-policy outcomes; not matched intermediate states',
            'Observation count excludes unrecorded pre-dispatch consistency reads; CPU includes them',
            'DEV CPU excludes separately reported pretraining; a final cost gate must include it']}
    if hashes != sources() or any(hashlib.sha256((training / name).read_bytes()).hexdigest() != sha
                                 for name, sha in training_hashes.items()):
        report['status'] = 'INVALID_SOURCE_OR_CHECKPOINT_CHANGED'
    write_new(output / 'report.json', report)
    print(canonical({k: report[k] for k in ('status', 'totals', 'wall_seconds')}), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['train', 'dev'])
    parser.add_argument('output')
    parser.add_argument('--training')
    parser.add_argument('--lives', type=int, default=4)
    args = parser.parse_args()
    if args.mode == 'train':
        prepare_training(args.output)
    elif args.training:
        run_dev(args.output, args.training, lives=args.lives)
    else:
        parser.error('--training required for DEV')
