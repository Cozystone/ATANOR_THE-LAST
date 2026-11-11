"""LAW_MEMORY_PLAN.md: a per-attribute law memory in one world (worlds by separate authors, never read here).
A law = for one attribute (or for 'ok'), the smallest set S (at most 2) of before-attributes that fixes its value after
(as a value, or as a change for numbers) in everything lived with one tool, with the table S -> result. Laws of the same
attribute, form and S are pooled when they never contradict. A late tool: m of its own course experiences pick the laws
that fit them; the picked laws answer its queries.   LIB-m: m shots + library   OWN-m: m shots only   OWN-all: its whole course
OTHER-m: m shots + the library of another world of the same author. Scored per attribute on the late places (24 on).
  python -m atanor_os.memory.lawlib --authors a b --worlds 0 1 [--lived 5 20] [--shots 3 8]
"""
import sys
from collections import Counter, defaultdict
from itertools import combinations
from .oneworld import author

def feats(e):
    return {(i, k): v for i, a in enumerate(e['args']) for k, v in e['before'][a].items()}

def targets(es):
    """outputs worth a law: 'ok', and every (pos, attr) that changes in some success."""
    out = [('ok',)] if any(not e['ok'] for e in es) else []
    f0 = feats(es[0])
    for (i, k) in f0:
        if any(e['ok'] and e['after'][e['args'][i]][k] != e['before'][e['args'][i]][k] for e in es):
            out.append((i, k))
    return out

def rows_of(es, y):
    if y == ('ok',):
        return [(feats(e), e['ok']) for e in es]
    i, k = y
    return [(feats(e), e['after'][e['args'][i]][k]) for e in es if e['ok']]

def rel(y, x):
    return ('self', x[1]) if y != ('ok',) and x[0] == y[0] else x

def fit(rows, y):
    """-> [(mode, S, table)] for the smallest S that makes the result a function; S in the tool's own positions."""
    if not rows:
        return []
    keys = sorted(rows[0][0], key=str)
    modes = ['value']
    if y != ('ok',) and all(isinstance(v, int) and isinstance(f[y], int) for f, v in rows):
        modes.append('delta')
    for size in (0, 1, 2):
        got = []
        for S in combinations(keys, size):
            for mode in modes:
                t, okk = {}, True
                for f, v in rows:
                    key = tuple(f[s] for s in S)
                    r = v - f[y] if mode == 'delta' else v
                    if t.setdefault(key, r) != r:
                        okk = False
                        break
                if okk:
                    got.append((mode, S, t))
        if got:
            return got[:6]
    return []

def answer(law, f, y):
    mode, S, t = law
    try:
        r = t.get(tuple(f[s] for s in S))
    except KeyError:
        return None
    if r is None:
        return None
    return f[y] + r if mode == 'delta' else r

def library(w, n):
    lib = defaultdict(list)                        # (attr or 'ok', mode, S relative) -> [table]
    for p in w['places'][:n]:
        by = defaultdict(list)
        for e in p['course'] + p['queries']:
            by[e['tool']].append(e)
        for es in by.values():
            for y in targets(es):
                for mode, S, t in fit(rows_of(es, y), y):
                    sig = (y[-1] if y != ('ok',) else 'ok', mode, tuple(rel(y, s) for s in S))
                    for old in lib[sig]:
                        if all(old.get(k, v) == v for k, v in t.items()):
                            old.update(t)
                            break
                    else:
                        lib[sig].append(dict(t))
    return lib

def candidates(lib, y, f0):
    """library laws put into this tool's positions."""
    name = y[-1] if y != ('ok',) else 'ok'
    out = []
    for (a, mode, Srel), tables in lib.items():
        if a != name:
            continue
        S = tuple((y[0], s[1]) if s[0] == 'self' else s for s in Srel)
        if all(s in f0 for s in S):
            out += [(mode, S, t) for t in tables]
    return out

def run(x, s, n, m):
    mod = author(x)
    w, wo = mod.world(s), mod.world(s + 500)
    libs = {'LIB': library(w, n), 'OTHER': library(wo, n)}
    C = defaultdict(Counter)
    for p in w['places'][24:]:
        by, bq = defaultdict(list), defaultdict(list)
        for e in p['course']:
            by[e['tool']].append(e)
        for e in p['queries']:
            bq[e['tool']].append(e)
        for tool, es in by.items():
            shots = es[:m]
            for y in targets(es):
                qs = rows_of(bq[tool], y)
                own_all, own_m = fit(rows_of(es, y), y)[:1], fit(rows_of(shots, y), y)[:1]
                picked = {}
                for nm, lib in libs.items():
                    sh = rows_of(shots, y)
                    ok = []
                    for law in candidates(lib, y, feats(es[0])):
                        a = [answer(law, f, y) for f, v in sh]
                        if sum(v is not None for v in a) >= min(2, len(sh)) and all(b is None or b == v for b, (f, v) in zip(a, sh)):
                            ok.append(law)
                    picked[nm] = ok
                kind = 'ok' if y == ('ok',) else 'effect'
                for f, v in qs:
                    for nm, laws in (('OWN-all', own_all), (f'OWN-{m}', own_m), (f'LIB-{m}', picked['LIB']), (f'OTHER-{m}', picked['OTHER'])):
                        a = {answer(l, f, y) for l in laws} - {None}
                        C[(kind, nm)]['right' if a == {v} else 'unknown' if len(a) != 1 else 'wrong'] += 1
    return C

def main():
    import argparse
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
                        tot[(x, n, m) + k].update(c)
    for k in sorted(tot):
        c = tot[k]
        t = sum(c.values())
        print(f"{k[0]} lived {k[1]:2d} shots {k[2]} {k[3]:6s} {k[4]:8s} R {c['right'] / t:.3f} W {c['wrong'] / t:.3f} n={t}")


if __name__ == '__main__':
    main()
