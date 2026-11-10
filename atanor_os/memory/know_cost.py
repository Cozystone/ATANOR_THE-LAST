"""O_KNOW_COST_PLAN.md: does knowing (the reader trained on other authors' worlds) make a body cheaper to learn? After the
course, the mind experiments in the practice world (k trials per action). A reader condition skips the calls the reader
is sure of (confidence >= TAU) and predicts with the hybrid; NONE is today's CHOOSE with the symbolic mind alone.
  python -m atanor_os.memory.know_cost one <cache_dir> <body> <seed> <out.json> --readers all5=path k1=path
  python -m atanor_os.memory.know_cost sum <dir>
"""
import argparse
import json
import pickle
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import torch

from ..rebuild.bench_predict import judge, train as sym_train
from ..rebuild.devbench import PRACTICE
from ..rebuild.experience import load_course
from ..rebuild.explore import READER, _newness, explore
from ..rebuild.effects import flat
from .episodic import Episode, by_tool
from .hybrid import ask, reader as load_reader
from .relational import Scene, scene_of

BODIES = ('board', 'clime', 'desk', 'dye', 'fs', 'view')
KS = (0, 1, 2, 3, 5, 10)
TAU = 0.95


class Skip:
    """CHOOSE's order (unknown calls, most new values first), except that a call the reader is sure of is not tried."""

    def __init__(self, model, scenes, body, device, k=10, seed=0):
        self.model, self.scenes, self.body, self.device, self.k = model, scenes, body, device, k
        self.rng = random.Random(seed)
        self.memo, self.skipped = {}, 0

    def sure(self, tool, args, before):
        same = [s for s in self.scenes if s.tool == tool and len(s.args) == len(args)]
        if not same or not all(before):
            return False
        key = (tool, tuple(args), json.dumps(before, sort_keys=True, default=str), len(same))
        if key not in self.memo:
            ex = same if len(same) <= self.k else self.rng.sample(same, self.k)
            q = Scene(self.body, tool, list(args), dict(zip(args, before)))
            vals, ans, conf = self.model.predict([Episode(ex, q)], self.device, 0.0)[0]
            self.memo[key] = conf >= TAU and vals is not None and not any(isinstance(v, tuple) for v in vals)
        return self.memo[key]

    def __call__(self, m, tool, args, before, y):
        if y is not None:
            return None
        if self.sure(tool, args, before):
            self.skipped += 1
            return None
        return (0, -_newness(m, flat(before)))


def bench(c, eff, model, scenes, device, seed):
    sym, qs = [], []
    for w, tool, args, before, truth, after in c['qs']:
        m = eff.model(tool, args)
        sym.append('never_seen' if m is None or not m.cases else judge(eff.predict(tool, args, before, reader=READER)['outcome'], truth))
        qs.append(Scene(c['body'], tool, args, dict(zip(args, before)), dict(zip(args, after)), truth[('r',)]))
    if model is not None:
        open_i = [i for i, x in enumerate(sym) if x == 'unknown']
        r = ask(model, by_tool(scenes), [qs[i] for i in open_i], device, 10, TAU, 1, random.Random(seed))
        for i, x in zip(open_i, r):
            sym[i] = x
    return dict(Counter(sym))


