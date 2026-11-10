"""V_TWO_SELVES_PLAN.md V1: learning by watching another Self. B has its own course; A (another course seed of the same
body) practises in its own practice world, and B watches: each of A's trials becomes an experience of B with actor
'other' (source 'observed'), never B's own. Then B practises (k trials per action) and is measured on its own evaluator
queries. Conditions: NONE (alone), OBS (watches A), OBSP (watches A but does not see the body's answer).
  python -m atanor_os.memory.observe_cost one <cache_dir> <body> <seed> <other_seed> <out.json>
  python -m atanor_os.memory.observe_cost sum <dir>
"""
import json
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path

from ..rebuild.bench_predict import train as sym_train
from ..rebuild.devbench import PRACTICE
from ..rebuild.explore import explore
from .know_cost import bench

KS = (0, 1, 2, 3, 5, 10)
CONDS = ('NONE', 'OBS', 'OBSP')


def watched(cache, body, other, work):
    """A's own practice (today's CHOOSE, 10 per action) in A's practice world: the trials as anyone watching sees them."""
    c = pickle.loads((Path(cache) / f'{body}-s{other}.pkl').read_bytes())
    names = json.loads((Path(c['course']) / c['body'] / 'names.json').read_text(encoding='utf-8'))
    eff, _ = sym_train(c['body'], c['course'], slack=1, tiered=True)
    seen = []

    def keep(e):
        eff.observe(e)
        seen.append(e)
    explore(eff, c['body'], names, c['eval_seed'] - 100 + PRACTICE, work, per_action=10, keep=keep)
    return seen


def one(cache, body, seed, other, out):
    c = pickle.loads((Path(cache) / f'{body}-s{seed}.pkl').read_bytes())
    names = json.loads((Path(c['course']) / c['body'] / 'names.json').read_text(encoding='utf-8'))
    wd = Path(out).with_suffix('.w')
    seen = watched(cache, body, other, wd / 'A')
    res = {'body': body, 'seed': seed, 'other': other, 'watched': len(seen)}
    for name in CONDS:
        for k in KS:
            eff, _ = sym_train(c['body'], c['course'], slack=1, tiered=True)
            if name != 'NONE':
                for i, e in enumerate(seen):               # after the course, before B's own practice
                    eff.observe({**e, 'actor': 'other', 'source': 'observed', 't': 500000 + i,
                                 'response': e['response'] if name == 'OBS' else None})
            trials = 0
            if k:
                explore(eff, c['body'], names, c['eval_seed'] - 100 + PRACTICE, wd / f'{name}-{k}', per_action=k)
                trials = sum(explore.counts.values())
            res[f'{name}:{k}'] = bench(c, eff, None, [], None, seed)
            res[f'{name}:{k}:trials'] = trials
    Path(out).write_text(json.dumps(res), encoding='utf-8')


def summ(d):
    T, N, W = defaultdict(Counter), defaultdict(int), Counter()
    for f in sorted(Path(d).glob('*.json')):
        r = json.loads(f.read_text(encoding='utf-8'))
        W[r['body']] += r['watched']
        for k, v in r.items():
            if k.endswith(':trials'):
                N[(r['body'], k[:-7])] += v
            elif isinstance(v, dict):
                T[(r['body'], k)].update(v)
    rate = lambda c, x: c[x] / (sum(c.values()) or 1)
    tot, v1, safe = Counter(), 0, True
    bodies = sorted({b for b, _ in T})
    for b in bodies:
        goal = 0.95 * rate(T[(b, 'NONE:10')], 'right')
        print(b, f'goal R >= {goal:.3f}', 'watched', W[b])
        cost = {}
        for name in CONDS:
            row = [f"k{k}: R {rate(T[(b, f'{name}:{k}')], 'right'):.3f} W {rate(T[(b, f'{name}:{k}')], 'wrong'):.4f} T {N[(b, f'{name}:{k}')]}" for k in KS]
            reached = next((k for k in KS if rate(T[(b, f'{name}:{k}')], 'right') >= goal), None)
            cost[name] = None if reached is None else N[(b, f'{name}:{reached}')]
            tot[name] += cost[name] or 0
            print(f'  {name:5s}', ' | '.join(row), '| cost', cost[name])
        v1 += cost['OBS'] is not None and cost['NONE'] is not None and cost['OBS'] <= 0.7 * cost['NONE']
        safe &= all(rate(T[(b, f'OBS:{k}')], 'wrong') <= rate(T[(b, f'NONE:{k}')], 'wrong') + 0.005 for k in KS)
    print('total cost', dict(tot))
    print(json.dumps({'bodies_cost_ok': v1, 'bodies': len(bodies), 'safe': bool(safe)}))


if __name__ == '__main__':
    if sys.argv[1] == 'sum':
        summ(sys.argv[2])
    else:
        one(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), sys.argv[6])
