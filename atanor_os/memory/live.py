"""LIVE_PLAN.md: a Self acting in one world. In a late place (never lived) it has no teacher: for every tool it tries calls
itself (the place's simulator), choosing a start it cannot yet predict when there is one. After T tries per tool, the
place's queries are asked: the whole outcome (refused or not, and every attribute after).
  PAST   has the law memory and the tools of the first n places of this world (LAW_MEMORY_PLAN.md, guards.py)
  NONE   the same learner with no past            OTHER  the past of another world of the same author
What a Self knows of a tool from its own tries: per attribute the smallest law that fits them, and refusal conditions
covering its refusals. PAST adds: laws of the memory that fit its tries where its own law has no answer, and the refusal
conditions of sibling tools when they agree.
  python -m atanor_os.memory.live --authors a b c --worlds 0 1 [--lived 20] [--tries 0 1 2 3 5 8 12 20 30]
"""
import argparse
import random
from collections import Counter, defaultdict
from itertools import permutations

from .guards import edges, instances, tools_of
from .lawlib import answer, candidates, feats, fit, library, rows_of, targets
from .oneworld import author


import os

SUPPORT = 2
FIT = int(os.environ.get('ATANOR_LIVE_FIT', '2'))          # a law of the memory must answer this many of the Self's own tries
SIBS = os.environ.get('ATANOR_LIVE_SIBS', '1') == '1'
CONDS = os.environ.get('ATANOR_LIVE_CONDS', '0') == '1'   # the world's refusal conditions from memory


class Knows:
    def __init__(self, E, lib=None, past=None):
        self.E = E
        self.targets, self.own, self.picked, self.seen = [], {}, {}, {}
        self.conds, self.loose, self.sibs = [], [], []
        if not E:
            return
        self.targets = [y for y in targets(E) if y != ('ok',)]
        self.conds, self.loose = edges([(feats(e), e['ok']) for e in E])
        f0 = feats(E[0])
        for y in f0:
            rows = rows_of(E, y)
            if y in self.targets:
                self.own[y] = fit(rows, y)[:1]
                if self.own[y]:                           # how often each start of the law was met in the Self's own tries
                    S = self.own[y][0][1]
                    self.seen[y] = Counter(tuple(f[s] for s in S) for f, _ in rows)
            if lib is not None and rows and y in self.targets:   # the memory is asked only about what was seen to change
                ok = []
                for law in candidates(lib, y, f0):
                    a = [answer(law, f, y) for f, v in rows]
                    if sum(v is not None for v in a) >= FIT and all(b is None or b == v for b, (f, v) in zip(a, rows)):
                        ok.append(law)
                self.picked[y] = ok
        if past is not None and CONDS:
            # the world's own refusal conditions (met in at least 2 earlier tools), put into this tool: one that has
            # held in a refusal here and in no success here is believed; one not yet met in a refusal is to be tested
            keys = Counter(c for t in past for c in t.keys_c)
            good = [f for f, o in ((feats(e), e['ok']) for e in E) if o]
            bad = [f for f, o in ((feats(e), e['ok']) for e in E) if not o]
            cands = []
            for key, n in keys.items():
                if n < 2:
                    continue
                for g in instances(key, f0):
                    if not any(g(f) for f in good):
                        cands.append((n, g))
            # the fewest of the world's conditions that explain the refusals met here are believed (those met in more
            # earlier tools first); the others that could still hold are to be tested, not believed
            left, chosen = list(bad), []
            while left and cands:
                n, g = max(cands, key=lambda c: (sum(c[1](f) for f in left), c[0]))
                if not any(g(f) for f in left):
                    break
                chosen.append(g)
                left = [f for f in left if not g(f)]
            own_t, own_l = edges([(f, False) for f in left] + [(f, True) for f in good]) if left else ([], [])
            self.conds = chosen + own_t
            self.loose = own_l + [g for _, g in cands if g not in chosen]
        if past is not None and SIBS:
            self.sibs = [t for t in past if t.agrees(E)]

    def predict(self, f):
        """-> ('refused',) | ('ok', {y: value}) | None (not known)."""
        if not self.E:
            return None
        a = {t.refused(f) for t in self.sibs}
        refused = a.pop() if len(a) == 1 else any(g(f) for g in self.conds)
        self.source = 'refused'
        if not refused and len(a) != 1 and any(g(f) for g in self.loose):
            return None                                   # between the refusals it met and the successes it met: not known
        if refused:
            return ('refused',)
        out = {}
        self.source = 'own'
        for y in f:
            v = None
            if y in self.own and self.own[y]:
                S = self.own[y][0][1]
                if self.seen[y][tuple(f[s] for s in S)] >= SUPPORT:   # an own law answers only where it was met that often
                    v = answer(self.own[y][0], f, y)
            if v is None and self.picked.get(y):
                got = {answer(l, f, y) for l in self.picked[y]} - {None}
                if len(got) == 1:
                    v = got.pop()
                    self.source = 'memory'
            if v is None:
                if y in self.own or self.picked.get(y):
                    return None
                v = f[y]                                  # never seen to change, and no law of the memory says it does
            out[y] = v
        return ('ok', out)


