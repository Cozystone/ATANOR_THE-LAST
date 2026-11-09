"""Development probe (GOAL_STATE step B, first of three tries at compounding): a past life carries the FORM of what it
found, not any body's words. Over the other bodies, the mind reads off its own best explanations: how many inputs an
outcome depended on, and whether an outcome's value was a fixed value, its own earlier value (it stayed), or copied
from another input. That form replaces the flat prior of the explanation averaging in a new body.
  NONE today's flat prior   LIFE the form of the other five bodies   SHUF same strength, the form scrambled (control)
Usage: python -m atanor_os.life.schema_probe one <cache_dir> <target> <seed> <out.json> | sum <dir>
"""
import json
import math
import pickle
import random
import sys
import itertools
from collections import Counter, defaultdict
from pathlib import Path

from ..rebuild.bench_predict import judge
from ..rebuild.effects import BayesAction, flat, freeze
from .transfer_probe import BODIES, KS, trained

FLAT = {'size': [0.25] * 4, 'r': (0.5, None, 0.5), 'a': (0.5, None, 0.5)}      # (fixed value, own value, another input); None: own value is one input among the others


class Schema(BayesAction):
    def __init__(self, model, tau, q):
        super().__init__(model, tau)
        self.q = q

    def _kind(self, out):
        return self.q['r' if out == ('r',) else 'a']

    def _size(self, out):
        return self.q['size']

    def _weights(self, out, n):
        """-> (weight of a fixed value, f(input) -> weight of copying that input)."""
        c, s, o = self._kind(out)
        if s is None:                                                      # today's core: every input alike
            return c, lambda v: o / n
        has_self = out != ('r',)
        if not has_self:
            c, o = c / ((c + o) or 1), o / ((c + o) or 1)
            s = 0.0
        share = o / max(n - (1 if has_self else 0), 1)
        return c, lambda v: s if has_self and v == out else share

    def _fit(self, out):
        if out in self._cache:
            return self._cache[out]
        cases = [(self.feats(c.x), c.y.get(out)) for c in self.m.cases if out in c.y]
        ins = sorted({k for f, _ in cases for k in f}, key=str)
        n = max(len(ins), 1)
        V = len({freeze(y) for _, y in cases}) + 1
        pc, pv = self._weights(out, n)
        vals = {v: {freeze(f.get(v)) for f, _ in cases} for v in ins}
        fixed = {v: json.loads(next(iter(vals[v]))) for v in ins if len(vals[v]) == 1}
        vary = [v for v in ins if v not in fixed]
        memo, hyps = {}, []
        for k in range(0, self.max_s + 1):
            for R in itertools.combinations(vary, k):
                groups = defaultdict(list)
                for i, (f, _) in enumerate(cases):
                    groups[tuple(f.get(s) for s in R)].append(i)
                logp, tab = 0.0, {}
                for key, idx in groups.items():
                    t = tuple(idx)
                    if t not in memo:
                        cs = [cases[i] for i in idx]
                        ys = {freeze(y) for _, y in cs}
                        const = pc / V if len(ys) == 1 else 0.0
                        cop = {v: pv(v) for v in ins if pv(v) > 0 and all(f.get(v) == y for f, y in cs)}
                        ev = const + sum(cop.values())
                        memo[t] = None if ev <= 0 else (next(iter(ys)) if len(ys) == 1 else None, const, cop, math.log(ev))
                    cell = memo[t]
                    if cell is None:
                        logp = None
                        break
                    logp += cell[3]
                    tab[key] = cell[:3]
                if logp is not None:
                    hyps.append((logp, R, tab))
        size = self._size(out)
        prior = lambda s: size[s] / math.comb(n, s) if s <= n and s <= self.max_s else 0.0
        nc = len(fixed)
        if hyps:
            top = max(h[0] for h in hyps)
            hyps = [(math.exp(h[0] - top), h[1], h[2]) for h in hyps]
            z = sum(w * sum(math.comb(nc, j) * prior(len(R) + j) for j in range(0, self.max_s - len(R) + 1)) for w, R, _ in hyps) or 1.0
            hyps = [(w / z, R, tab) for w, R, tab in hyps]
        self._cache[out] = (hyps, ins, n, V, {freeze(y) for _, y in cases}, fixed, prior, pc, pv)
        return self._cache[out]

    def answer(self, out, x):
        hyps, ins, n, V, seen_vals, fixed, prior, pc, pv = self._fit(out)
        if not hyps:
            return None
        f = self.feats(x)
        nc = len(fixed)
        miss = sum(f.get(v) != c for v, c in fixed.items())
        dist = defaultdict(float)

        def spread(mass):
            for val in seen_vals:
                dist[val] += mass * pc / V
            dist['<other>'] += mass * pc / V
            for v in ins:
                dist[freeze(f.get(v))] += mass * pv(v)
        for w, R, tab in hyps:
            js = range(0, self.max_s - len(R) + 1)
            match = w * sum(math.comb(nc - miss, j) * prior(len(R) + j) for j in js)
            other = w * sum((math.comb(nc, j) - math.comb(nc - miss, j)) * prior(len(R) + j) for j in js)
            key = tuple(f.get(s) for s in R)
            if key in tab:
                val, const, cop = tab[key]
                tot = const + sum(cop.values())
                if val is not None:
                    dist[val] += match * const / tot
                for v, p in cop.items():
                    dist[freeze(f.get(v))] += match * p / tot
            else:
                spread(match)
            if other:
                spread(other)
        total = sum(dist.values()) or 1.0
        best = max(dist, key=dist.get)
        return json.loads(best) if dist[best] / total >= self.tau and best != '<other>' else None


