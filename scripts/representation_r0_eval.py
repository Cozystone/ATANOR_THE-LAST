"""Single-attempt R0 native trial. All roots and outcomes are retained.

Run from repository root. Only this supervisor sees native paths or cohort setup.
Predictions are durably journaled BEFORE dispatch. Training uses observed effects,
never the setup label. The evaluator does not claim hostile-process isolation.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packages.action_core.world import Action, Sandbox
from packages.representation_r0.search import fit, majority

FIELDS = ('st_dev', 'st_ino', 'st_nlink', 'st_size', 'st_mode')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def source_hashes():
    paths = sorted((ROOT / 'packages').rglob('*.py'))
    paths += [Path(__file__).resolve()]
    return {str(p.relative_to(ROOT)).replace('\\', '/'): digest(p) for p in paths}


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def journal(stream, value):
    stream.write(json.dumps(value, sort_keys=True) + '\n')
    stream.flush()
    os.fsync(stream.fileno())


def build(parent, name, payload, linked, nlinks, rng):
    names = [f'{rng.getrandbits(96):024x}.bin' for _ in range(2)]
    root = parent / name
    initial = {names[0]: payload}
    if not linked:
        initial[names[1]] = payload
    body = Sandbox(root, names, initial, protected=set())
    if linked:
        os.link(root / names[0], root / names[1])
        for i in range(nlinks - 2):
            os.link(root / names[0], root / f'aux_{i}')
    else:
        for role in range(2):
            for i in range(nlinks - 1):
                os.link(root / names[role], root / f'aux_{role}_{i}')
    paths = [root / name for name in names]
    infos = [p.stat() for p in paths]
    if any(info.st_ino == 0 or info.st_nlink != nlinks for info in infos):
        raise RuntimeError('unsupported raw identity or hardlink setup')
    return body, paths


def run(prereg_path, output):
    if git('status', '--porcelain'):
        raise RuntimeError('source tree must be clean and preregistration committed')
    relative = str(prereg_path.relative_to(ROOT)).replace('\\', '/')
    git('ls-files', '--error-unmatch', relative)
    p = json.loads(prereg_path.read_text(encoding='utf-8'))
    if p['attempt'] != 'r0-v1':
        raise ValueError('unsupported preregistration')
    # Exclusive marker lives NEXT TO the committed registration, so changing the
    # output directory cannot casually re-run the same registered attempt.
    marker = prereg_path.with_suffix('.attempt.json')
    write_json(marker, {'started': time.time(), 'output': str(output),
                        'prereg_sha256': digest(prereg_path), 'commit': git('rev-parse', 'HEAD')})
    output.mkdir(parents=True, exist_ok=False)
    before_sources = source_hashes()
    start, cpu = time.perf_counter(), time.process_time()
    rng = random.Random(p['seed'])
    field_order = list(FIELDS)
    rng.shuffle(field_order)
    native_root = Path(tempfile.mkdtemp(prefix='atanor_r0_'))
    pairs, labels, rows = [], [], []
    identities = {'train': set(), 'fresh': set()}
    model = ablated = None
    trained_snapshot = None
    old_default = False
    with (output / 'events.jsonl').open('x', encoding='utf-8') as events:
        for phase, count in (('train', p['train_pairs']), ('fresh', p['fresh_pairs'])):
            for pair_id in range(count):
                payload = rng.randbytes(rng.randint(1, 512))
                target = rng.randrange(2)
                nlinks = 2 + pair_id % 4
                order = [False, True]
                rng.shuffle(order)
                paired = []
                for variant, linked in enumerate(order):
                    body, paths = build(native_root, f'{phase}_{pair_id}_{variant}',
                                        payload, linked, nlinks, rng)
                    old = body.observe().to_dict()
                    infos = [path.stat() for path in paths]
                    identities[phase].update((x.st_dev, x.st_ino) for x in infos)
                    raw = tuple(tuple(int(getattr(x, f)) for f in field_order) for x in infos)
                    evidence_before = body.evidence()
                    prediction = None if model is None else {
                        'search': model.predict(raw), 'old_frame': old_default,
                        'selected_channel_removed': ablated.predict(raw)}
                    row_id = f'{phase}:{pair_id}:{variant}'
                    journal(events, {'event': 'pre_dispatch', 'id': row_id,
                                     'raw': raw, 'old_frame': old,
                                     'action': {'op': 'empty', 'args': [f'n{target}']},
                                     'prediction': prediction, 'native_root': str(body.root),
                                     'before': evidence_before})
                    if not body.step(Action('empty', (f'n{target}',))):
                        raise RuntimeError('native dispatch failed')
                    evidence_after = body.evidence()
                    observed = evidence_before[f'n{1-target}']['sha256'] != evidence_after[f'n{1-target}']['sha256']
                    if evidence_after[f'n{target}']['size_bytes'] != 0:
                        raise RuntimeError('native operation not realized')
                    # Setup is audit-only; fit() receives only raw and observed.
                    row = {'id': row_id, 'phase': phase, 'pair': pair_id,
                           'raw': raw, 'old_frame': old, 'target': target,
                           'prediction': prediction, 'observed': observed,
                           'setup_linked': linked, 'before': evidence_before,
                           'after': evidence_after, 'native_paths': list(map(str, paths))}
                    journal(events, {'event': 'post_dispatch', **row})
                    rows.append(row)
                    paired.append(row)
                    if phase == 'train':
                        pairs.append(raw)
                        labels.append(observed)
                if (paired[0]['old_frame'] != paired[1]['old_frame'] or
                        paired[0]['observed'] == paired[1]['observed']):
                    raise RuntimeError('observational aliasing contrast failed')
            if phase == 'train':
                model = fit(pairs, labels)
                ablated = fit(pairs, labels, excluded_columns=(model.column,))
                old_default = majority(labels)
                trained_snapshot = {'rule': asdict(model), 'ablated': asdict(ablated),
                                    'old_default': old_default}
                write_json(output / 'trained.json', trained_snapshot)
                journal(events, {'event': 'training_frozen', **trained_snapshot})
    fresh = [r for r in rows if r['phase'] == 'fresh']
    correct = {arm: sum(r['prediction'][arm] == r['observed'] for r in fresh)
               for arm in ('search', 'old_frame', 'selected_channel_removed')}
    total = len(fresh)
    accuracy = {arm: n / total for arm, n in correct.items()}
    gates = {
        'old_view_aliasing_all_pairs': True,  # checked above for every pair
        'train_fresh_native_id_disjoint': not identities['train'] & identities['fresh'],
        'observed_effect_agrees_with_native_setup': all(r['observed'] == r['setup_linked'] for r in rows),
        'source_unchanged': before_sources == source_hashes(),
        'frozen_model': trained_snapshot == {'rule': asdict(model), 'ablated': asdict(ablated),
                                           'old_default': old_default},
        'search_accuracy': accuracy['search'] >= p['min_accuracy'],
        'lift_vs_old': accuracy['search'] - accuracy['old_frame'] >= p['min_lift'],
        'lift_vs_removed': accuracy['search'] - accuracy['selected_channel_removed'] >= p['min_lift'],
    }
    write_json(output / 'rows.json', rows)
    report = {'verdict': 'R0_FEASIBILITY_GREEN' if all(gates.values()) else 'R0_NO_GO',
              'capability_claim': False, 'planning_integration': False,
              'fresh_n': total, 'correct': correct, 'accuracy': accuracy, 'gates': gates,
              'selected_rule': asdict(model), 'supervisor_channel_mapping': field_order,
              'native_root': str(native_root), 'source_hashes': before_sources,
              'prereg_sha256': digest(prereg_path), 'commit': git('rev-parse', 'HEAD'),
              'wall_seconds': time.perf_counter() - start,
              'supervisor_cpu_seconds': time.process_time() - cpu,
              'rows_sha256': digest(output / 'rows.json'),
              'events_sha256': digest(output / 'events.jsonl'),
              'limitations': p['limitations']}
    write_json(output / 'report.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prereg', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.prereg.resolve(), args.output.resolve())
