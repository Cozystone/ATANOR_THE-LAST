"""H_LEARNED_MEMORY_PLAN.md: leave one body out. Train on five bodies' course experiences (dev seeds), meet the sixth with
0 and k of its own course experiences, against (b) the same model from the k alone, and (a) the empty symbolic mind
(the bench's ADAPTER numbers, course only). Word-cipher control on the sixth body.
  python -m atanor_os.memory.lobo <out_dir> [--bodies ...] [--seeds 1 2 3 4 5] [--ks 0 3 10 30] [--epochs 30] [--tau 0.9]
"""
import argparse
import glob
import json
import pickle
import random
import sys
import time
from collections import Counter
from pathlib import Path

import torch

from ..rebuild.bench_predict import judge
from ..rebuild.effects import Effects
from ..rebuild.experience import load_course
from .relational import Memory, Scene, cipher, scene_of, score, train

CACHE = 'D:/ATANOR-experiments/probe-work/stage1-dev/cache'
BODIES = ('board', 'clime', 'desk', 'dye', 'fs', 'view')


def load(body, seed):
    c = pickle.loads(Path(f'{CACHE}/{body}-s{seed}.pkl').read_bytes())
    exps = [e for e in load_course(c['course'], body) if e.get('action') and e.get('before') is not None and e.get('after') is not None]
    for e in exps:
        e['body'] = body
    train_sc = [scene_of(e) for e in exps]
    qs = []
    for w, tool, args, before, truth, after in c['qs']:
        resp = truth[('r',)]
        qs.append(Scene(body, tool, args, dict(zip(args, before)), dict(zip(args, after)), resp))
    return exps, train_sc, qs


def empty_mind(body, exps, c_qs):
    """(a) the symbolic predictor from this body's course only."""
    eff = Effects(slack=1, tiered=True)
    for e in exps:
        eff.observe(e)
    c = Counter()
    for w, tool, args, before, truth, after in c_qs:
        m = eff.model(tool, args)
        if m is None or not m.cases:
            c['never_seen'] += 1
            continue
        c[judge(eff.predict(tool, args, before, reader='BAYES0.99')['outcome'], truth)] += 1
    return dict(c)


def run(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    log = open(out / 'log.txt', 'a', encoding='utf-8')

    def say(*x):
        print(*x, flush=True)
        log.write(' '.join(map(str, x)) + '\n')
        log.flush()
    data = {(b, s): load(b, s) for b in BODIES for s in a.seeds}     # every body is lived; --bodies says which are held out
    rows = []
    for held in a.bodies:
        others = [sc for (b, s), (_, tr, _) in data.items() if b != held for sc in tr]
        held_train = [sc for (b, s), (_, tr, _) in data.items() if b == held for sc in tr]
        held_q = [q for (b, s), (_, _, qs) in data.items() if b == held for q in qs]
        rng = random.Random(f'{held}-cipher')
        held_q_c = cipher(held_q, rng)
        rng2 = random.Random(f'{held}-cipher')
        held_train_c = cipher(held_train, rng2)
        # (a) the empty symbolic mind
        ea = Counter()
        for s in a.seeds:
            c = pickle.loads(Path(f'{CACHE}/{held}-s{s}.pkl').read_bytes())
            ea.update(empty_mind(held, data[(held, s)][0], c['qs']))
        say(held, 'EMPTY-SYMBOLIC', dict(ea))
        rows.append({'held': held, 'cond': 'EMPTY-SYMBOLIC', 'k': None, **ea})
        torch.manual_seed(0)
        t0 = time.time()
        base = train(Memory(), others, device, epochs=a.epochs, seed=0)
        say(held, 'trained on five bodies', len(others), 'scenes', f'{time.time() - t0:.0f}s')
        for k in a.ks:
            rng = random.Random(k)
            shots = held_train if k >= len(held_train) else rng.sample(held_train, k)
            shots_c = held_train_c if k >= len(held_train_c) else [held_train_c[held_train.index(s)] for s in shots]
            for cond, tr_sc, q_sc in (('LIFE', shots, held_q), ('LIFE-CIPHER', shots_c, held_q_c), ('ALONE', shots, held_q)):
                torch.manual_seed(k)
                if cond.startswith('LIFE'):
                    m = Memory()
                    m.load_state_dict(base.state_dict())
                    m.to(device)
                else:
                    m = Memory().to(device)
                if tr_sc:
                    train(m, tr_sc, device, epochs=max(5, a.epochs // 2), lr=1e-4 if cond.startswith('LIFE') else 3e-4, seed=k)
                elif cond == 'ALONE':
                    continue                                   # nothing to learn from: no model
                r = score(m, q_sc, device, a.tau)
                say(held, cond, 'k', k, r)
                rows.append({'held': held, 'cond': cond, 'k': k, **r})
        (out / 'rows.json').write_text(json.dumps(rows), encoding='utf-8')
    summ(rows, say)


def summ(rows, say=print):
    for held in sorted({r['held'] for r in rows}):
        say('==', held)
        for r in rows:
            if r['held'] == held:
                n = sum(v for k, v in r.items() if k in ('right', 'wrong', 'unknown', 'never_seen'))
                say(f"  {r['cond']:15s} k={r['k']!s:5s} R {r.get('right', 0) / max(n, 1):.3f} W {r.get('wrong', 0) / max(n, 1):.3f} n={n}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--bodies', nargs='+', default=list(BODIES))
    ap.add_argument('--seeds', nargs='+', type=int, default=[1, 2, 3, 4, 5])
    ap.add_argument('--ks', nargs='+', type=int, default=[0, 3, 10, 30])
    ap.add_argument('--epochs', type=int, default=30)
    ap.add_argument('--tau', type=float, default=0.9)
    a = ap.parse_args()
    if any(s > 5 for s in a.seeds):
        ap.error('development: seeds 1-5 only')
    run(a)
