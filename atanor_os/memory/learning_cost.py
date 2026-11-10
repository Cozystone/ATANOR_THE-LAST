"""I_LEARNING_COST_PLAN.md: does a reader make a new body cheaper to learn? The symbolic mind predicts and decides as always;
the reader only orders the mind's own experiments: among the calls the mind does not know, the one the reader is least sure
of comes first. One body held out, its course, then k own trials per action.
  python -m atanor_os.memory.learning_cost one <cache_dir> <body> <seed> <reader.pt> <out.json> [--steps 1500]
  python -m atanor_os.memory.learning_cost sum <dir>
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
from ..rebuild.explore import explore
from .episodic import Episode, Episodic, train as reader_train
from .hybrid import reader as load_reader
from .relational import Scene, scene_of

BODIES = ('board', 'clime', 'desk', 'dye', 'fs', 'view')
KS = (1, 2, 3, 5, 10)
CONDS = ('NONE', 'UNTRAINED', 'GEN', 'LIFE')


def scenes_of_body(cache, body, seed):
    c = pickle.loads((Path(cache) / f'{body}-s{seed}.pkl').read_bytes())
    out = []
    for e in load_course(c['course'], body):
        if e.get('action') and e.get('before') is not None and e.get('after') is not None:
            e['body'] = body
            out.append(scene_of(e))
    return out


class Guide:
    """A chooser for explore: ranks the calls the symbolic mind does not know by the reader's confidence, lowest first."""

    def __init__(self, model, eff, device, k=10, seed=0):
        self.model, self.eff, self.device, self.k = model, eff, device, k
        self.rng = random.Random(seed)
        self.pool, self.done, self.memo = defaultdict(list), 0, {}

    def _sync(self):
        for row in self.eff.raw[self.done:]:
            body, tool, args, before, after, resp, t, actor = row
            if resp is None or not all(before) or not all(after):
                continue
            self.pool[(tool, len(args))].append(Scene(body, tool, list(args), dict(zip(args, before)), dict(zip(args, after)), resp))
        self.done = len(self.eff.raw)

    def __call__(self, m, tool, args, before, y):
        if y is not None:
            return None
        self._sync()
        same = self.pool.get((tool, len(args)), [])
        if not same or not all(before):
            return (0, 0.0)
        key = (tool, tuple(args), json.dumps(before, sort_keys=True, default=str), len(same))
        if key not in self.memo:
            ex = same if len(same) <= self.k else self.rng.sample(same, self.k)
            q = Scene(ex[0].body, tool, list(args), dict(zip(args, before)))
            self.memo[key] = self.model.predict([Episode(ex, q)], self.device, 0.0)[0][2]
        return (0, self.memo[key])


def bench(c, eff):
    r = Counter()
    for w, tool, args, before, truth, _ in c['qs']:
        m = eff.model(tool, args)
        if m is None or not m.cases:
            continue
        r[judge(eff.predict(tool, args, before, reader='BAYES0.99')['outcome'], truth)] += 1
    return dict(r)


def one(a):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    c = pickle.loads((Path(a.cache) / f'{a.body}-s{a.seed}.pkl').read_bytes())
    names = json.loads((Path(c['course']) / c['body'] / 'names.json').read_text(encoding='utf-8'))
    ps = c['eval_seed'] - 100 + PRACTICE
    out_f = Path(a.out)
    wd = out_f.with_suffix('.w')
    torch.manual_seed(a.seed)
    gen = load_reader(a.reader, device)
    untrained = Episodic(n_bucket=gen.n_bucket).to(device).eval()
    lived = [s for b in BODIES if b != a.body for s in scenes_of_body(a.cache, b, a.seed)]
    life = Episodic(n_bucket=gen.n_bucket)
    life.load_state_dict(gen.state_dict())
    reader_train(life, lived, device, steps=a.steps, k=10, batch=16, lr=1e-4, augment=True, biased=0.5, seed=a.seed)
    life.eval()
    models = {'NONE': None, 'UNTRAINED': untrained, 'GEN': gen, 'LIFE': life}
    res = {'body': a.body, 'seed': a.seed, 'lived_scenes': len(lived)}
    for name in CONDS:
        for k in KS:
            eff, _ = sym_train(c['body'], c['course'], slack=1, tiered=True)
            sel = 'CHOOSE' if models[name] is None else Guide(models[name], eff, device, seed=a.seed)
            explore(eff, c['body'], names, ps, wd / f'{name}-{k}', per_action=k, selector=sel)
            res[f'{name}:{k}'] = bench(c, eff)
            res[f'{name}:{k}:trials'] = sum(explore.counts.values())
    out_f.write_text(json.dumps(res), encoding='utf-8')


def summ(d):
    T, N = defaultdict(Counter), defaultdict(int)
    for f in sorted(Path(d).glob('*.json')):
        r = json.loads(f.read_text(encoding='utf-8'))
        for k, v in r.items():
            if k.endswith(':trials'):
                N[(r['body'], k[:-7])] += v
            elif ':' in k:
                T[(r['body'], k)].update(v)
    rate = lambda c, x: c[x] / (sum(c.values()) or 1)
    verdict = {}
    tot = Counter()
    for b in BODIES:
        if not any(k[0] == b for k in T):
            continue
        goal = 0.95 * rate(T[(b, 'NONE:10')], 'right')
        print(b, f'goal R >= {goal:.3f}')
        cost = {}
        for name in CONDS:
            row = []
            for k in KS:
                c = T[(b, f'{name}:{k}')]
                row.append(f"k{k}: R {rate(c, 'right'):.3f} W {rate(c, 'wrong'):.4f} T {N[(b, f'{name}:{k}')]}")
            reached = next((k for k in KS if rate(T[(b, f'{name}:{k}')], 'right') >= goal), None)
            cost[name] = N[(b, f'{name}:{reached}')] if reached else None
            print(f'  {name:9s}', ' | '.join(row), '| cost', cost[name])
            if cost[name]:
                tot[name] += cost[name]
        safe = all(rate(T[(b, f'LIFE:{k}')], 'wrong') <= rate(T[(b, f'NONE:{k}')], 'wrong') + 0.005 for k in KS)
        i1 = cost['LIFE'] is not None and cost['NONE'] is not None and cost['LIFE'] <= 0.7 * cost['NONE']
        i3 = i1 and cost['UNTRAINED'] is not None and cost['LIFE'] < cost['UNTRAINED']
        verdict[b] = {'I1': i1, 'safe': safe, 'I3': i3}
    n1 = sum(v['I1'] for v in verdict.values())
    n3 = sum(v['I3'] for v in verdict.values())
    I1, I2, I3 = n1 >= 4, all(v['safe'] for v in verdict.values()), n1 > 0 and n3 * 2 >= n1
    print('per body', verdict)
    print('total cost', dict(tot))
    print(json.dumps({'I1': I1, 'I2': I2, 'I3': I3, 'I4_life_below_gen': tot['LIFE'] < tot['GEN'], 'bodies_I1': n1, 'PASS': bool(I1 and I2 and I3)}))


if __name__ == '__main__':
    if sys.argv[1] == 'sum':
        summ(sys.argv[2])
        sys.exit(0)
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd')
    ap.add_argument('cache')
    ap.add_argument('body')
    ap.add_argument('seed', type=int)
    ap.add_argument('reader')
    ap.add_argument('out')
    ap.add_argument('--steps', type=int, default=1500)
    one(ap.parse_args())
