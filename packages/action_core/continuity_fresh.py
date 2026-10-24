"""One locked carry/reset experiment on new configurations, not new mechanics."""
from __future__ import annotations

import os
for _key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[_key] = '1'

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import secrets
import sqlite3
import tempfile
import time
import zipfile

from .continuity_metrics import summarize
from .episode import canonical, digest, verify_episode
from .fresh_eval import decode, file_hash, new_cases, process_cpu, sources, write_new
from .life import Life
from .life_dev import load_base
from .planner import Goal
from .storage import require_space
from .worker import Client
from .world import Sandbox

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / 'docs/CONTINUITY_FRESH_PROTOCOL.md'
PLANNING = dict(horizon=2, width=2, limit=4096, cover_root=True,
                uncertainty_weight=0, revisit_weight=0)
DEADLINE = datetime(2026, 9, 11, 11, 21, tzinfo=timezone.utc).timestamp()


def make_dataset(seed):
    rng, lives = random.Random(seed), []
    first = ['carry'] * 8 + ['reset'] * 8
    rng.shuffle(first)
    for life in range(16):
        child_seed = rng.getrandbits(63)
        pool, cases = new_cases(child_seed), []
        for half in range(2):
            selected = []
            for stratum in range(4):
                missing = bool((life + half + stratum) % 2)
                options = [r for r in pool if r['stratum'] == stratum and r['missing_parent'] == missing]
                row = dict(rng.choice(options))
                row['goal'] = dict(row['goal'], id=f'continuity-{life}-{half}-{stratum}')
                selected.append(row)
            rng.shuffle(selected)
            for row in selected:
                row['index'] = len(cases)
                cases.append(row)
        order = [first[life], 'reset' if first[life] == 'carry' else 'carry']
        lives.append({'life': life, 'configuration_seed': child_seed, 'arm_order': order, 'cases': cases})
    rng.shuffle(lives)
    return {'seed': seed, 'lives': lives}


def check_deadline():
    if time.time() >= DEADLINE:
        raise TimeoutError('preregistered continuity hard cap reached')


