"""R_GATE_PLAN.md development: the reader answers only on tools it reads well in this body. Before answering, it predicts
the body's own course experiences leave-one-out, tool by tool (hybrid.self_check); a tool with share right below a is
not answered at all (conservative gate; L used the same check to LOWER the threshold, which added wrong).
  python -m atanor_os.memory.gate_dev <cache_dir> <reader.pt> --bodies ... --seeds ... [--accs 0.8 0.9 1.0] [--taus 0.95 0.9]
"""
import argparse
import pickle
import random
from collections import Counter
from pathlib import Path

import torch

from . import hybrid, lobo
from ..rebuild.bench_predict import judge
from ..rebuild.effects import Effects
from .episodic import by_tool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cache')
    ap.add_argument('reader')
    ap.add_argument('--bodies', nargs='+', required=True)
    ap.add_argument('--seeds', nargs='+', type=int, required=True)
    ap.add_argument('--accs', nargs='+', type=float, default=[0.8, 0.9, 1.0])
    ap.add_argument('--taus', nargs='+', type=float, default=[0.95, 0.9])
    ap.add_argument('--n-check', type=int, default=20)
    a = ap.parse_args()
    lobo.CACHE = a.cache
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = hybrid.reader(a.reader, device)
    allt = {}
    for body in a.bodies:
        tot = {}
        for seed in a.seeds:
            f = Path(a.cache) / f'{body}-s{seed}.pkl'
            if not f.exists():
                continue
            exps, tr, qs = lobo.load(body, seed)
            c = pickle.loads(f.read_bytes())
            eff = Effects(slack=1, tiered=True)
            for e in exps:
                eff.observe(e)
            sym = []
            for w, tool, args, before, truth, after in c['qs']:
                m = eff.model(tool, args)
                sym.append('never_seen' if m is None or not m.cases else judge(eff.predict(tool, args, before, reader='BAYES0.99')['outcome'], truth))
            pool = by_tool(tr)
            open_i = [i for i, s in enumerate(sym) if s == 'unknown']
            tot.setdefault('EMPTY', Counter()).update(sym)
            trust = hybrid.self_check(model, pool, device, 10, random.Random(f'sc-{body}-{seed}'), n=a.n_check)
            for tau in a.taus:
                conds = [('HYB', None)] + [(f'GATE@{x}', x) for x in a.accs]
                for name, acc in conds:
                    if acc is None:
                        r = hybrid.ask(model, pool, [qs[i] for i in open_i], device, 10, tau, 1, random.Random(f'{seed}-10-1'))
                    else:
                        r = hybrid.ask(model, pool, [qs[i] for i in open_i], device, 10, 1.01, 1, random.Random(f'{seed}-10-1'), trust, tau, acc)
                    h = list(sym)
                    for i, x in zip(open_i, r):
                        h[i] = x
                    tot.setdefault(f'{name} tau{tau}', Counter()).update(h)
        for name, cnt in tot.items():
            n = sum(cnt.values())
            print(f"{body:6s} {name:18s} R {cnt['right'] / n:.3f} W {cnt['wrong'] / n:.4f} ({cnt['wrong']}) n={n}", flush=True)
            allt.setdefault(name, Counter()).update(cnt)
    for name, cnt in allt.items():
        n = sum(cnt.values())
        print(f"ALL    {name:18s} R {cnt['right'] / n:.3f} W {cnt['wrong'] / n:.4f} ({cnt['wrong']}) n={n}", flush=True)


if __name__ == '__main__':
    main()
