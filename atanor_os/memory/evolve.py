"""EVOLVE_PLAN.md: the drive not written by hand. A genome holds the drive's numbers (how much of its energy a Self may
spend on trying, how many of its own predictions must come true before it stops, how often what it expected must have come
true before it answers, whether it is careful when one wrong answer would end it, how many tries a tool is worth, how
often a try checks a prediction). Genomes start at random; each lives short lives in development worlds; those that die
or do little are replaced by varied copies of those that live and work. Nothing of the hand-written drive is given.
  python -m atanor_os.memory.evolve grow <out.json> [--pop 12] [--gens 5]
  python -m atanor_os.memory.evolve test <genomes.json> <out.json> --worlds 130 131
"""
import argparse
import json
import random
from multiprocessing import Pool

from .guards import tools_of
from .lawlib import library
from .oneworld import author
from .survive import HAND, life

DEV = [('a', 0, 30, 'PAST'), ('b', 0, 150, 'NONE'), ('c', 0, 60, 'PAST'), ('a', 1, 60, 'NONE'), ('b', 1, 30, 'PAST'), ('c', 1, 150, 'NONE')]
_cache = {}


def setting(x, s, pn):
    if (x, s) not in _cache:
        w = author(x).world(s)
        _cache[(x, s)] = (w, library(w, 20), tools_of(w, 20))
    w, lib, past = _cache[(x, s)]
    return (w, lib, past) if pn == 'PAST' else (w, None, None)


def one(job):
    genome, x, s, e0, pn, last = job
    w, lib, past = setting(x, s, pn)
    c = life(w, x, s, lib, past, 'DRIVE' if genome != 'F8' else 'FIXED-8', e0, genome=None if genome in ('F8', 'HAND') else genome, last=last)
    return {'died': c['died'], 'right': c['right'], 'wrong': c['wrong'], 'tries': c['tries'], 'energy': c['energy']}


def rand_genome(rng):
    return {'spare': rng.random(), 'streak': rng.randrange(0, 6), 'answer': rng.random(), 'danger': rng.randrange(2),
            'payback': rng.uniform(0, 3), 'test': rng.random()}


def child(a, b, rng):
    g = {k: (a if rng.random() < 0.5 else b)[k] for k in a}
    for k in g:
        if rng.random() < 0.3:
            if k == 'streak':
                g[k] = max(0, min(5, g[k] + rng.choice((-1, 1))))
            elif k == 'danger':
                g[k] = 1 - g[k]
            else:
                hi = 3 if k == 'payback' else 1
                g[k] = max(0.0, min(hi, g[k] + rng.gauss(0, 0.15 * hi)))
    return g


def fitness(rs):
    return sum(r['right'] - 200 * r['died'] for r in rs)


def grow(a):
    rng = random.Random(a.seed)
    pop = [rand_genome(rng) for _ in range(a.pop)]
    hist = []
    with Pool(a.procs) as pool:
        for gen in range(a.gens):
            jobs = [(g, x, s, e0, pn, 24 + a.places) for g in pop for x, s, e0, pn in DEV]
            res = pool.map(one, jobs)
            scored = []
            for i, g in enumerate(pop):
                rs = res[i * len(DEV):(i + 1) * len(DEV)]
                scored.append((fitness(rs), sum(r['died'] for r in rs), sum(r['right'] for r in rs), g))
            scored.sort(key=lambda z: -z[0])
            hist.append({'gen': gen, 'deaths': sum(z[1] for z in scored), 'lives': len(jobs), 'best': scored[0][:3], 'mean_right': sum(z[2] for z in scored) / len(scored)})
            print(json.dumps(hist[-1]), flush=True)
            keep = [z[3] for z in scored[:a.pop // 2]]
            pop = keep + [child(rng.choice(keep), rng.choice(keep), rng) for _ in range(a.pop - len(keep))]
            json.dump({'history': hist, 'evolved': scored[0][3], 'first_random': None}, open(a.out, 'w'))
    rng0 = random.Random(a.seed)
    first = [rand_genome(rng0) for _ in range(a.pop)]
    json.dump({'history': hist, 'evolved': scored[0][3], 'random': first[:3], 'hand': HAND}, open(a.out, 'w'), indent=1)
    print('evolved', scored[0][3], flush=True)


def test(a):
    G = json.load(open(a.genomes))
    who = {'EVOLVED': G['evolved'], 'HAND': 'HAND', 'FIXED-8': 'F8', **{f'RANDOM{i}': g for i, g in enumerate(G['random'])}}
    conds = [(x, s, e0, pn) for x in 'abc' for s in a.worlds for e0 in (30, 150) for pn in ('PAST', 'NONE')]
    with Pool(a.procs) as pool:
        res = pool.map(one, [(g, x, s, e0, pn, None) for g in who.values() for x, s, e0, pn in conds])
    out = {}
    for i, name in enumerate(who):
        rs = res[i * len(conds):(i + 1) * len(conds)]
        out[name] = {'lives': len(rs), 'died': sum(r['died'] for r in rs), 'right': sum(r['right'] for r in rs), 'wrong': sum(r['wrong'] for r in rs),
                     'tries': sum(r['tries'] for r in rs), 'end_energy': sum(r['energy'] for r in rs),
                     'right_past': sum(r['right'] for r, c in zip(rs, conds) if c[3] == 'PAST'), 'right_none': sum(r['right'] for r, c in zip(rs, conds) if c[3] == 'NONE')}
        print(name, out[name], flush=True)
    json.dump(out, open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    g = sp.add_parser('grow')
    g.add_argument('out')
    g.add_argument('--pop', type=int, default=12)
    g.add_argument('--gens', type=int, default=5)
    g.add_argument('--places', type=int, default=4)
    g.add_argument('--seed', type=int, default=0)
    g.add_argument('--procs', type=int, default=12)
    t = sp.add_parser('test')
    t.add_argument('genomes')
    t.add_argument('out')
    t.add_argument('--worlds', nargs='+', type=int, required=True)
    t.add_argument('--procs', type=int, default=12)
    a = ap.parse_args()
    grow(a) if a.cmd == 'grow' else test(a)
