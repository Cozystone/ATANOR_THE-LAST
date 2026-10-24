"""One-attempt D4 registration/execution; no automatic retry or tuning.

Run as python -B -m scripts.shared_world_fresh prereg|run ... . This is a
trusted local supervisor, not cryptographic protection against its operator.
Native replay, external checkpoint binding, arithmetic and source closure are
separate checks. A completed goal is never accepted from a GREEN field alone.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import copy
import hashlib
import json
import math
import importlib.metadata
import os
import platform
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

from scripts.shared_world_metrics import ARMS, analyze


ROOT = Path(__file__).resolve().parents[1]
PLAN = {'horizon': 2, 'width': 8, 'limit': 4096, 'revisit_penalty': .2}
DESIGN = {'lives': 64, 'seed': 914800, 'goals_per_life': 4, 'learning_indexes': [0, 1],
          'evaluation_indexes': [2, 3], 'goal_budget': 8, 'total_budget': 32,
          'bootstrap': 4000, 'bootstrap_seed': 91377, 'arms': list(ARMS),
          'ordering': 'cyclic arm rotation by life modulo four', 'planning': PLAN}
THRESHOLDS = {'baseline_success_min': .50, 'success_min': .75, 'success_delta_lcb_min': -.05,
              'charged_ratio_max': .80, 'charged_ratio_ucb_max': .90,
              'cpu_ratio_max': 1., 'cpu_ratio_ucb_max': 1.10,
              'online_charged_delta_lcb_strict_min': 0., 'online_success_delta_lcb_min': -.05}
TRAIN_FILES = ('observations.json', 'relational.json', 'full_context.json', 'retrieval.json')
MODEL_FILES = ('packages/shared_world/relational.py', 'packages/shared_world/full_context.py',
               'packages/shared_world/contracts.py')
DEV_FILES = MODEL_FILES + ('packages/shared_world/planning.py', 'packages/shared_world/runtime.py',
                           'packages/shared_world/worker.py')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(canonical(value) + '\n')


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, check=False)
    if result.returncode:
        raise ValueError('git check failed: ' + ' '.join(args) + ': ' + result.stderr.decode(errors='replace'))
    return result.stdout


def source_closure(root):
    return {p.relative_to(root).as_posix(): sha(p)
            for directory in ('packages', 'scripts', 'tests')
            for p in sorted((Path(root) / directory).rglob('*.py'))}


def environment():
    return {'python': platform.python_version(), 'executable': sys.executable,
            'platform': platform.platform(),
            'packages': {name: importlib.metadata.version(name) for name in ('numpy', 'torch')},
            'thread_settings': {name: os.environ.get(name) for name in
                                ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS')}}


def _committed_sources(root, hashes):
    for name, expected in hashes.items():
        if hashlib.sha256(git(root, 'show', 'HEAD:' + name)).hexdigest() != expected:
            raise ValueError('uncommitted or changed source: ' + name)
    tracked = git(root, 'ls-tree', '-r', '--name-only', 'HEAD', '--', 'packages', 'scripts', 'tests').decode().splitlines()
    if {p for p in tracked if p.endswith('.py')} != set(hashes):
        raise ValueError('source closure additions/deletions are uncommitted')


def training_binding(directory, closure):
    directory = Path(directory).resolve()
    manifest = read(directory / 'manifest.json')
    if (manifest.get('status') != 'DEV_TRAINING' or manifest.get('native_training_reexecution') is not True
            or (manifest.get('cases'), manifest.get('steps_per_case'), manifest.get('observations'), manifest.get('seed'))
            != (32, 16, 512, 913100) or set(manifest.get('files', {})) != set(TRAIN_FILES)):
        raise ValueError('invalid registered training manifest')
    hashes = {name: sha(directory / name) for name in TRAIN_FILES + ('manifest.json',)}
    if any(hashes[name] != manifest['files'][name] for name in TRAIN_FILES):
        raise ValueError('training artifact digest mismatch')
    if len(read(directory / 'observations.json')) != 512:
        raise ValueError('training observation count mismatch')
    checked = [p for p in closure if p.startswith('packages/action_core/')] + list(MODEL_FILES)
    if any(manifest.get('source_hashes', {}).get(p) != closure.get(p) or p not in closure for p in checked):
        raise ValueError('training model/native definitions changed')
    common, costs = manifest.get('common_cpu_seconds'), manifest.get('training_cpu_seconds', {})
    if (type(common) not in (int, float) or not math.isfinite(common) or common < 0
            or set(costs) != set(ARMS) - {'frozen'}
            or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in costs.values())):
        raise ValueError('invalid training CPU accounting')
    totals = {arm: common + costs['relational' if arm == 'frozen' else arm] for arm in ARMS}
    return {'directory': str(directory), 'files': hashes, 'cpu_seconds': totals}


def dev_binding(path, closure):
    path = Path(path).resolve()
    report = read(path)
    lives, totals = report.get('lives'), report.get('totals', {})
    if (report.get('status') != 'DEV_READY' or type(lives) is not int or lives < 1
            or set(totals) != set(ARMS) or report.get('planning') != PLAN
            or report.get('source_hashes_before') != report.get('source_hashes_after')):
        raise ValueError('DEV readiness not established')
    if any(not totals[a].get('all_native_verified') or totals[a].get('invalid_proposals') != 0
           or totals[a].get('evaluation_count') != lives * 2 for a in ARMS):
        raise ValueError('DEV controls or denominators are invalid')
    if totals['full_context'].get('evaluation_successes', -1) < lives:
        raise ValueError('DEV strong baseline below fifty percent')
    if any(report.get('source_hashes_after', {}).get(p) != closure.get(p) or p not in closure for p in DEV_FILES):
        raise ValueError('candidate changed since DEV readiness')
    return {'path': str(path), 'sha256': sha(path)}


def prereg(path, training, dev, *, root=ROOT):
    root, path = Path(root).resolve(), Path(path).resolve()
    path.relative_to(root)  # The registration must later be committed in this repository.
    if path.exists():
        raise FileExistsError('registration already exists')
    closure = source_closure(root)
    _committed_sources(root, closure)
    training_info, dev_info = training_binding(training, closure), dev_binding(dev, closure)
    dev_proof = audit_dev_replay(dev, training)
    if source_closure(root) != closure or training_binding(training, closure) != training_info or dev_binding(dev, closure) != dev_info:
        raise ValueError('registration inputs changed during independent DEV audit')
    protocol = {'format': 'shared-world-d4-v1', 'candidate_head': git(root, 'rev-parse', 'HEAD').decode().strip(),
        'repository': str(root), 'sources': closure, 'environment': environment(), 'training': training_info,
        'dev': dev_info, 'dev_proof': {'sha256': digest(dev_proof), 'evidence': dev_proof},
        'design': copy.deepcopy(DESIGN), 'thresholds': copy.deepcopy(THRESHOLDS),
        'scope': ['Known five-operation filesystem mechanics, five fully observed locators, not new mechanics.',
                  'One pretrained checkpoint per arm; each independent life starts from that checkpoint.',
                  'On-policy damage, including unrecoverable directories, is retained as failure.',
                  'Common training costs charged equally to alternatives; frozen uses relational training cost.',
                  'Native verification is separate from forecast/model claims; no production activation.'],
        'cost_boundary': 'Standalone execution process CPU plus all OS worker CPU. Residual startup/preflight/dataset/guard/serialization CPU is charged once to each alternative in addition to training. Only final cross-arm bootstrap and report emission are excluded; no learning, search or native verification is excluded.'}
    write_new(path, protocol)
    return protocol


def preflight(path, *, root=ROOT):
    root, path = Path(root).resolve(), Path(path).resolve()
    protocol = read(path)
    if (protocol.get('format') != 'shared-world-d4-v1' or protocol.get('repository') != str(root)
            or protocol.get('design') != DESIGN or protocol.get('thresholds') != THRESHOLDS):
        raise ValueError('protocol differs from fixed design')
    if git(root, 'show', 'HEAD:' + path.relative_to(root).as_posix()) != path.read_bytes():
        raise ValueError('protocol is not committed exactly')
    git(root, 'merge-base', '--is-ancestor', protocol['candidate_head'], 'HEAD')
    proof = protocol.get('dev_proof', {})
    evidence = proof.get('evidence', {})
    if (proof.get('sha256') != digest(evidence) or evidence.get('dev_sha256') != protocol['dev']['sha256']
            or evidence.get('training_files') != protocol['training']['files']):
        raise ValueError('independent DEV audit binding mismatch')
    guard(protocol, root=root)
    return protocol


def guard(protocol, *, root=ROOT):
    if protocol.get('environment') != environment():
        raise ValueError('registered runtime environment changed')
    closure = source_closure(Path(root))
    if closure != protocol['sources']:
        raise ValueError('frozen source closure changed')
    if training_binding(protocol['training']['directory'], closure) != protocol['training']:
        raise ValueError('frozen training changed')
    if dev_binding(protocol['dev']['path'], closure) != protocol['dev']:
        raise ValueError('frozen DEV receipt changed')


def claim_attempt(protocol_path, output):
    """An exclusive marker binds this protocol to one output, even across paths."""
    protocol_path, output = Path(protocol_path).resolve(), Path(output).resolve()
    marker = protocol_path.with_suffix(protocol_path.suffix + '.attempt.json')
    if marker.exists() or output.exists():
        raise FileExistsError('attempt already claimed or output already exists')
    output.mkdir(parents=True, exist_ok=False)
    claim = {'protocol_sha256': sha(protocol_path), 'output': str(output), 'started_ns': time.time_ns()}
    write_new(marker, claim)
    write_new(output / 'attempt-start.json', claim)
    return claim


def audit_journal(path, row, *, checkpoint, config, goals, life, arm):
    """Independent count/model binding. Caller must ALSO perform native replay."""
    with closing(sqlite3.connect('file:' + Path(path).resolve().as_posix() + '?mode=ro', uri=True)) as db:
        events = list(db.execute('SELECT seq,kind,payload,digest FROM events ORDER BY seq'))
        state = json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
    previous, decoded = '', []
    for number, (seq, kind, text, value) in enumerate(events, 1):
        previous = hashlib.sha256((previous + kind + text).encode()).hexdigest()
        if seq != number or value != previous:
            raise ValueError('independent journal chain mismatch')
        decoded.append((kind, json.loads(text)))
    if not decoded or decoded[0][0] != 'BEGIN' or state['head'] != previous:
        raise ValueError('missing BEGIN or state head mismatch')
    algorithm = 'relational' if arm == 'frozen' else arm
    expected = {'format': 'shared-world-worker-v1', 'algorithm': algorithm, 'frozen': arm == 'frozen',
                'revision': checkpoint['revision'], 'seen': sorted(checkpoint['seen']), 'model': checkpoint}
    begin = decoded[0][1]
    if (begin['model_digest'] != digest(expected) or begin['model_revision'] != checkpoint['revision']
            or begin['binding']['config'] != config or begin['binding']['world_id'] != f'life:{life}'
            or begin['binding']['self_id'] != 'shared-core' or begin['binding']['total_budget'] != 32
            or begin['binding']['decision_cap'] != 128 or row['arm'] != arm or row['life'] != life):
        raise ValueError('external initial model/world binding mismatch')
    starts = [p for k, p in decoded if k == 'GOAL']
    ends = [p for k, p in decoded if k == 'GOAL_END']
    dispatches = [p for k, p in decoded if k == 'DISPATCH']
    results = [p for k, p in decoded if k == 'RESULT']
    learns = [p for k, p in decoded if k == 'LEARN']
    if len(starts) != 4 or len(ends) != 4 or len(row['episodes']) != 4 or len(results) != len(dispatches) or len(learns) != len(dispatches):
        raise ValueError('native goal/action count mismatch')
    spent = 0
    for index, (start, end, episode, goal) in enumerate(zip(starts, ends, row['episodes'], goals)):
        if (start != {'goal': goal, 'budget': 8, 'start_steps': spent, 'result': None}
                or episode['index'] != index or episode['phase'] != ('learning' if index < 2 else 'evaluation')
                or episode['goal'] != goal or episode['result'] != end
                or end['goal_id'] != goal['id'] or type(end['completed']) is not bool
                or type(end['steps']) is not int or not 0 <= end['steps'] <= 8
                or episode['charged_steps'] != (end['steps'] if end['completed'] else 8)
                or end['reason'] == 'invalid_proposal'):
            raise ValueError('goal boundary/result binding mismatch')
        spent += end['steps']
    model = state['model']
    if (spent != len(dispatches) or spent != row['actual_steps'] or spent != state['steps']
            or model['revision'] != checkpoint['revision'] + spent
            or digest(model) != row['state_model_digest'] or sha(path) != row['journal_sha256']):
        raise ValueError('native totals/checkpoint binding mismatch')
    if arm == 'frozen' and canonical(model['model']) != canonical(checkpoint):
        raise ValueError('frozen inner model changed')
    predictions = [p for k, p in decoded if k == 'PREDICT']
    if not predictions:
        raise ValueError('first-decision control was not exercised')
    return {'bound': True, 'goals': 4, 'dispatches': spent,
            'first_decision': {k: predictions[0][k] for k in ('action', 'prediction', 'nodes')},
            'base_model_digest': digest(checkpoint), 'journal_sha256': row['journal_sha256']}


def audit_dev_replay(reportpath, trainingdir):
    """Run once at registration, not inside each fresh guard. No learner rerun."""
    from packages.action_core.episode import encode_config
    from packages.shared_world.experiment import make_life
    from packages.shared_world.runtime import verify_world
    reportpath, trainingdir = Path(reportpath).resolve(), Path(trainingdir).resolve()
    report, started = read(reportpath), time.process_time()
    lives, rows = report.get('lives'), report.get('rows')
    if (report.get('status') != 'DEV_READY' or type(lives) is not int or lives < 1
            or type(rows) is not list or len(rows) != lives * 4 or type(report.get('seed')) is not int):
        raise ValueError('DEV independent audit requires complete identified rows')
    checkpoints = {a: read(trainingdir / (('relational' if a == 'frozen' else a) + '.json')) for a in ARMS}
    seen, first = set(), {}
    for row in rows:
        life, arm = row.get('life'), row.get('arm')
        if type(life) is not int or not 0 <= life < lives or arm not in ARMS or (life, arm) in seen:
            raise ValueError('duplicate/invalid DEV life arm')
        seen.add((life, arm))
        if row.get('errors'):
            raise ValueError('DEV row carries execution errors')
        config, goals = make_life(report['seed'] + life, ordinal=life)
        path = reportpath.parent / f'{life:03d}-{arm}' / 'world.sqlite'
        verified = verify_world(path, expected_config=config, expected_total_budget=32,
            expected_world_id=f'life:{life}', expected_self_id='shared-core',
            expected_goals=[(g, 8) for g in goals], expected_decision_cap=128)
        if not verified['green']:
            raise ValueError('DEV independent native replay failed:' + canonical(verified['errors']))
        bound = audit_journal(path, row, checkpoint=checkpoints[arm], config=encode_config(config),
                              goals=[g.to_dict() for g in goals], life=life, arm=arm)
        first[life, arm] = bound['first_decision']
    if any(first[life, 'relational'] != first[life, 'frozen'] for life in range(lives)):
        raise ValueError('DEV first-decision pair mismatch')
    totals = {}
    for arm in ARMS:
        subset = [r for r in rows if r['arm'] == arm]
        evaluation = [e for r in subset for e in r['episodes'] if e['index'] >= 2]
        totals[arm] = {'evaluation_successes': sum(e['result']['completed'] for e in evaluation),
            'evaluation_count': len(evaluation), 'expected_count': lives * 2,
            'evaluation_charged_steps': sum(e['charged_steps'] for e in evaluation),
            'cpu_seconds': sum(r['cpu_seconds'] for r in subset),
            'all_native_verified': True, 'invalid_proposals': 0}
    if totals != report.get('totals'):
        raise ValueError('DEV independently recounted totals differ from reported totals')
    return {'format': 'shared-world-dev-native-recount-v1', 'dev_sha256': sha(reportpath),
            'training_files': {n: sha(trainingdir / n) for n in TRAIN_FILES + ('manifest.json',)},
            'native_arm_runs': lives * 4, 'goal_ends': lives * 16, 'first_decision_pairs': lives,
            'totals': totals, 'audit_cpu_seconds': time.process_time() - started}


def execution_costs(rows, trainingcosts, process_cpu):
    """Reconcile unallocated supervisor CPU; standalone run-process counter."""
    parent = sum(r['cpu_seconds'] - r['worker_cpu_seconds'] for r in rows)
    if any(r['cpu_seconds'] < r['worker_cpu_seconds'] for r in rows):
        raise ValueError('worker CPU exceeds accounted whole-life CPU')
    common = max(0., process_cpu - parent)
    return common, {a: trainingcosts[a] + common for a in ARMS}


def run(protocol_path, output, *, root=ROOT):
    protocol_bytes = Path(protocol_path).read_bytes()
    protocol = preflight(protocol_path, root=root)
    if Path(protocol_path).read_bytes() != protocol_bytes:
        raise ValueError('protocol changed during preflight')
    protocol_digest = hashlib.sha256(protocol_bytes).hexdigest()

    def bound_guard():
        if sha(protocol_path) != protocol_digest:
            raise ValueError('committed protocol changed during execution')
        guard(protocol, root=root)

    execution_head = git(root, 'rev-parse', 'HEAD').decode().strip()
    output = Path(output).resolve()
    claim_attempt(protocol_path, output)
    rows, audits, error, status, metrics, matched_pairs = [], [], None, None, None, 0
    execution_common, fixed_costs = None, None
    try:
        from packages.action_core.episode import encode_config
        from packages.shared_world.experiment import make_life, run_life
        from packages.shared_world.runtime import verify_world
        training = Path(protocol['training']['directory'])
        checkpoints = {a: read(training / (('relational' if a == 'frozen' else a) + '.json')) for a in ARMS}
        write_new(output / 'dataset.json', [{'life': life, 'config': encode_config(make_life(914800 + life, ordinal=life)[0]),
            'goals': [g.to_dict() for g in make_life(914800 + life, ordinal=life)[1]]} for life in range(64)])
        for life in range(64):
            config, goals = make_life(914800 + life, ordinal=life)
            controls = {}
            for arm in ARMS[life % 4:] + ARMS[:life % 4]:
                before = time.process_time()
                bound_guard()
                guard_cpu = time.process_time() - before
                directory = output / f'{life:03d}-{arm}'
                row = run_life(directory, arm, config, goals, checkpoints[arm], life=life, planning=dict(PLAN), goal_budget=8)
                started = time.process_time()
                rows.append(row)  # Preserve returned evidence even when the next guard fails.
                if row['errors']:
                    raise ValueError('life execution error:' + canonical(row['errors']))
                native = verify_world(directory / 'world.sqlite', expected_config=config, expected_total_budget=32,
                    expected_world_id=f'life:{life}', expected_self_id='shared-core', expected_goals=[(g, 8) for g in goals], expected_decision_cap=128)
                if not native['green']:
                    raise ValueError('independent native replay:' + canonical(native['errors']))
                audit = audit_journal(directory / 'world.sqlite', row, checkpoint=checkpoints[arm],
                    config=encode_config(config), goals=[g.to_dict() for g in goals], life=life, arm=arm)
                bound_guard()
                write_new(directory / 'independent-binding.json', audit)
                row['reported_cpu_seconds'] = row['cpu_seconds']
                row['audit_cpu_seconds'] = guard_cpu + time.process_time() - started
                row['cpu_seconds'] += row['audit_cpu_seconds']
                audits.append({'life': life, 'arm': arm, **audit})
                controls[arm] = audit['first_decision']
                with (output / 'rows.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(canonical(row) + '\n')
            if controls['relational'] != controls['frozen']:
                raise ValueError('online/frozen first decision mismatch')
            matched_pairs += 1
            print(canonical({'completed_life_clusters': life + 1, 'total': 64}), flush=True)
        bound_guard()
        execution_common, fixed_costs = execution_costs(rows, protocol['training']['cpu_seconds'], time.process_time())
        # Final cross-arm arithmetic/reporting is explicitly outside this cost
        # cut; all model/search/native replay and input guards are already paid.
        metrics = analyze(rows, fixed_costs)
    except Exception as exc:
        error, status = type(exc).__name__ + ':' + str(exc), 'NO_GO'
    report = {'status': status or metrics['status'], 'protocol_sha256': protocol_digest,
        'execution_head': execution_head, 'hard_controls_green': error is None,
        'first_failed_control': error, 'completed_arm_runs': len(rows), 'independent_bindings': audits,
        'first_decision_pairs': matched_pairs, 'metrics': metrics, 'rows': rows,
        'training_cpu_seconds': protocol['training']['cpu_seconds'],
        'execution_common_cpu_seconds': execution_common, 'combined_fixed_cpu_seconds': fixed_costs,
        'metric_fixed_cost_label': 'metrics training_cpu_seconds contains training plus execution-common fixed charge',
        'capability_claim': bool(error is None and metrics['integrated_utility']),
        'scope': 'Local known-mechanics utility only; no AGI, new mechanics, new body or general RSI claim.'}
    write_new(output / 'report.json', report)
    print(canonical({'status': report['status'], 'first_failed_control': error}), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    register = commands.add_parser('prereg')
    register.add_argument('path'); register.add_argument('--training', required=True); register.add_argument('--dev', required=True)
    execute = commands.add_parser('run')
    execute.add_argument('protocol'); execute.add_argument('output')
    args = parser.parse_args()
    if args.command == 'prereg':
        prereg(args.path, args.training, args.dev)
    else:
        run(args.protocol, args.output)


if __name__ == '__main__':
    main()
