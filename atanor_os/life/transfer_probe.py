"""Development probe (GOAL_STATE step B): what could a past life carry to a body never met? One candidate, measured.
Life statistic: what happened, in earlier bodies, on the calls whose start held a value that action had never met
(anonymous: the body's answer, and whether the attributes stayed as they were). It replaces the uniform guess for an
unseen cell in BayesAction, only there. Leave-one-body-out on the dev caches.
  NONE    uniform (today's core)      LIFE    the statistic of the other five bodies      SHUF  the same statistic with
  the answers permuted (a control: a prior of the same strength about nothing true)
Budget k: k chosen trials per action in the new body before answering (cost of learning it).
Usage: python -m atanor_os.life.transfer_probe one <cache_dir> <target> <seed> <out.json> | sum <dir>
"""
import json
import pickle
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from ..rebuild.bench_predict import judge, novelty, train
from ..rebuild.devbench import PRACTICE
from ..rebuild.effects import BayesAction, flat, freeze
from ..rebuild.explore import explore

BODIES = ('board', 'clime', 'desk', 'dye', 'fs', 'view')
KS = (0, 1, 3, 10)


def trained(c, k, wd):
    eff, _ = train(c['body'], c['course'], slack=1, tiered=True)
    if k:
        names = json.loads((Path(c['course']) / c['body'] / 'names.json').read_text(encoding='utf-8'))
        explore(eff, c['body'], names, c['eval_seed'] - 100 + PRACTICE, wd, per_action=k)
    return eff


def stats(eff):
    """Over one body, per call whose start held a value the action had not met: the answer, and whether the attributes
    stayed as they were; apart for a value on an attribute that had never varied in that action ('fixed') and else ('varied')."""
    out = {'fixed': (Counter(), Counter()), 'varied': (Counter(), Counter())}
    seen = defaultdict(lambda: defaultdict(set))
    for body, tool, args, before, after, resp, t, actor in sorted(eff.raw, key=lambda x: x[6]):
        key = (tool, len(args))
        x = flat(before)
        kind = None
        if seen[key]:
            if any(len(seen[key][k]) == 1 and v not in seen[key][k] for k, v in x.items()):
                kind = 'fixed'
            elif any(v not in seen[key][k] for k, v in x.items()):
                kind = 'varied'
        for k, v in x.items():
            seen[key][k].add(v)
        if kind is None or resp is None:
            continue
        out[kind][0][resp] += 1
        out[kind][1][all((after[i] or {}).get(q) == (before[i] or {}).get(q) for i in range(len(args)) for q in set(before[i] or {}) | set(after[i] or {}))] += 1
    return out


def q_of(prior, rng=None):
    res = {}
    for kind in ('fixed', 'varied'):
        r, a = Counter(), Counter()
        for p in prior:
            r.update(p[kind][0]), a.update(p[kind][1])
        if rng:
            k = sorted(r)
            v = [r[i] for i in k]
            rng.shuffle(v)
            r = Counter(dict(zip(k, v)))
            a = Counter({True: a[False], False: a[True]})
        n, m = sum(r.values()) or 1, sum(a.values()) or 1
        res[kind] = ({k: v / n for k, v in r.items()}, a[True] / m)
    return res


def predict(eff, tool, args, before, tau, q):
    m = eff.model(tool, args)
    if not m or not m.cases:
        return None
    x = flat(before)
    outs = sorted({k for c in m.cases for k in c.y}, key=str)
    if getattr(m, '_b', None) != len(m.cases):
        m._ba, m._b = BayesAction(m, tau), len(m.cases)
    y = {}
    for o in outs:
        v = out(m._ba, o, x, q)
        if v is None:
            return None
        y[o] = v
    return y


def out(ba, o, x, q):
    import math
    hyps, ins, n, V, seen_vals, fixed, prior = ba._fit(o)
    if not hyps:
        return None
    f = ba.feats(x)
    nc = len(fixed)
    miss = sum(f.get(v) != c for v, c in fixed.items())
    dist = defaultdict(float)

    def spread(mass, kind):
        if q is not None:
            r, keep = q[kind]
            if o == ('r',):
                for val, p in r.items():
                    dist[freeze(val)] += mass * p
                return
            dist[freeze(f.get(o, '-'))] += mass * keep
            mass *= 1 - keep
        for val in seen_vals:
            dist[val] += mass * 0.5 / V
        dist['<other>'] += mass * 0.5 / V
        for v in ins:
            dist[freeze(f.get(v))] += mass * 0.5 / n
    for w, R, tab in hyps:
        js = range(0, ba.max_s - len(R) + 1)
        match = w * sum(math.comb(nc - miss, j) * prior(len(R) + j) for j in js)
        other = w * sum((math.comb(nc, j) - math.comb(nc - miss, j)) * prior(len(R) + j) for j in js)
        key = tuple(f.get(s) for s in R)
        if key in tab:
            val, const, cop = tab[key]
            tot = const + 0.5 * len(cop) / n
            if val is not None:
                dist[val] += match * const / tot
            for v in cop:
                dist[freeze(f.get(v))] += match * (0.5 / n) / tot
        else:
            spread(match, 'varied')
        if other:
            spread(other, 'fixed')
    best = max(dist, key=dist.get)
    return json.loads(best) if dist[best] >= ba.tau and best != '<other>' else None


def one(d, target, seed, out_f):
    d = Path(d)
    wd = Path(out_f).with_suffix('.w')
    load = lambda b: pickle.loads((d / f'{b}-s{seed}.pkl').read_bytes())
    prior = [stats(trained(load(b), 10, wd / b)) for b in BODIES if b != target]
    c = load(target)
    qs = {'NONE': None, 'LIFE': q_of(prior), 'SHUF': q_of(prior, random.Random(seed))}
    res = {}
    for k in KS:
        eff = trained(c, k, wd / target)
        tr = len(eff.raw)
        for name, q in qs.items():
            r = Counter()
            for w, tool, args, before, truth, _ in c['qs']:
                if not eff.model(tool, args) or not eff.model(tool, args).cases:
                    continue
                r[judge(predict(eff, tool, args, before, 0.99, q), truth)] += 1
            res[f'{name}:{k}'] = dict(r)
        res[f'exp:{k}'] = tr
    res['q'] = qs['LIFE']
    Path(out_f).write_text(json.dumps(res), encoding='utf-8')


def summ(d):
    T = defaultdict(Counter)
    for f in sorted(Path(d).glob('*.json')):
        b = f.stem.split('-')[0]
        for k, v in json.loads(f.read_text(encoding='utf-8')).items():
            if ':' in k and not k.startswith('exp'):
                T[(b, k)].update(v)
    for b in BODIES:
        print(b)
        for k in KS:
            row = []
            for name in ('NONE', 'LIFE', 'SHUF'):
                c = T[(b, f'{name}:{k}')]
                n = sum(c.values()) or 1
                row.append(f'{name} R {c["right"] / n:.3f} W {c["wrong"] / n:.3f}')
            print('  k', k, ' | '.join(row))


if __name__ == '__main__':
    if sys.argv[1] == 'one':
        one(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5])
    else:
        summ(sys.argv[2])
