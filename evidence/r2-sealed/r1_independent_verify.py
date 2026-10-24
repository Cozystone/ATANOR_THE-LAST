"""Independent stdlib-only native replay and arithmetic; no ATANOR imports.

Created outside candidate tree while its registered run executes. Read results
only after final report. Reconstruct environments from registered RNG, not from
claimed caller configuration. Preserve replay roots, no destructive cleanup.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import sqlite3
import tempfile
import sys

STUDY = sys.argv[1] if len(sys.argv) > 1 else 'R1'
assert STUDY in ('R1', 'R2')
ROOT = Path('D:/ATANOR-experiments/2026-09-17') / ('representation-' + STUDY.lower())
OUT = ROOT.parent / (STUDY.lower() + '-fresh-v1')


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def state(paths, spec):
    values = [p.read_bytes() if p.is_file() else None for p in paths]
    observed = {'handles': [f'n{i}' for i in range(3)],
                'kinds': [1 if v is not None else 0 for v in values],
                'sizes': [min(1., math.log1p(len(v)) / 16) if v is not None else 0. for v in values],
                'equal': [[float(a is not None and b is not None and a == b) for b in values] for a in values],
                'parent': [[0.] * 3 for _ in range(3)]}
    evidence = {f'n{i}': {'kind': 1 if v is not None else 0,
                         'size_bytes': len(v) if v is not None else None,
                         'sha256': sha_bytes(v) if v is not None else None} for i, v in enumerate(values)}
    if spec:
        matrices = {}
        for key, rule in spec['channels'].items():
            field = spec['fields'][rule['column']]
            raw = [getattr(p.stat(), field) if p.exists() else None for p in paths]
            matrix = []
            for a in raw:
                row = []
                for b in raw:
                    if a is None or b is None:
                        row.append(0.)
                    else:
                        bit = {'eq': a == b, 'lt': a < b, 'le': a <= b}[rule['operator']]
                        row.append(float(rule['predictions'][int(bit)]))
                matrix.append(row)
            matrices[key] = matrix
        observed.update(view_version=2, relations=matrices)
    return observed, evidence


def verify():
    p = json.loads((ROOT / 'docs' / (STUDY + '_PREREG_V1.json')).read_text())
    report = json.loads((OUT / 'report.json').read_text())
    rows = [json.loads(x) for x in (OUT / 'rows.jsonl').read_text().splitlines()]
    assert len(rows) == 4 * p['blocks']
    assert sha_bytes((OUT / 'rows.jsonl').read_bytes()) == report['rows_sha256']
    for filename, expected in p['source_hashes'].items():
        assert sha_bytes((ROOT / filename).read_bytes()) == expected
    for filename, expected in p['training_hashes'].items():
        assert sha_bytes((ROOT / p.get('training_directory', 'evidence/r1-training') / filename).read_bytes()) == expected
    r0 = json.loads((ROOT / 'evidence/r0-v1/trained.json').read_text())
    mapping = json.loads((ROOT / 'evidence/r0-v1/report.json').read_text())['supervisor_channel_mapping']
    spec = p.get('projection', {'version': 'stat-comparison-v1', 'fields': mapping, 'channels': {'r_c2_eq': r0['rule']}})
    rng = random.Random(p['seed'])
    replay_root = Path(tempfile.mkdtemp(prefix='atanor_r1_independent_'))
    actual_rows = []
    ordinal = 0
    for block in range(p['blocks']):
        seed = rng.getrandbits(60)
        payload = rng.randbytes(rng.randint(53, 511))
        target = rng.randrange(2)
        conditions = [False, True]
        rng.shuffle(conditions)
        for linked in conditions:
            arms = ['on', 'off']
            rng.shuffle(arms)
            for arm in arms:
                row = rows[ordinal]
                assert (row['block'], row['linked'], row['arm'], row['target']) == (block, linked, arm, target)
                local = random.Random(seed)
                names = [f'{local.getrandbits(80):020x}.bin' for _ in range(3)]
                cfg = {'paths': names, 'initial': {name: payload.hex() for i, name in enumerate(names) if i != 1 or not linked},
                       'initial_links': {names[1]: names[0]} if linked else {}, 'protected': ['n2'],
                       'operations': [{'id': 'empty', 'arity': 1}, {'id': 'unlink', 'arity': 1}, {'id': 'copy', 'arity': 2}]}
                if arm == 'on':
                    cfg['relation_spec'] = spec
                assert row['config'] == cfg
                root = replay_root / f'case_{ordinal:03d}'
                root.mkdir()
                paths = [root / name for name in names]
                for i, path in enumerate(paths):
                    if i != 1 or not linked:
                        path.write_bytes(payload)
                if linked:
                    os.link(paths[0], paths[1])
                db = OUT / f'case_{ordinal:03d}' / 'world.sqlite'
                conn = sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True)
                events = list(conn.execute('SELECT seq,kind,payload,digest FROM events ORDER BY seq'))
                conn.close()
                prev, steps, collateral, prediction, relation_exact = '', 0, False, None, True
                for seq, kind, text, digest in events:
                    assert sha_bytes((prev + kind + text).encode()) == digest
                    prev = digest
                    item = json.loads(text)
                    if kind == 'PREDICT':
                        action = item['action']
                        prediction = item['prediction']
                    if kind == 'DISPATCH':
                        assert steps < 2
                        args = [int(h[1:]) for h in action['args']]
                        assert all(0 <= i < 3 for i in args) and args[-1] != 2
                        try:
                            if action['op'] == 'empty':
                                assert len(args) == 1
                                paths[args[0]].write_bytes(b'')
                            elif action['op'] == 'unlink':
                                assert len(args) == 1
                                paths[args[0]].unlink()
                            else:
                                assert action['op'] == 'copy' and len(args) == 2
                                shutil.copyfile(paths[args[0]], paths[args[1]])
                            succeeded = True
                        except OSError:
                            succeeded = False
                        steps += 1
                    if kind in ('BEGIN', 'OBSERVE', 'RESULT'):
                        frame, evidence = state(paths, spec if arm == 'on' else None)
                        assert item['frame'] == frame and item['evidence'] == evidence
                        if kind == 'RESULT':
                            assert item['succeeded'] is succeeded
                            collateral |= evidence[f'n{1-target}']['sha256'] != sha_bytes(payload)
                            if arm == 'on':
                                relation_exact &= all(branch['state']['relations'] == frame['relations']
                                                      for branch in prediction['outcomes'])
                success = paths[target].is_file() and paths[target].read_bytes() == b''
                success &= paths[1-target].is_file() and paths[1-target].read_bytes() == payload
                success &= paths[2].read_bytes() == payload
                assert (bool(success), collateral, steps, relation_exact) == (
                    row['native_success'], row['collateral'], row['steps'], row['relation_effect_exact'])
                original_paths = [Path(row['native_root']) / name for name in names]
                assert state(original_paths, spec if arm == 'on' else None) == state(paths, spec if arm == 'on' else None)
                actual_rows.append((block, arm, bool(success), collateral, steps, linked))
                ordinal += 1
    for arm in ('on', 'off'):
        selected = [r for r in actual_rows if r[1] == arm]
        claimed = report['scores'][arm]
        assert claimed['n'] == len(selected)
        assert claimed['successes'] == sum(r[2] for r in selected)
        assert claimed['collateral_cases'] == sum(r[3] for r in selected)
        assert claimed['actions'] == sum(r[4] for r in selected)
    lift = [(sum((1 if arm == 'on' else -1) * success for b, arm, success, _, _, _ in actual_rows if b == block) / 2)
            for block in range(p['blocks'])]
    rng = random.Random(p['bootstrap_seed'])
    boot = sorted(sum(rng.choice(lift) for _ in lift) / len(lift) for _ in range(p['bootstrap_replicates']))
    assert report['success_lift'] == sum(lift) / len(lift)
    assert report['paired_lcb95'] == boot[int(.05 * len(boot))]
    result = {'independent_native_replay': 'PASS', 'episodes': len(rows), 'replay_root': str(replay_root),
              'raw_arithmetic': 'PASS', 'report_sha256': sha_bytes((OUT / 'report.json').read_bytes())}
    destination = OUT.parent / (STUDY.lower() + '-independent-verification.json')
    with destination.open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    verify()
