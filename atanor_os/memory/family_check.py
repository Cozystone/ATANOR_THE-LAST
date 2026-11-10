"""J_FAMILY_PLAN.md: within a family of worlds, does a life in many worlds make a NEW world of the family cheaper than the
empty symbolic mind finds it? Each held-out world gives a course (n_course trials per tool, as the generator draws them)
and queries (other trials). The symbolic mind learns the course; the reader (trained on other worlds of the family, never
these) answers only the symbolic mind's unknowns, with abstention and votes.
  python -m atanor_os.memory.family_check <reader.pt> --family-seed S [--worlds 200] [--course 6 12 24] [--tau .9] [--votes 3]
"""
import argparse
import json
import random
from collections import Counter

import torch

from ..rebuild.bench_predict import judge
from ..rebuild.effects import Effects, outputs
from .episodic import by_tool
from .hybrid import ask, reader, self_check
from .relational import RESP
from .worlds import World


def as_lists(s):
    args = s.args
    before = [{k: v for i, k, v in s.toks if i == j} for j in range(len(args))]
    after = [{k: av for (i, k, _), av in zip(s.toks, s.after_values) if i == j} for j in range(len(args))]
    return args, before, after


def check(model, device, fam_seed, n_worlds, n_course, n_query, tau, votes, k, kinds=False, cal=None):
    tot = {'EMPTY': Counter(), 'HYBRID': Counter()}
    for w in range(n_worlds):
        world = World(fam_seed * 1000003 + w, True, kinds and w % 2 == 0)
        rng = random.Random(f'fam-{fam_seed}-{w}')
        course, queries = [], []
        for tool in world.tools:
            course += world.scenes(tool, n_course, rng, teacher=kinds)
            queries += world.scenes(tool, n_query, rng)
        eff = Effects(slack=1, tiered=True)
        for t, s in enumerate(course):
            args, before, after = as_lists(s)
            eff.observe({'t': t, 'body': s.body, 'source': 'program', 'actor': 'teacher', 'action': {'tool': s.tool, 'args': list(args)},
                         'before': dict(zip(args, before)), 'after': dict(zip(args, after)), 'response': {'ok': s.resp == 0, 'guard': None}})
        sym = []
        for q in queries:
            args, before, after = as_lists(q)
            m = eff.model(q.tool, args)
            truth = outputs(before, after, RESP[q.resp])
            sym.append('never_seen' if m is None or not m.cases else judge(eff.predict(q.tool, args, before, reader='BAYES0.99')['outcome'], truth))
        open_i = [i for i, s in enumerate(sym) if s == 'unknown']
        pool = by_tool(course)
        trust = self_check(model, pool, device, k, random.Random(f'sc{w}')) if cal else None
        r = ask(model, pool, [queries[i] for i in open_i], device, k, tau, votes, random.Random(w), trust, *(cal or (None, None)))
        hyb = list(sym)
        for i, x in zip(open_i, r):
            hyb[i] = x
        tot['EMPTY'].update(sym)
        tot['HYBRID'].update(hyb)
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('reader')
    ap.add_argument('--family-seed', type=int, required=True)
    ap.add_argument('--worlds', type=int, default=200)
    ap.add_argument('--course', nargs='+', type=int, default=[6, 12, 24])
    ap.add_argument('--queries', type=int, default=12)
    ap.add_argument('--tau', type=float, default=0.9)
    ap.add_argument('--votes', type=int, default=3)
    ap.add_argument('--k', type=int, default=10)
    ap.add_argument('--out', default=None)
    ap.add_argument('--kinds', action='store_true')
    ap.add_argument('--cal', nargs=2, type=float, default=None, help='tau_trusted min_acc')
    a = ap.parse_args()
    if a.family_seed == 1:
        ap.error('family seed 1 is the reader training family')
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = reader(a.reader, device)
    res = {}
    for n in a.course:
        tot = check(model, device, a.family_seed, a.worlds, n, a.queries, a.tau, a.votes, a.k, a.kinds, a.cal)
        res[n] = {k: dict(v) for k, v in tot.items()}
        for name, c in tot.items():
            m = sum(c.values())
            print(f"course {n:3d}/tool {name:7s} R {c['right'] / m:.3f} W {c['wrong'] / m:.4f} ({c['wrong']}) U {(c['unknown'] + c['never_seen']) / m:.3f} n={m}", flush=True)
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(json.dumps(res))


if __name__ == '__main__':
    main()