def one(a):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    c = pickle.loads((Path(a.cache) / f'{a.body}-s{a.seed}.pkl').read_bytes())
    names = json.loads((Path(c['course']) / c['body'] / 'names.json').read_text(encoding='utf-8'))
    ps = c['eval_seed'] - 100 + PRACTICE
    wd = Path(a.out).with_suffix('.w')
    course = [scene_of(dict(e, body=a.body)) for e in load_course(c['course'], a.body)
              if e.get('action') and e.get('before') is not None and e.get('after') is not None]
    models = {'NONE': None}
    for spec in a.readers:
        n, p = spec.split('=', 1)
        models[n] = load_reader(p, device)
    res = {'body': a.body, 'seed': a.seed}
    for name, model in models.items():
        for k in KS:
            eff, _ = sym_train(c['body'], c['course'], slack=1, tiered=True)
            scenes = list(course)
            trials, skipped = 0, 0
            if k:
                sel = 'CHOOSE' if model is None else Skip(model, scenes, a.body, device, seed=a.seed)

                def keep(e, eff=eff, scenes=scenes):
                    eff.observe(e)
                    if e.get('before') is not None and e.get('after') is not None:
                        scenes.append(scene_of(dict(e, body=a.body)))
                explore(eff, c['body'], names, ps, wd / f'{name}-{k}', per_action=k, selector=sel, keep=keep)
                trials = sum(explore.counts.values())
                skipped = getattr(sel, 'skipped', 0)
            res[f'{name}:{k}'] = bench(c, eff, model, scenes, device, a.seed)
            res[f'{name}:{k}:trials'] = trials
            res[f'{name}:{k}:skipped'] = skipped
    Path(a.out).write_text(json.dumps(res), encoding='utf-8')


def summ(d):
    T, N = defaultdict(Counter), defaultdict(int)
    for f in sorted(Path(d).glob('*.json')):
        r = json.loads(f.read_text(encoding='utf-8'))
        for k, v in r.items():
            if k.endswith(':trials'):
                N[(r['body'], k[:-7])] += v
            elif k.count(':') == 1:
                T[(r['body'], k)].update(v)
    conds = sorted({k.split(':')[0] for _, k in T}, key=lambda x: (x != 'NONE', x))
    rate = lambda c, x: c[x] / (sum(c.values()) or 1)
    cost, verdict = {}, {}
    for b in BODIES:
        if not any(k[0] == b for k in T):
            continue
        goal = 0.95 * rate(T[(b, 'NONE:10')], 'right')
        print(b, f'goal R >= {goal:.3f}')
        for name in conds:
            row = [f"k{k}: R {rate(T[(b, f'{name}:{k}')], 'right'):.3f} W {rate(T[(b, f'{name}:{k}')], 'wrong'):.4f} T {N[(b, f'{name}:{k}')]}" for k in KS]
            reached = next((k for k in KS if rate(T[(b, f'{name}:{k}')], 'right') >= goal), None)
            cost[(b, name)] = None if reached is None else N[(b, f'{name}:{reached}')]
            print(f'  {name:6s}', ' | '.join(row), '| cost', cost[(b, name)])
        safe = all(rate(T[(b, f'all5:{k}')], 'wrong') <= rate(T[(b, f'NONE:{k}')], 'wrong') + 0.005 for k in KS)
        cn, ca, ck = cost[(b, 'NONE')], cost[(b, 'all5')], cost.get((b, 'k1'))
        o1 = ca is not None and cn is not None and ca <= 0.7 * cn
        o3 = o1 and (ck is None or ca < ck)
        verdict[b] = {'O1': o1, 'safe': safe, 'O3': o3}
    n1 = sum(v['O1'] for v in verdict.values())
    n3 = sum(v['O3'] for v in verdict.values())
    tot = {n: sum(cost[(b, n)] or 0 for b in verdict) for n in conds}
    print('per body', verdict)
    print('total cost (bodies that reached)', tot)
    o2 = all(v['safe'] for v in verdict.values())
    print(json.dumps({'O1': n1 >= 4, 'O2': o2, 'O3': n1 > 0 and n3 * 2 >= n1, 'bodies_O1': n1,
                      'PASS': bool(n1 >= 4 and o2 and n3 * 2 >= n1)}))


if __name__ == '__main__':
    if sys.argv[1] == 'sum':
        summ(sys.argv[2])
        sys.exit(0)
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd')
    ap.add_argument('cache')
    ap.add_argument('body')
    ap.add_argument('seed', type=int)
    ap.add_argument('out')
    ap.add_argument('--readers', nargs='+', default=[])
    one(ap.parse_args())
