"""ONE_WORLD_PLAN.md: does a life pile up inside ONE world? Worlds written by separate authors (outside the repo, never
read here): one world has 30+ places that share objects and hidden laws; every place has its own tools. A Self has lived
the first n places (all their experiences are in its memory; the reader is trained further on them, half of every batch,
the other half replayed from the worlds read before). Then it meets the LATE places (from --late on, never lived) as the
hybrid does: the symbolic mind from that place's course, the reader on its unknowns (k=10).
  OWN    lived the first n places of this world          OTHER  lived n places of another world of the same author
  age 0 is the unchanged reader. OTHER has the same training and the same author's style, but not this world's laws.
  python -m atanor_os.memory.oneworld <out_dir> --authors a b --worlds 0 1 2 [--ages 2 5 10 20] [--late 24] [--steps 600]
"""
import argparse
import importlib.util
import json
import random
from collections import Counter
from pathlib import Path

import torch

from ..rebuild.bench_predict import judge
from ..rebuild.effects import Effects, outputs
from . import hybrid
from .authors import family, scene
from .carry import mixed_train
from .episodic import by_tool
from .know import DEFAULT

OW = Path('D:/ATANOR-experiments/2026-09-19/oneworld')


def author(x):
    spec = importlib.util.spec_from_file_location(f'ow_{x}', OW / f'ow_{x}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def lived(w, tag, n):
    out = []
    for i, p in enumerate(w['places'][:n]):
        out += [scene(f'{tag}:{i}', e) for e in p['course'] + p['queries']]
    return out


def meet(model, w, tag, late, device, tau, seed):
    tot = {'EMPTY': Counter(), 'HYBRID': Counter()}
    for i, p in enumerate(w['places'][late:], late):
        name = f'{tag}:{i}'
        eff = Effects(slack=1, tiered=True)
        course = []
        for t, e in enumerate(p['course']):
            eff.observe({'t': t, 'body': name, 'source': 'program', 'actor': 'teacher', 'action': {'tool': e['tool'], 'args': list(e['args'])},
                         'before': e['before'], 'after': e['after'], 'response': {'ok': bool(e['ok']), 'guard': None}})
            course.append(scene(name, e))
        sym, qs = [], []
        for e in p['queries']:
            args = list(e['args'])
            before, after = [e['before'][x] for x in args], [e['after'][x] for x in args]
            m = eff.model(e['tool'], args)
            truth = outputs(before, after, 'ok' if e['ok'] else 'failed')
            sym.append('never_seen' if m is None or not m.cases else judge(eff.predict(e['tool'], args, before, reader='BAYES0.99')['outcome'], truth))
            qs.append(scene(name, e))
        open_i = [j for j, x in enumerate(sym) if x == 'unknown']
        r = hybrid.ask(model, by_tool(course), [qs[j] for j in open_i], device, 10, tau, 1, random.Random(f'{seed}-{i}'))
        hyb = list(sym)
        for j, x in zip(open_i, r):
            hyb[j] = x
        tot['EMPTY'].update(sym)
        tot['HYBRID'].update(hyb)
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--authors', nargs='+', required=True)
    ap.add_argument('--worlds', nargs='+', type=int, required=True)
    ap.add_argument('--ages', nargs='+', type=int, default=[2, 5, 10, 20])
    ap.add_argument('--late', type=int, default=24)
    ap.add_argument('--steps', type=int, default=600)
    ap.add_argument('--lr', type=float, default=1e-4)
    ap.add_argument('--tau', type=float, default=0.95)
    ap.add_argument('--replay', type=int, default=60)
    ap.add_argument('--other-shift', type=int, default=500, help='OTHER lives in world seed + this')
    ap.add_argument('--base', default=DEFAULT)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    old = []
    for au in 'abcde':
        mod = family(au)
        for s in range(a.replay):
            x = mod.world(s)
            old += [scene(f'{au}:{s}', e) for e in x['course'] + x['queries']]
    rows = []
    for x in a.authors:
        mod = author(x)
        for s in a.worlds:
            w, tag = mod.world(s), f'ow{x}{s}'
            wo, tago = mod.world(s + a.other_shift), f'ow{x}{s + a.other_shift}'
            base = hybrid.reader(a.base, device)
            conds = [('BASE', 0, base)]
            for n in a.ages:
                for cond, ww, tt in (('OWN', w, tag), ('OTHER', wo, tago)):
                    m = hybrid.reader(a.base, device)
                    torch.manual_seed(0)
                    mixed_train(m, lived(ww, tt, n), old, device, a.steps, a.lr, 0.5)
                    conds.append((cond, n, m.eval()))
            for cond, n, m in conds:
                tot = meet(m, w, tag, a.late, device, a.tau, s)
                for k, c in tot.items():
                    if k == 'HYBRID' or cond == 'BASE':
                        rows.append({'author': x, 'world': s, 'life': cond if k == 'HYBRID' else 'EMPTY', 'age': n, **c})
                c = tot['HYBRID']
                nq = sum(c.values())
                print(f"{tag} {cond:5s} age {n:2d} R {c['right'] / nq:.3f} W {c['wrong']} n={nq}", flush=True)
            (out / 'rows.json').write_text(json.dumps(rows), encoding='utf-8')
    print('== summary')
    for x in a.authors + ['ALL']:
        for cond, n in [('EMPTY', 0), ('BASE', 0)] + [(c, n) for n in a.ages for c in ('OWN', 'OTHER')]:
            c = Counter()
            for r in rows:
                if (x == 'ALL' or r['author'] == x) and r['life'] == cond and r['age'] == n:
                    c.update({k: v for k, v in r.items() if k in ('right', 'wrong', 'unknown', 'never_seen')})
            nq = sum(c.values())
            if nq:
                print(f"{x:3s} {cond:5s} age {n:2d} R {c['right'] / nq:.3f} W {c['wrong']} ({c['wrong'] / nq:.4f}) n={nq}", flush=True)


if __name__ == '__main__':
    main()
