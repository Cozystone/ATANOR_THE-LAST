"""Owner-observed corpus; proposal subprocess gets only training observations.

capture then commit corpus/manifest before evaluate. Both modes exclusive-output.
No model-generated score is used by the independent local acceptance gate.
"""
import argparse
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packages.action_core.world import Action
from packages.shared_world.refinement_gate import RefinementGate, digest
from scripts.representation_r0_eval import build, FIELDS
from scripts.representation_r1_dev import train


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    root = Path(tempfile.mkdtemp(prefix='atanor_r2_discovery_'))
    rng = random.Random(9178117)
    fields = list(FIELDS)
    rng.shuffle(fields)
    audit, corpus = [], {}
    for phase in ('training', 'validation'):
        corpus[phase] = []
        for pair in range(16):
            payload = rng.randbytes(rng.randint(1, 512))
            target = rng.randrange(2)
            order = [False, True]
            rng.shuffle(order)
            for variant, linked in enumerate(order):
                body, paths = build(root, f'{phase}_{pair}_{variant}', payload, linked,
                                    2 + pair % 4, rng)
                before = body.observe().to_dict()
                raw = [[int(getattr(path.stat(), f)) for f in fields] for path in paths]
                evidence_before = body.evidence()
                action = Action('empty', (f'n{target}',))
                if not body.step(action):
                    raise RuntimeError('native discovery dispatch failed')
                record = {'before': before, 'action': action.to_dict(), 'after': body.observe().to_dict(),
                          'raw_before': raw}
                corpus[phase].append(record)
                audit.append({'phase': phase, 'pair': pair, 'variant': variant, 'native_root': str(body.root),
                              'record_digest': digest(record), 'before': evidence_before, 'after': body.evidence()})
    for key, data in corpus.items():
        save(output / f'{key}.json', data)
    save(output / 'manifest.json', {'seed': 9178117, 'raw_fields': fields,
         'training_digest': digest(corpus['training']), 'validation_digest': digest(corpus['validation']),
         'min_reduction': .9, 'native_actions': len(audit), 'root': str(root)})
    save(output / 'audit.json', audit)
    print('captured 32 training + 32 separate validation transitions; no proposal executed')


def evaluate(corpus, output):
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        raise RuntimeError('commit corpus and manifest before proposal')
    output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((corpus / 'manifest.json').read_text())
    training = json.loads((corpus / 'training.json').read_text())
    validation = json.loads((corpus / 'validation.json').read_text())
    authority = RefinementGate(training, validation, expected_training=manifest['training_digest'],
                               expected_validation=manifest['validation_digest'], raw_fields=manifest['raw_fields'],
                               min_reduction=manifest['min_reduction'])
    started = time.perf_counter()
    worker = subprocess.run([sys.executable, '-B', '-m', 'packages.shared_world.refinement'],
                            input=json.dumps(training), text=True, capture_output=True,
                            cwd=ROOT, timeout=60, check=True,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    proposal = json.loads(worker.stdout)
    receipt = authority.evaluate(proposal) if proposal else {'accepted': False, 'reason': 'no_proposal'}
    receipt['proposal_and_validation_wall_seconds'] = time.perf_counter() - started
    save(output / 'proposal.json', proposal)
    save(output / 'receipt.json', receipt)
    print(json.dumps(receipt, indent=2))
    if receipt['accepted']:
        train(output / 'successor-training', projection=receipt['projection'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['capture', 'evaluate'])
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    capture(args.output) if args.mode == 'capture' else evaluate(args.corpus, args.output)