def score(k, qs):
    c = Counter()
    for e in qs:
        p = k.predict(feats(e))
        if p is None:
            c['unknown'] += 1
        elif p[0] == 'refused':
            c['right' if not e['ok'] else 'wrong'] += 1
        else:
            c['right' if e['ok'] and all(e['after'][e['args'][i]][a] == v for (i, a), v in p[1].items()) else 'wrong'] += 1
    return c


def attempt(sim, seed, tool, args):
    sim.reset(seed)
    before = {a: dict(sim.objects()[a]) for a in args}
    ok, after = sim.call(tool, list(args))
    return {'tool': tool, 'args': list(args), 'before': before, 'after': {a: dict(after.get(a, before[a])) if ok else before[a] for a in args}, 'ok': bool(ok)}


def trusted(tests):
    """GATE_LIVE_PLAN.md: a Self answers about a tool only when what it expected of the tool, before trying, mostly came
    true (at least 2 checked expectations, 2 of 3 right among the last 5)."""
    last = tests[-5:]
    return len(tests) >= 2 and sum(last) / len(last) >= 0.67


def came_true(p, e):
    if p[0] == 'refused':
        return not e['ok']
    return e['ok'] and all(e['after'][e['args'][i]][a] == v for (i, a), v in p[1].items())


def run(x, s, n, tries, late=24, look=20, gate=False):
    mod = author(x)
    w, wo = mod.world(s), mod.world(s + 500)
    pasts = {'PAST': (library(w, n), tools_of(w, n)), 'NONE': (None, None), 'OTHER': (library(wo, n), tools_of(wo, n))}
    if os.environ.get('ATANOR_LIVE_ONLY'):
        pasts = {os.environ['ATANOR_LIVE_ONLY']: pasts[os.environ['ATANOR_LIVE_ONLY']]}
    if gate:
        pasts = {'PAST': pasts['PAST'], 'NONE': pasts['NONE'], 'PAST-G': pasts['PAST'], 'NONE-G': pasts['NONE']}
    C = defaultdict(Counter)
    for pi, p in enumerate(w['places'][late:], late):
        sim = p['sim']
        bq = defaultdict(list)
        for e in p['queries']:
            bq[e['tool']].append(e)
        for tool, na in sorted(sim.tools().items()):
            if not bq[tool]:
                continue
            for cond, (lib, past) in pasts.items():
                rng = random.Random(f'{x}-{s}-{pi}-{tool}')          # the same starts on offer under every condition
                E, done, tests = [], set(), []
                G = cond.endswith('-G')
                for T in range(max(tries) + 1):
                    k = Knows(E, lib, past)
                    if T in tries:
                        C[(cond, T)].update(score(k, bq[tool]) if not G or trusted(tests) else Counter(unknown=len(bq[tool])))
                    if T == max(tries):
                        break
                    pick = None
                    for _ in range(look):
                        seed = rng.randrange(10 ** 6)
                        sim.reset(seed)
                        obs = sim.objects()
                        names = sorted(obs)
                        if len(names) < na:
                            continue
                        args = tuple(rng.sample(names, na))
                        if (seed, args) in done:
                            continue
                        pr = k.predict({(i, a): v for i, o in enumerate(args) for a, v in obs[o].items()})
                        pick = pick or (seed, args, pr)
                        if (pr is None) != (G and T % 2 == 1):      # gated: every other try checks an expectation of its own
                            pick = (seed, args, pr)
                            break
                    if pick is None:
                        break
                    done.add(pick[:2])
                    E.append(attempt(sim, pick[0], tool, pick[1]))
                    if pick[2] is not None:
                        tests.append(came_true(pick[2], E[-1]))
    return C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--authors', nargs='+', required=True)
    ap.add_argument('--worlds', nargs='+', type=int, required=True)
    ap.add_argument('--lived', type=int, default=20)
    ap.add_argument('--tries', nargs='+', type=int, default=[0, 1, 2, 3, 5, 8, 12, 20, 30])
    ap.add_argument('--gate', action='store_true')
    a = ap.parse_args()
    for x in a.authors:
        tot = defaultdict(Counter)
        for s in a.worlds:
            for k, c in run(x, s, a.lived, a.tries, gate=a.gate).items():
                tot[k].update(c)
        for cond in (('NONE', 'NONE-G', 'PAST', 'PAST-G') if a.gate else ('NONE', 'PAST', 'OTHER')):
            for T in a.tries:
                c = tot[(cond, T)]
                t = sum(c.values()) or 1
                print(f"{x} {cond:5s} tries {T:2d} R {c['right'] / t:.3f} W {c['wrong'] / t:.3f} n={t}", flush=True)


if __name__ == '__main__':
    main()
