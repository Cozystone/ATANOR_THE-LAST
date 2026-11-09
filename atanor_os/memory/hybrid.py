"""H_LEARNED_MEMORY_PLAN.md: the learned reader as an organ beside the symbolic predictor, not instead of it.

One life's course in a body is all either gets. The symbolic mind answers what it is sure of (tau 0.99, as always). Where it
says 'unknown', the reader is asked: it reads up to k of the course's experiences of that action as examples (no weight
update; it was trained on generated worlds only) and answers only if it is confident (tau) and, with votes > 1, only if
that many independent draws of examples give the same whole outcome. A hash-bucket answer (a word it cannot produce) is
an abstention. Scored on the whole outcome, like the symbolic mind.
  EMPTY   the symbolic mind alone            HYBRID  symbolic, then the reader on its unknowns
  python -m atanor_os.memory.hybrid <reader.pt> <out_dir> [--ks 10] [--taus 0.5 0.7 0.9] [--votes 1 3] [--seeds 1 2 3 4 5]
  python -m atanor_os.memory.hybrid family <reader.pt>       (held-out generated worlds, a query never its own example)
"""
import argparse
import json
import pickle
import random
import sys
from collections import Counter
from pathlib import Path

import torch

from ..rebuild.bench_predict import judge
from ..rebuild.effects import Effects
from .episodic import Episode, Episodic, by_tool, score
from .lobo import BODIES, CACHE, load
from .relational import BLANK, RESP
from .worlds import generate


def reader(path, device):
    m = Episodic()
    m.load_state_dict(torch.load(path, map_location=device))
    return m.to(device).eval()


def strict(e, vals, ans):
    """right / wrong / unknown on the whole outcome; a bucket (no word produced) is an abstention."""
    if vals is None or any(isinstance(v, tuple) for v in vals):
        return 'unknown'
    q = e.query
    if ans != RESP[q.resp]:
        return 'wrong'
    return 'right' if list(vals) == list(q.after_values) else 'wrong'


def ask(model, pool, qs, device, k, tau, votes, rng):
    """-> per query: 'right' / 'wrong' / 'unknown' from the reader (unknown also when it has no example)."""
    out = ['unknown'] * len(qs)
    draws = []
    for v in range(votes):
        eps, idx = [], []
        for i, q in enumerate(qs):
            same = [x for x in pool.get((q.body, q.tool, len(q.args)), []) if x is not q]
            if not same:
                continue
            ex = same if len(same) <= k else rng.sample(same, k)
            eps.append(Episode(ex, q))
            idx.append(i)
        res = {}
        for j in range(0, len(eps), 64):
            bs = eps[j:j + 64]
            for e, i, (vals, ans, conf) in zip(bs, idx[j:j + 64], model.predict(bs, device, tau)):
                res[i] = (e, vals, ans)
        draws.append(res)
    for i in draws[0]:
        got = [d.get(i) for d in draws]
        if any(g is None or g[1] is None or any(isinstance(v, tuple) for v in g[1]) for g in got):
            continue
        if any((g[1], g[2]) != (got[0][1], got[0][2]) for g in got[1:]):
            continue                                       # the draws disagree: not known
        out[i] = strict(got[0][0], got[0][1], got[0][2])
    return out


def run(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = reader(a.reader, device)
    rows = []
    for body in a.bodies:
        tot = {}
        for seed in a.seeds:
            exps, tr, qs = load(body, seed)
            c = pickle.loads(Path(f'{CACHE}/{body}-s{seed}.pkl').read_bytes())
            eff = Effects(slack=1, tiered=True)
            for e in exps:
                eff.observe(e)
            sym = []
            for w, tool, args, before, truth, after in c['qs']:
                m = eff.model(tool, args)
                sym.append('never_seen' if m is None or not m.cases else judge(eff.predict(tool, args, before, reader='BAYES0.99')['outcome'], truth))
            pool = by_tool(tr)
            open_i = [i for i, s in enumerate(sym) if s == 'unknown']
            tot.setdefault('EMPTY', Counter()).update(sym)
            for k in a.ks:
                for tau in a.taus:
                    for votes in a.votes:
                        r = ask(model, pool, [qs[i] for i in open_i], device, k, tau, votes, random.Random(f'{seed}-{k}-{votes}'))
                        h = list(sym)
                        for i, x in zip(open_i, r):
                            h[i] = x
                        tot.setdefault(f'HYBRID k{k} tau{tau} v{votes}', Counter()).update(h)
                        tot.setdefault(f'reader-on-unknowns k{k} tau{tau} v{votes}', Counter()).update(r)
        for name, cnt in tot.items():
            n = sum(cnt.values())
            row = {'body': body, 'cond': name, 'n': n, **cnt}
            rows.append(row)
            print(f"{body:6s} {name:34s} R {cnt['right'] / n:.3f} W {cnt['wrong'] / n:.4f} ({cnt['wrong']}) U {(cnt['unknown'] + cnt['never_seen']) / n:.3f} n={n}", flush=True)
        (out / 'rows.json').write_text(json.dumps(rows), encoding='utf-8')
    print('== all bodies')
    for name in [r['cond'] for r in rows if r['body'] == a.bodies[0]]:
        cnt = Counter()
        for r in rows:
            if r['cond'] == name:
                cnt.update({k: v for k, v in r.items() if k in ('right', 'wrong', 'unknown', 'never_seen')})
        n = sum(cnt.values())
        print(f"ALL    {name:34s} R {cnt['right'] / n:.3f} W {cnt['wrong'] / n:.4f} ({cnt['wrong']}) n={n}", flush=True)


def family(path):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = reader(path, device)
    held = generate(300, 12, seed=2)                        # worlds never trained on (training used seed 1)
    for k in (1, 3, 10):
        for tau in (0.0, 0.5, 0.7, 0.9):
            r = score(model, held, held[:3000], device, k, random.Random(k), tau)
            n = sum(r.values())
            print(f"family k={k} tau={tau} R {r.get('right', 0) / n:.3f} W {r.get('wrong', 0) / n:.4f} n={n}", flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'family':
        family(sys.argv[2])
        sys.exit(0)
    ap = argparse.ArgumentParser()
    ap.add_argument('reader')
    ap.add_argument('out')
    ap.add_argument('--bodies', nargs='+', default=list(BODIES))
    ap.add_argument('--seeds', nargs='+', type=int, default=[1, 2, 3, 4, 5])
    ap.add_argument('--ks', nargs='+', type=int, default=[10])
    ap.add_argument('--taus', nargs='+', type=float, default=[0.5, 0.7, 0.9])
    ap.add_argument('--votes', nargs='+', type=int, default=[1, 3])
    a = ap.parse_args()
    if any(s > 5 for s in a.seeds):
        ap.error('development: seeds 1-5 only')
    run(a)
