"""GUARD_PLAN.md: refusals in one world. A tool is refused when one of a few conditions holds; the conditions are laws of
the world, and which of them a tool has goes with what the tool does. So: an earlier tool is a SIBLING of a new tool when
its own effect laws and its own refusal conditions agree with the new tool's m shots; the siblings' conditions answer
whether a query is refused (all siblings must agree, else unknown).
A tool's conditions: a greedy cover of its refusals by conditions that never hold in its successes (one attribute equal to
a value, a number at most / at least a bound, two attributes compared).
  SIB-m: m shots + siblings from the n places lived   OWN-all: the tool's own conditions from its whole course
  OWN-m: from its m shots only                         OTHER-m: siblings from another world of the same author
  python -m atanor_os.memory.guards --authors a b c --worlds 0 1 [--lived 5 20] [--shots 3 8]
"""
import argparse
from collections import Counter, defaultdict
from itertools import combinations

from .lawlib import answer, feats, fit, rows_of, targets
from .oneworld import author


def conditions(F):
    """F: [(feats, ok)] -> list of (name, fn) candidates, general first."""
    keys = sorted(F[0][0], key=str)
    out = []
    for z in keys:
        vals = {f[z] for f, _ in F}
        if all(isinstance(v, int) for v in vals):
            for c in sorted(vals, reverse=True):
                out.append((('le', z, c), lambda f, z=z, c=c: isinstance(f.get(z), int) and f[z] <= c))
            for c in sorted(vals):
                out.append((('ge', z, c), lambda f, z=z, c=c: isinstance(f.get(z), int) and f[z] >= c))
        for v in sorted(vals, key=str):
            out.append((('eq', z, v), lambda f, z=z, v=v: f.get(z) == v))
    for a, b in combinations(keys, 2):
        va, vb = F[0][0][a], F[0][0][b]
        if isinstance(va, int) and isinstance(vb, int):
            out.append((('lt', a, b), lambda f, a=a, b=b: isinstance(f.get(a), int) and isinstance(f.get(b), int) and f[a] < f[b]))
            out.append((('gt', a, b), lambda f, a=a, b=b: isinstance(f.get(a), int) and isinstance(f.get(b), int) and f[a] > f[b]))
        out.append((('same', a, b), lambda f, a=a, b=b: a in f and b in f and f[a] == f[b]))
        out.append((('differ', a, b), lambda f, a=a, b=b: a in f and b in f and f[a] != f[b]))
    return out


def cover(F):
    """-> [fn]: conditions never true in a success, chosen greedily to cover the refusals (each must cover 2 or all left)."""
    bad = [f for f, o in F if not o]
    good = [f for f, o in F if o]
    if not bad:
        return []
    pure = [(nm, g) for nm, g in conditions(F) if not any(g(f) for f in good)]
    left, chosen = list(bad), []
    while left:
        best = max(pure, key=lambda p: sum(p[1](f) for f in left), default=None)
        n = sum(best[1](f) for f in left) if best else 0
        if n == 0 or (n < 2 and n < len(left)):
            break
        chosen.append(best[1])
        left = [f for f in left if not best[1](f)]
    return chosen


class Tool:
    def __init__(self, es):
        self.nargs = len(es[0]['args'])
        self.keys = set(feats(es[0]))
        self.targets = [y for y in targets(es) if y != ('ok',)]
        self.laws = {y: fit(rows_of(es, y), y)[:1] for y in self.targets}
        self.conds = cover([(feats(e), e['ok']) for e in es])

    def refused(self, f):
        return any(g(f) for g in self.conds)

    def agrees(self, shots):
        if self.nargs != len(shots[0]['args']) or self.keys != set(feats(shots[0])):
            return False
        hit = 0
        for e in shots:
            f = feats(e)
            if self.refused(f) == e['ok']:
                return False
            if not e['ok']:
                continue
            for (i, k) in f:
                v = e['after'][e['args'][i]][k]
                laws = self.laws.get((i, k))
                if laws is None:
                    if v != f[(i, k)]:
                        return False                      # the shot changes what this tool never changes
                    continue
                a = answer(laws[0], f, (i, k)) if laws else None
                if a is not None:
                    if a != v:
                        return False
                    hit += 1
        return hit > 0


def tools_of(w, n):
    out = []
    for p in w['places'][:n]:
        by = defaultdict(list)
        for e in p['course'] + p['queries']:
            by[e['tool']].append(e)
        out += [Tool(es) for es in by.values()]
    return out


def run(x, s, n, m, late=24):
    mod = author(x)
    w, wo = mod.world(s), mod.world(s + 500)
    past = {'SIB': tools_of(w, n), 'OTHER': tools_of(wo, n)}
    C = defaultdict(Counter)
    for p in w['places'][late:]:
        by, bq = defaultdict(list), defaultdict(list)
        for e in p['course']:
            by[e['tool']].append(e)
        for e in p['queries']:
            bq[e['tool']].append(e)
        for tool, es in by.items():
            shots = es[:m]
            own_all, own_m = cover([(feats(e), e['ok']) for e in es]), cover([(feats(e), e['ok']) for e in shots])
            sib = {nm: [t for t in ts if t.agrees(shots)] for nm, ts in past.items()}
            for e in bq[tool]:
                f, kind = feats(e), 'refused' if not e['ok'] else 'ok'
                for nm, conds in (('OWN-all', own_all), (f'OWN-{m}', own_m)):
                    C[nm]['right' if any(g(f) for g in conds) != e['ok'] else 'wrong'] += 1
                    C[nm + ':' + kind]['right' if any(g(f) for g in conds) != e['ok'] else 'wrong'] += 1
                for nm, ts in sib.items():
                    a = {t.refused(f) for t in ts}
                    r = 'unknown' if len(a) != 1 else 'right' if a == {not e['ok']} else 'wrong'
                    C[f'{nm}-{m}'][r] += 1
                    C[f'{nm}-{m}:' + kind][r] += 1
    return C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--authors', nargs='+', required=True)
    ap.add_argument('--worlds', nargs='+', type=int, required=True)
    ap.add_argument('--lived', nargs='+', type=int, default=[5, 20])
    ap.add_argument('--shots', nargs='+', type=int, default=[3, 8])
    a = ap.parse_args()
    tot = defaultdict(Counter)
    for x in a.authors:
        for s in a.worlds:
            for n in a.lived:
                for m in a.shots:
                    for k, c in run(x, s, n, m).items():
                        tot[(x, n, m, k)].update(c)
    for k in sorted(tot):
        c = tot[k]
        t = sum(c.values())
        print(f"{k[0]} lived {k[1]:2d} shots {k[2]} {k[3]:16s} R {c['right'] / t:.3f} W {c['wrong'] / t:.3f} n={t}")


if __name__ == '__main__':
    main()
