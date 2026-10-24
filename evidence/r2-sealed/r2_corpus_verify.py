"""Independent R2 observed-data/proposal audit; no ATANOR imports."""
import hashlib
import json
import math
from pathlib import Path
import random
from collections import Counter, defaultdict

ROOT = Path('D:/ATANOR-experiments/2026-09-17/representation-r2')
corpus = ROOT / 'evidence/r2-corpus'
manifest = json.loads((corpus / 'manifest.json').read_text())
receipt = json.loads((ROOT / 'evidence/r2-discovery/receipt.json').read_text())
prereg = json.loads((ROOT / 'docs/R2_PREREG_V1.json').read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


rng = random.Random(manifest['seed'])
fields = ['st_dev', 'st_ino', 'st_nlink', 'st_size', 'st_mode']
rng.shuffle(fields)
assert fields == manifest['raw_fields']
audited = 0
for phase in ('training', 'validation'):
    rows = json.loads((corpus / f'{phase}.json').read_text())
    assert digest(rows) == manifest[f'{phase}_digest'] == receipt[f'{phase}_digest']
    for pair in range(16):
        payload = rng.randbytes(rng.randint(1, 512))
        target = rng.randrange(2)
        conditions = [False, True]
        rng.shuffle(conditions)
        for variant, linked in enumerate(conditions):
            names = [f'{rng.getrandbits(96):024x}.bin' for _ in range(2)]
            paths = [Path(manifest['root']) / f'{phase}_{pair}_{variant}' / name for name in names]
            row = rows[2 * pair + variant]
            expected_raw = []
            for path in paths:
                info = path.stat()
                expected_raw.append([len(payload) if field == 'st_size' else getattr(info, field) for field in fields])
                assert info.st_nlink == 2 + pair % 4
            assert row['raw_before'] == expected_raw
            assert row['action'] == {'op': 'empty', 'args': [f'n{target}']}
            values = [path.read_bytes() for path in paths]
            assert values[target] == b'' and values[1-target] == (b'' if linked else payload)
            expected_before = {'handles': ['n0', 'n1'], 'kinds': [1, 1],
                'sizes': [math.log1p(len(payload)) / 16] * 2, 'equal': [[1., 1.], [1., 1.]], 'parent': [[0., 0.], [0., 0.]]}
            expected_after = dict(expected_before, sizes=[math.log1p(len(v)) / 16 for v in values],
                                  equal=[[float(a == b) for b in values] for a in values])
            assert row['before'] == expected_before and row['after'] == expected_after
            audited += 1
    original, refined = defaultdict(Counter), defaultdict(Counter)
    expression = receipt['proposal']
    for row in rows:
        key = digest([row['before'], row['action']])
        original[key][digest(row['after'])] += 1
        values = [v[expression['column']] for v in row['raw_before']]
        op = expression['operator']
        bits = [a == b if op == 'eq' else a < b if op == 'lt' else a <= b for a in values for b in values]
        refined[digest([key, bits])][digest(row['after'])] += 1
    prefix = 'train' if phase == 'training' else 'validation'
    assert sum(sum(c.values()) - max(c.values()) for c in original.values()) == receipt[f'{prefix}_errors_before']
    assert sum(sum(c.values()) - max(c.values()) for c in refined.values()) == receipt[f'{prefix}_errors_after']
assert hashlib.sha256((ROOT / 'evidence/r2-discovery/receipt.json').read_bytes()).hexdigest() == prereg['refinement_receipt_sha256']
assert receipt['projection'] == prereg['projection']
result = {'native_observation_audit': 'PASS', 'transitions': audited,
          'independent_refinement_arithmetic': 'PASS', 'projection_binding': 'PASS'}
with (ROOT.parent / 'r2-corpus-independent.json').open('x') as stream:
    json.dump(result, stream, indent=2)
print(json.dumps(result, indent=2))
