"""SURVIVE_PLAN.md: a drive tied to the Self's own energy, in one world. A life goes through the late places (never
lived) with an amount of energy. A try costs 1. After its tries with a tool, that tool's queries come as jobs: a right
answer pays GAIN, a wrong one costs LOSS, passing costs nothing. At energy 0 the life is over.
  FIXED-T   always T tries per tool; answers whatever it can predict.
  DRIVE     what it does depends on its energy and on what answering has cost it so far:
            tries only while it has more than its reserve (half of the energy it had when it reached the tool, shared
            over the tools left in the place); every other try checks one of its own predictions, and it stops when
            what it expected has just come true 3 times, and never spends more tries on a tool than half of what the
            jobs of a tool have been worth in this life;
            answers a tool's jobs only if what it expected of that tool mostly came true (with no record there, its
            record in this life with that kind of answer); when one wrong answer would end it, only after 3 in a row.
Each with the past of this world (PAST) and without (NONE).
  python -m atanor_os.memory.survive --authors a b c --worlds 0 1 [--energy 30 150]
"""
import argparse
import random
from collections import Counter, defaultdict

from .guards import tools_of
from .lawlib import feats, library
from .live import Knows, attempt
from .oneworld import author

GAIN, LOSS = 3, 3
CHECK = (0, 1, 2, 3, 5, 8, 12, 16, 20, 25, 30)


def right(p, e):
    if p[0] == 'refused':
        return not e['ok']
    return e['ok'] and all(e['after'][e['args'][i]][a] == v for (i, a), v in p[1].items())


def life(w, x, s, lib, past, policy, energy, late=24, look=12):
    rec = defaultdict(lambda: [3, 1])                       # kind of answer -> [right, wrong] in this life (starts hopeful: it must answer to find out)
    out = Counter()
    jobs = []                                               # how many jobs each tool brought so far in this life
    for pi, p in enumerate(w['places'][late:], late):
        sim = p['sim']
        bq = defaultdict(list)
        for e in p['queries']:
            bq[e['tool']].append(e)
        tools = [(t, na) for t, na in sorted(sim.tools().items()) if bq[t]]
        for ti, (tool, na) in enumerate(tools):
            rng = random.Random(f'{x}-{s}-{pi}-{tool}')
            E, done, tests = [], set(), []
            reserve = energy - energy / (2 * (len(tools) - ti))
            k = Knows(E, lib, past)
            T = 0
            while T < 30:
                starts = []
                for _ in range(look):
                    seed = rng.randrange(10 ** 6)
                    sim.reset(seed)
                    obs = sim.objects()
                    if len(obs) < na:
                        continue
                    args = tuple(rng.sample(sorted(obs), na))
                    if (seed, args) not in done:
                        starts.append((seed, args, k.predict({(i, a): v for i, o in enumerate(args) for a, v in obs[o].items()})))
                if not starts:
                    break
                known = sum(pr is not None for _, _, pr in starts) / len(starts)
                if policy == 'DRIVE':
                    # it stops when it has no energy to spare, or when what it expected of this tool has just come true 3 times
                    if energy - 1 <= reserve or (len(tests) >= 3 and all(tests[-3:]) and known >= 0.7):
                        break
                    if jobs and T >= 0.5 * GAIN * sum(jobs) / len(jobs):   # never more tries than half of what such a tool has paid
                        break
                    want_test = T % 2 == 1                          # every other try checks a prediction of its own
                    order = sorted(starts, key=lambda z: (z[2] is None) == want_test)
                    step = 1
                else:
                    if T >= int(policy.split('-')[1]) or energy <= 1:
                        break
                    order = sorted(starts, key=lambda z: z[2] is not None)   # a start it cannot predict first
                    step = min([c for c in CHECK if c > T][0], int(policy.split('-')[1])) - T
                for seed, args, pr in order[:step]:
                    if energy <= 1:
                        break
                    done.add((seed, args))
                    e = attempt(sim, seed, tool, args)
                    if pr is not None:
                        tests.append(right(pr, e))
                    E.append(e)
                    energy -= 1
                    out['tries'] += 1
                    T += 1
                k = Knows(E, lib, past)
                if energy <= 1:
                    break
            jobs.append(len(bq[tool]))
            for e in bq[tool]:
                pr = k.predict(feats(e))
                if pr is None:
                    out['passed'] += 1
                    continue
                kind = k.source
                if policy == 'DRIVE':
                    if len(tests) >= 2:                             # its own record with this tool: did what it expected come true?
                        share = sum(tests[-5:]) / len(tests[-5:])
                        sure = len(tests) >= 3 and all(tests[-3:])
                    else:                                           # no record here yet: its record in this life with that kind of answer
                        r, wr = rec[kind]
                        share, sure = r / (r + wr), False
                    if share * GAIN - (1 - share) * LOSS <= 0 or (energy <= LOSS and not sure):
                        out['passed'] += 1
                        continue
                ok = right(pr, e)
                rec[kind][0 if ok else 1] += 1
                energy += GAIN if ok else -LOSS
                out['right' if ok else 'wrong'] += 1
                if energy <= 0:
                    out['died'] = 1
                    out['places'] = pi - late
                    return out
        out['places'] = pi - late + 1
    out['energy'] = energy
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--authors', nargs='+', required=True)
    ap.add_argument('--worlds', nargs='+', type=int, required=True)
    ap.add_argument('--energy', nargs='+', type=int, default=[30, 150])
    ap.add_argument('--policies', nargs='+', default=['FIXED-3', 'FIXED-8', 'FIXED-20', 'DRIVE'])
    ap.add_argument('--lived', type=int, default=20)
    a = ap.parse_args()
    for x in a.authors:
        tot = defaultdict(Counter)
        for s in a.worlds:
            w = author(x).world(s)
            pasts = {'PAST': (library(w, a.lived), tools_of(w, a.lived)), 'NONE': (None, None)}
            for pn, (lib, past) in pasts.items():
                for e0 in a.energy:
                    for pol in a.policies:
                        c = life(w, x, s, lib, past, pol, e0)
                        c['lives'] = 1
                        tot[(e0, pn, pol)].update(c)
        for k in sorted(tot):
            c = tot[k]
            n = c['lives']
            print(f"{x} energy {k[0]:3d} {k[1]:4s} {k[2]:8s} died {c['died']}/{n} right {c['right'] / n:6.1f} wrong {c['wrong'] / n:5.1f} tries {c['tries'] / n:6.1f} "
                  f"places {c['places'] / n:4.1f} end energy {c['energy'] / n:6.1f}", flush=True)


if __name__ == '__main__':
    main()
