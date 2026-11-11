"""Z_GROW_PLAN.md: does a life pile up? One reader starts empty and goes through worlds written by other authors, a few
at first and then more, keeping what it met (its own memory is replayed). At each age it meets the real bodies as the
hybrid does (symbolic first, the reader on its unknowns, k=10). FEW is the control: the same number of training steps at
every age but only the first worlds, so age in steps is equal and only the amount of life differs.
  python -m atanor_os.memory.grow <cache_dir> <out_dir> --seeds 1 2 3 [--ages 25 100 400 1500 3000] [--steps 1500] [--first 0]
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import torch

from . import hybrid, lobo
from .authors import family, scene
from .episodic import Episodic, train as reader_train

AUTHORS = 'abcde'


def worlds(lo, hi, first):
    """scenes of worlds number lo..hi-1 in the order lived (authors take turns)."""
    out = []
    for i in range(lo, hi):
        au, s = AUTHORS[i % len(AUTHORS)], first + i // len(AUTHORS)
        w = family(au).world(s)
        out += [scene(f'{au}:{s}', e) for e in w['course'] + w['queries']]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cache')
    ap.add_argument('out')
    ap.add_argument('--seeds', nargs='+', type=int, required=True)
    ap.add_argument('--ages', nargs='+', type=int, default=[25, 100, 400, 1500, 3000])
    ap.add_argument('--steps', type=int, default=1500)
    ap.add_argument('--first', type=int, default=0, help='first world seed of each author')
    ap.add_argument('--tau', type=float, default=0.95)
    ap.add_argument('--conds', nargs='+', default=['GROW', 'FEW'])
    ap.add_argument('--bodies', nargs='+', default=list(lobo.BODIES))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    lobo.CACHE = hybrid.CACHE = a.cache
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    rows = []
    for cond in a.conds:
        torch.manual_seed(0)
        model = Episodic().to(device)
        mem, lived = [], 0
        for n, age in enumerate(a.ages):
            if cond == 'GROW' or n == 0:
                mem += worlds(lived, age, a.first)
                lived = age
            model.train()
            reader_train(model, mem, device, steps=a.steps, k=10, batch=32, lr=3e-4, augment=False, biased=0.5, seed=n)
            path = out / f'{cond}-{age}.pt'
            torch.save(model.state_dict(), path)
            d = out / f'{cond}-{age}'
            hybrid.run(argparse.Namespace(reader=str(path), out=str(d), bodies=a.bodies, seeds=a.seeds, ks=[10], taus=[a.tau], votes=[1],
                                          selfcal=None, tau_trusted=[]))
            for r in json.loads((d / 'rows.json').read_text(encoding='utf-8')):
                rows.append(dict(r, life=cond, age=age, lived=lived, steps=(n + 1) * a.steps))
            (out / 'rows.json').write_text(json.dumps(rows), encoding='utf-8')
    print('== summary')
    for cond in a.conds:
        for age in a.ages:
            c, per = Counter(), {}
            for r in rows:
                if r['life'] == cond and r['age'] == age and r['cond'].startswith('HYBRID'):
                    c.update({k: r.get(k, 0) for k in ('right', 'wrong', 'n')})
                    per[r['body']] = round(r.get('right', 0) / r['n'], 3)
            e = Counter()
            for r in rows:
                if r['life'] == cond and r['age'] == age and r['cond'] == 'EMPTY':
                    e.update({k: r.get(k, 0) for k in ('right', 'n')})
            print(f"{cond:4s} age {age:5d} R {c['right'] / c['n']:.3f} W {c['wrong']} (empty {e['right'] / e['n']:.3f}) {per}", flush=True)


if __name__ == '__main__':
    main()
