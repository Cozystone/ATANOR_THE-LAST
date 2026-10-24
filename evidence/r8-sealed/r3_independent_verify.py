"""Stdlib-only seeded reconstruction and native replay; no candidate imports."""
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import sqlite3
import tempfile

BASE = Path('D:/ATANOR-experiments/2026-09-17')
ROOT = BASE / 'representation-r3'
OUT = BASE / 'r3-fresh-v1'
sha = lambda b: hashlib.sha256(b).hexdigest()

def observe(paths, spec):
    values = [p.read_bytes() if p.is_file() else None for p in paths]
    n = len(paths)
    frame = {'handles': [f'n{i}' for i in range(n)],
        'kinds': [int(v is not None) for v in values],
        'sizes': [min(1., math.log1p(len(v))/16) if v is not None else 0. for v in values],
        'equal': [[float(a is not None and b is not None and a == b) for b in values] for a in values],
        'parent': [[0.] * n for _ in values], 'view_version': 2, 'relations': {}}
    for key, rule in spec['channels'].items():
        field = spec['fields'][rule['column']]
        raw = [getattr(p.stat(), field) if p.exists() else None for p in paths]
        frame['relations'][key] = [[0. if a is None or b is None else
            float(rule['predictions'][int({'eq': a == b, 'lt': a < b, 'le': a <= b}[rule['operator']])])
            for b in raw] for a in raw]
    evidence = {f'n{i}': {'kind': int(v is not None), 'size_bytes': len(v) if v is not None else None,
                         'sha256': sha(v) if v is not None else None} for i, v in enumerate(values)}
    return frame, evidence

def main():
    p = json.loads((ROOT/'docs/R3_PREREG_V1.json').read_text())
    report = json.loads((OUT/'report.json').read_text())
    rows = [json.loads(x) for x in (OUT/'rows.jsonl').read_text().splitlines()]
    assert len(rows) == p['blocks'] * 4
    assert report['rows_sha256'] == sha((OUT/'rows.jsonl').read_bytes())
    for name, digest in p['source_hashes'].items():
        assert sha((ROOT/name).read_bytes()) == digest
    for name, digest in p['training_hashes'].items():
        assert sha((ROOT/'evidence/r3-training'/name).read_bytes()) == digest
    spec = json.loads((ROOT/'evidence/r2-discovery/receipt.json').read_text())['projection']
    rng = random.Random(p['seed'])
    replay_root = Path(tempfile.mkdtemp(prefix='atanor_r3_independent_'))
    ordinal, actual = 0, []
    for block in range(p['blocks']):
        count = 4 + block % 2
        seed = rng.getrandbits(60)
        payload = rng.randbytes(rng.randint(53, 511))
        goals = [False, True]
        rng.shuffle(goals)
        for collective in goals:
            arms = ['on', 'off']
            rng.shuffle(arms)
            for arm in arms:
                row = rows[ordinal]
                assert (row['block'], row['arm'], row['collective'], row['aliases_count']) == (block, arm, collective, count)
                local = random.Random(seed)
                names = [f'{local.getrandbits(72):018x}' for _ in range(count+1)]
                ordered = list(names)
                local.shuffle(ordered)
                handles = {name: f'n{ordered.index(name)}' for name in names}
                aliases = [handles[name] for name in names[:-1]]
                reference = handles[names[-1]]
                cfg = {'paths': ordered, 'initial': {names[-1]: payload.hex(), names[0]: payload.hex()},
                    'initial_links': {name: names[0] for name in names[1:-1]}, 'protected': [reference],
                    'operations': [{'id':'empty','arity':1},{'id':'unlink','arity':1},{'id':'copy','arity':2}],
                    'relation_spec': spec}
                assert row['config'] == cfg and row['aliases'] == aliases and row['reference'] == reference
                root = replay_root/f'case_{ordinal:03d}'
                root.mkdir()
                (root/names[0]).write_bytes(payload)
                (root/names[-1]).write_bytes(payload)
                for name in names[1:-1]:
                    os.link(root/names[0], root/name)
                paths = [root/name for name in ordered]
                db = OUT/f'case_{ordinal:03d}'/'world.sqlite'
                conn = sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True)
                events = list(conn.execute('SELECT seq,kind,payload,digest FROM events ORDER BY seq'))
                conn.close()
                prev, steps, dispatches, results = '', 0, 0, 0
                for seq, kind, text, digest in events:
                    assert sha((prev+kind+text).encode()) == digest
                    prev = digest
                    item = json.loads(text)
                    if kind == 'PREDICT':
                        action = item['action']
                    if kind == 'DISPATCH':
                        assert steps < 2
                        args = [int(h[1:]) for h in action['args']]
                        assert all(0 <= i < len(paths) for i in args)
                        assert action['args'][-1] != reference
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
                        dispatches += 1
                    if kind in ('BEGIN', 'OBSERVE', 'RESULT'):
                        frame, evidence = observe(paths, spec)
                        assert item['frame'] == frame and item['evidence'] == evidence
                        if kind == 'RESULT':
                            assert item['succeeded'] is succeeded
                            results += 1
                assert dispatches == results == row['steps']
                expected = {h: b'' if collective or i == 0 else payload for i,h in enumerate(aliases)}
                expected[reference] = payload
                success = all(paths[int(h[1:])].is_file() and paths[int(h[1:])].read_bytes() == value
                              for h,value in expected.items())
                assert success == row['native_success']
                assert observe([Path(row['native_root'])/name for name in ordered],spec) == observe(paths,spec)
                actual.append((block,arm,collective,success,steps))
                ordinal += 1
    for arm in ('on','off'):
        selected = [r for r in actual if r[1] == arm]
        score = report['scores'][arm]
        assert score['n'] == len(selected)
        assert score['successes'] == sum(r[3] for r in selected)
        assert score['collective_successes'] == sum(r[3] for r in selected if r[2])
        assert score['selective_successes'] == sum(r[3] for r in selected if not r[2])
        assert score['actions'] == sum(r[4] for r in selected)
    deltas = [sum((1 if a=='on' else -1)*s for b,a,c,s,n in actual if b==block)/2 for block in range(p['blocks'])]
    rng = random.Random(p['bootstrap_seed'])
    boot = sorted(sum(rng.choice(deltas) for _ in deltas)/len(deltas) for _ in range(10000))
    assert report['success_lift'] == sum(deltas)/len(deltas) and report['paired_lcb95'] == boot[500]
    result = {'independent_native_replay':'PASS','episodes':len(rows),'raw_arithmetic':'PASS',
              'report_sha256':sha((OUT/'report.json').read_bytes()),'replay_root':str(replay_root)}
    with (BASE/'r3-independent-verification.json').open('x') as f:
        json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))

if __name__ == '__main__':
    main()
