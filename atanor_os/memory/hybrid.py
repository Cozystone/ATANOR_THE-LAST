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
from .episodic import Episode, Episodic, by_tool, right, score
from .lobo import BODIES, CACHE, load
from .relational import BLANK, RESP
from .worlds import generate


def reader(path, device):
    sd = torch.load(path, map_location=device)
    m = Episodic(n_bucket=sd['bucket.weight'].shape[0])    # older readers have hash buckets
    m.load_state_dict(sd)
    return m.to(device).eval()


strict = right


def prior_only(pool, qs, k, rng):
    """No learned model: the counted priors' own best guess (ablation: what the learning must add to). -> right/wrong/unknown"""
    out = []
    for q in qs:
        same = [x for x in pool.get((q.body, q.tool, len(q.args)), []) if x is not q]
        if not same:
            out.append('unknown')
            continue
        e = Episode(same if len(same) <= k else rng.sample(same, k), q)
        P, b, failed, Pc, bc = e.prior
        S, sb = P + Pc, b + bc
        vals = []
        for p in range(e.n_q):
            j = int(S[p].argmax())
            vals.append(BLANK if float(sb[p]) > float(S[p, j]) else e.rows[j][4])
        ans = 'failed' if failed > 0.5 else 'ok'
        if ans == 'failed':                                # a refused call leaves everything as it was
            vals = [v for _, _, v in q.toks]
        out.append('right' if ans == RESP[q.resp] and vals == list(q.after_values) else 'wrong')
    return out


def self_check(model, pool, device, k, rng, n=20):
    """How well the reader reads THIS world, tool by tool, from the world's own course: each of up to n course experiences
    predicted from k others (leave one out, no abstention). -> {(body, tool, nargs): share right}. Nothing outside the
    course is used; this is the Self testing its own reading where it can check it."""
    acc = {}
    for key, same in pool.items():
        if len(same) < 3:
            continue
        probe = same if len(same) <= n else rng.sample(same, n)
        eps = []
        for q in probe:
            rest = [x for x in same if x is not q]
            eps.append(Episode(rest if len(rest) <= k else rng.sample(rest, k), q))
        got = []
        for j in range(0, len(eps), 64):
            bs = eps[j:j + 64]
            got += [right(e, v, a) == 'right' for e, (v, a, c) in zip(bs, model.predict(bs, device, 0.0))]
        acc[key] = sum(got) / len(got)
    return acc


def ask(model, pool, qs, device, k, tau, votes, rng, trust=None, tau_trusted=None, min_acc=None):
    """trust: {(body, tool, nargs): share right in self_check}; a tool read at least min_acc right is answered at
    tau_trusted, every other tool at tau."""
    """-> per query: 'right' / 'wrong' / 'unknown' from the reader (unknown also when it has no example)."""
    out = ['unknown'] * len(qs)
    draws = []
    for v in range(votes):
        eps, idx = [], []
        for i, q in enumerate(qs):
            same = [x for x in pool.get((q.body, q.tool, len(q.args)), []) if x is not q]
            if not same:
                continue
            kk = min(k, len(same)) if votes == 1 else min(k, max(1, (2 * len(same) + 2) // 3))   # votes must see different examples
            ex = same if len(same) <= kk else rng.sample(same, kk)
            eps.append(Episode(ex, q))
            idx.append(i)
        res = {}
        for j in range(0, len(eps), 64):
            bs = eps[j:j + 64]
            for e, i, (vals, ans, conf) in zip(bs, idx[j:j + 64], model.predict(bs, device, 0.0)):
                q = e.query
                t = tau
                if trust is not None and trust.get((q.body, q.tool, len(q.args)), 0.0) >= min_acc:
                    t = tau_trusted
                res[i] = (e, vals, ans) if conf >= t else (e, None, None)
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
                trust = self_check(model, pool, device, k, random.Random(f'sc-{seed}')) if a.selfcal else None
                for tau in a.taus:
                    for votes in a.votes:
                        r = ask(model, pool, [qs[i] for i in open_i], device, k, tau, votes, random.Random(f'{seed}-{k}-{votes}'))
                        h = list(sym)
                        for i, x in zip(open_i, r):
                            h[i] = x
                        tot.setdefault(f'HYBRID k{k} tau{tau} v{votes}', Counter()).update(h)
                        for ma in (a.selfcal or []):
                            for tt in a.tau_trusted:
                                r2 = ask(model, pool, [qs[i] for i in open_i], device, k, tau, votes, random.Random(f'{seed}-{k}-{votes}'), trust, tt, ma)
                                h2 = list(sym)
                                for i, x in zip(open_i, r2):
                                    h2[i] = x
                                tot.setdefault(f'SELFCAL k{k} tau{tau}/{tt}@{ma} v{votes}', Counter()).update(h2)
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
            for ok_only in (False, True):
                r = score(model, held, held[:3000], device, k, random.Random(k), tau, ok_only)
                n = sum(r.values())
                print(f"family k={k} tau={tau} {'successes-only examples' if ok_only else 'any examples'} R {r.get('right', 0) / n:.3f} W {r.get('wrong', 0) / n:.4f} n={n}", flush=True)


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
    ap.add_argument('--selfcal', nargs='*', type=float, default=None, help='min self-check accuracy values; tau_trusted from --tau-trusted')
    ap.add_argument('--tau-trusted', nargs='+', type=float, default=[0.5, 0.7])
    a = ap.parse_args()
    if any(s > 5 for s in a.seeds):
        ap.error('development: seeds 1-5 only')
    run(a)