def form_of(eff):
    """What this body's own best explanations looked like, anonymous: counts only."""
    size, kind = Counter(), {'r': Counter(), 'a': Counter()}
    for m in eff.models.values():
        if not m.cases:
            continue
        ba = Schema(m, 0.99, FLAT)
        for o in sorted({k for c in m.cases for k in c.y}, key=str):
            hyps = ba._fit(o)[0]
            if not hyps:
                continue
            w, R, tab = max(hyps, key=lambda h: h[0])
            size[len(R)] += 1
            k = 'r' if o == ('r',) else 'a'
            for val, const, cop in tab.values():
                tot = const + sum(cop.values())
                kind[k]['c'] += const / tot
                for v, p in cop.items():
                    kind[k]['s' if v == o else 'o'] += p / tot
    return size, kind


def q_of(forms, rng=None):
    size, kind = Counter(), {'r': Counter(), 'a': Counter()}
    for s, k in forms:
        size.update(s)
        for t in 'ra':
            kind[t].update(k[t])
    sz = [size[i] + 1 for i in range(4)]
    tot = sum(sz)
    q = {'size': [v / tot for v in sz]}
    for t in 'ra':
        v = [kind[t][x] + 1 for x in 'cso']
        s = sum(v)
        q[t] = tuple(x / s for x in v)
    if rng:
        rng.shuffle(q['size'])
        for t in 'ra':
            q[t] = tuple(rng.sample(list(q[t]), 3))
    return q


def predict(eff, tool, args, before, q, cls=Schema):
    m = eff.model(tool, args)
    if not m or not m.cases:
        return None
    x = flat(before)
    outs = sorted({k for c in m.cases for k in c.y}, key=str)
    key = (len(m.cases), id(q))
    store = m.__dict__.setdefault('_sch', {}) if hasattr(m, '__dict__') else {}
    if store.get('k') != key:
        store.clear()
        store.update(k=key, ba=cls(m, 0.99, q))
    y = {}
    for o in outs:
        v = store['ba'].answer(o, x)
        if v is None:
            return None
        y[o] = v
    return y


def one(d, target, seed, out_f):
    d = Path(d)
    wd = Path(out_f).with_suffix('.w')
    load = lambda b: pickle.loads((d / f'{b}-s{seed}.pkl').read_bytes())
    forms = [form_of(trained(load(b), 0, wd / b)) for b in BODIES if b != target]
    c = load(target)
    qs = {'NONE': FLAT, 'LIFE': q_of(forms), 'SHUF': q_of(forms, random.Random(seed))}
    res = {}
    for k in KS:
        eff = trained(c, k, wd / target)
        for name, q in qs.items():
            r = Counter()
            for w, tool, args, before, truth, _ in c['qs']:
                if not eff.model(tool, args) or not eff.model(tool, args).cases:
                    continue
                r[judge(predict(eff, tool, args, before, q), truth)] += 1
            res[f'{name}:{k}'] = dict(r)
    res['q'] = qs['LIFE']
    Path(out_f).write_text(json.dumps(res), encoding='utf-8')


def summ(d):
    T = defaultdict(Counter)
    for f in sorted(Path(d).glob('*.json')):
        b = f.stem.split('-')[0]
        for k, v in json.loads(f.read_text(encoding='utf-8')).items():
            if ':' in k:
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