def prepare(source, output):
    check_deadline()
    output = Path(output).resolve()
    storage = require_space(output)
    output.mkdir(parents=True, exist_ok=False)
    frozen_sources = sources()
    base = load_base(Path(source) / 'model.json')
    write_new(output / 'base.json', base)
    seed = secrets.randbits(63)
    write_new(output / 'dataset.json', make_dataset(seed))
    with zipfile.ZipFile(output / 'source.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in frozen_sources:
            archive.write(ROOT / relative, relative)
        archive.write(PROTOCOL, PROTOCOL.relative_to(ROOT).as_posix())
    prereg = {'schema': 1, 'seed': seed, 'sources': frozen_sources,
        'protocol_sha256': file_hash(PROTOCOL), 'planning': PLANNING,
        'base_original_sha256': file_hash(Path(source) / 'model.json'),
        'bindings': {n: file_hash(output / n) for n in ('base.json', 'dataset.json', 'source.zip')},
        'unit_deadline_unix': DEADLINE, 'storage': storage,
        'lives': 16, 'tasks_per_life': 8, 'primary_indices': [4, 5, 6, 7],
        'overall_actual_budget': 64, 'actual_task_budget': 8,
        'bootstrap_seed': 771031, 'bootstrap_draws': 4000}
    if frozen_sources != sources():
        raise ValueError('source changed during preparation')
    write_new(output / 'preregistration.json', prereg)
    print(canonical({'prepared': str(output), 'prereg_sha256': file_hash(output / 'preregistration.json')}))


def check_bindings(output, prereg, expected_sha):
    if file_hash(output / 'preregistration.json') != expected_sha:
        raise ValueError('external preregistration digest mismatch')
    if sources() != prereg['sources'] or file_hash(PROTOCOL) != prereg['protocol_sha256']:
        raise ValueError('source/protocol changed')
    if prereg['planning'] != PLANNING or prereg['unit_deadline_unix'] != DEADLINE:
        raise ValueError('fixed planning/deadline mismatch')
    if set(prereg['bindings']) != {'base.json', 'dataset.json', 'source.zip'}:
        raise ValueError('unexpected artifact binding set')
    for name, sha in prereg['bindings'].items():
        if file_hash(output / name) != sha:
            raise ValueError('artifact changed: ' + name)
    dataset = json.loads((output / 'dataset.json').read_text(encoding='utf-8'))
    if dataset != make_dataset(prereg['seed']):
        raise ValueError('dataset/schedule does not match frozen generator seed')
    with zipfile.ZipFile(output / 'source.zip') as archive:
        import hashlib
        for relative, sha in prereg['sources'].items():
            if hashlib.sha256(archive.read(relative)).hexdigest() != sha:
                raise ValueError('source archive mismatch')
        if hashlib.sha256(archive.read(PROTOCOL.relative_to(ROOT).as_posix())).hexdigest() != prereg['protocol_sha256']:
            raise ValueError('protocol archive mismatch')


def native_row(entry, case, life_id, arm):
    """Do not take a life summary's success/counters as authoritative."""
    if entry['phase'] != 'done' or entry['index'] != case['index']:
        raise ValueError('episode boundary mismatch')
    path = Path(entry['db_path'])
    verified = verify_episode(path, expected_config=decode(case['config']),
        expected_goal=Goal.from_dict(case['goal']), expected_budget=8)
    if not verified['green']:
        raise ValueError('native replay rejected: ' + str(verified))
    db = sqlite3.connect('file:' + path.resolve().as_posix() + '?mode=ro', uri=True)
    try:
        stops = list(db.execute("SELECT payload FROM events WHERE kind='STOP'"))
        count = db.execute("SELECT COUNT(*) FROM events WHERE kind='DISPATCH'").fetchone()[0]
    finally:
        db.close()
    if len(stops) != 1:
        raise ValueError('not exactly one authoritative STOP')
    stop = json.loads(stops[0][0])
    if (type(stop['completed']) is not bool or type(stop['steps']) is not int or
        stop['reason'] not in ('goal_reached', 'step_budget_exceeded') or
        stop['steps'] != count or not 1 <= count <= 8 or
        stop['completed'] != verified['completed'] or count != verified['steps'] or
        stop != entry['stop']):
        raise ValueError('native completion/dispatch disagreement')
    return {'life': life_id, 'arm': arm, 'index': case['index'],
        'stratum': case['stratum'], 'missing_parent': case['missing_parent'],
        'success': stop['completed'], 'charged_steps': count if stop['completed'] else 8,
        'actual_steps': count, 'stop': stop, 'replay': verified,
        'sqlite_path': str(path), 'sqlite_sha256': file_hash(path)}


def advance(life, *, pause_after=None):
    """Check the wall cap before each actual-step opportunity, not just each life."""
    while True:
        check_deadline()
        result = life.step()
        if result['status'] != 'RUNNING':
            return result
        if pause_after is not None and sum(e['phase'] == 'done' for e in result['episodes']) == pause_after:
            return dict(result, status='PAUSED')


def execute_life(output, body_parent, spec, arm, base):
    agenda = [{'config': decode(c['config']), 'goal': Goal.from_dict(c['goal']), 'budget': 8}
              for c in spec['cases']]
    # Native, policy-free eligibility check; no candidate trial/rejection sampling.
    with tempfile.TemporaryDirectory(prefix='atanor-eligibility-') as temp:
        for i, item in enumerate(agenda):
            body = Sandbox(Path(temp) / str(i), **item['config'])
            if item['goal'].holds(body.evidence()):
                raise ValueError('initially solved configuration')
    root = output / f'life-{spec["life"]:02d}-{arm}'
    bodies = body_parent / root.name
    parent_cpu, wall = time.process_time(), time.perf_counter()
    child_cpu, pids = 0.0, []
    boundary = None
    for half in range(2):
        check_deadline()
        client = Client(seed=2101, timeout=60, **PLANNING)
        pids.append(client.process.pid)
        try:
            with Life(root, bodies, agenda, client, initial_checkpoint=base,
                      overall_budget=64, mode=arm) as life:
                if half and digest(life.checkpoint()) != boundary:
                    raise ValueError('committed restart checkpoint changed')
                if half == 0:
                    result = advance(life, pause_after=4)
                    if result['status'] != 'PAUSED':
                        raise ValueError('unexpected warm-up boundary: ' + canonical(result))
                    boundary = digest(life.checkpoint())
                else:
                    result = advance(life)
                    if result['status'] != 'COMPLETE':
                        raise ValueError('unexpected final boundary: ' + canonical(result))
                    final_digest = digest(life.checkpoint())
        finally:
            child_cpu += process_cpu(client)
            client.close()
    rows = [native_row(e, c, spec['life'], arm) for e, c in zip(result['episodes'], spec['cases'], strict=True)]
    if len(rows) != 8 or len(pids) != 2:
        raise ValueError('incomplete life/restart')
    summary = {'life': spec['life'], 'arm': arm, 'cpu_seconds': time.process_time() - parent_cpu + child_cpu,
        'wall_seconds': time.perf_counter() - wall, 'worker_pids': pids,
        'boundary_checkpoint_digest': boundary, 'final_checkpoint_digest': final_digest,
        'life_sqlite_sha256': file_hash(root / 'life.sqlite')}
    return rows, summary


def run(output, expected_sha):
    output = Path(output).resolve()
    check_deadline()
    require_space(output)
    prereg = json.loads((output / 'preregistration.json').read_text(encoding='utf-8'))
    check_bindings(output, prereg, expected_sha)
    write_new(output / 'attempt.lock', {'started_unix': time.time(), 'prereg_sha256': expected_sha})
    rows, summaries = [], []
    receipt = {'status': 'INVALID', 'capability_claim': False, 'prereg_sha256': expected_sha}
    started = time.perf_counter()
    try:
        base = json.loads((output / 'base.json').read_text(encoding='utf-8'))
        dataset = json.loads((output / 'dataset.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory(prefix='atanor-continuity-fresh-') as temp, \
             (output / 'raw.jsonl').open('x', encoding='utf-8') as raw, \
             (output / 'life_summaries.jsonl').open('x', encoding='utf-8') as summaries_out:
            for ordinal, spec in enumerate(dataset['lives']):
                for arm in spec['arm_order']:
                    check_deadline()
                    require_space(output, minimum_bytes=4 * 1024**3)
                    arm_rows, summary = execute_life(output, Path(temp), spec, arm, base)
                    for row in arm_rows:
                        raw.write(canonical(row) + '\n')
                        rows.append(row)
                    raw.flush()
                    summaries_out.write(canonical(summary) + '\n')
                    summaries_out.flush()
                    summaries.append(summary)
                print(f'continuity fresh {ordinal + 1}/16 life pairs (results withheld)', flush=True)
        check_deadline()
        check_bindings(output, prereg, expected_sha)
        metric_rows = [{k: row[k] for k in ('life', 'arm', 'index', 'success', 'charged_steps')} for row in rows]
        metric_cpu = [{k: row[k] for k in ('life', 'arm', 'cpu_seconds')} for row in summaries]
        metrics = summarize(metric_rows, metric_cpu)
        receipt.update(status=metrics['verdict'], metrics=metrics,
            capability_claim=metrics['verdict'] == 'CONTINUITY_LIFT',
            verified_episodes=len(rows), verified_restarts=len(summaries), bindings_unchanged=True)
    except Exception as error:
        receipt.update(error=type(error).__name__ + ': ' + str(error), completed_rows=len(rows))
    receipt.update(wall_seconds=time.perf_counter() - started,
        raw_sha256=file_hash(output / 'raw.jsonl') if (output / 'raw.jsonl').exists() else None,
        life_summaries_sha256=file_hash(output / 'life_summaries.jsonl') if (output / 'life_summaries.jsonl').exists() else None,
        claim_scope='New configurations of four known filesystem operations; repeated learning across separate bodies, not new mechanics or unified Self')
    write_new(output / 'receipt.json', receipt)
    print(json.dumps(receipt, indent=2))


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
