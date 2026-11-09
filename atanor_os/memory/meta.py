"""H_LEARNED_MEMORY_PLAN.md: train the example-reader on generated worlds (worlds.py), then meet the six real bodies as
worlds never seen, with k of each body's course experiences as examples and no weight update.
  python -m atanor_os.memory.meta <out> [--worlds 3000] [--per-tool 14] [--steps 6000] [--ks 1 3 10] [--tau 0.0 0.9 0.99]
Baselines per body: EMPTY (the symbolic predictor from the body's course), and ALONE-GEN (the same reader trained on
generated worlds only, no real body ever: that is the LIFE condition here; the five other bodies are not needed).
"""
import argparse
import json
import pickle
import random
import time
from collections import Counter
from pathlib import Path

import torch

from .episodic import Episodic, score, train
from .lobo import BODIES, CACHE, empty_mind, load
from .relational import cipher
from .worlds import generate


def run(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    log = open(out / 'log.txt', 'a', encoding='utf-8')

    def say(*x):
        print(*x, flush=True)
        log.write(' '.join(map(str, x)) + '\n')
        log.flush()
    t0 = time.time()
    gen = generate(a.worlds, a.per_tool, seed=1)
    say('generated', len(gen), 'scenes from', a.worlds, 'worlds', f'{time.time() - t0:.0f}s')
    held = generate(200, a.per_tool, seed=2)                 # worlds never trained on, same family
    torch.manual_seed(0)
    t0 = time.time()
    model = train(Episodic(), gen, device, steps=a.steps, k=max(a.ks), batch=a.batch, augment=a.augment, seed=0,
                  log=lambda s: say('META', s))
    say('trained', f'{time.time() - t0:.0f}s')
    torch.save(model.state_dict(), out / 'reader.pt')
    rows = []
    taus = sorted(set(a.tau) | {0.0})
    for k in a.ks:
        for tau in taus:
            r = score(model, held, held[: min(len(held), 3000)], device, k, random.Random(k), tau)
            say('HELD-GENERATED', 'k', k, 'tau', tau, r)
            rows.append({'held': 'generated', 'cond': 'META', 'k': k, 'tau': tau, **r})
    # H2's threshold is chosen on generated worlds only, never on a real body: the smallest tau at which wrong <= 1% there
    cal = None
    for tau in taus:
        rs = [r for r in rows if r['held'] == 'generated' and r['tau'] == tau]
        n = sum(sum(v for kk, v in r.items() if kk in ('right', 'wrong', 'unknown')) for r in rs)
        if n and sum(r.get('wrong', 0) for r in rs) / n <= 0.01:
            cal = tau
            break
    say('CALIBRATED tau (wrong <= 1% on generated worlds):', cal)
    if cal is not None and cal not in a.tau:
        a.tau = list(a.tau) + [cal]
    for body in a.bodies:
        ea = Counter()
        tr, qs = [], []
        for s in a.seeds:
            exps, trs, q = load(body, s)
            tr += trs
            qs += q
            c = pickle.loads(Path(f'{CACHE}/{body}-s{s}.pkl').read_bytes())
            ea.update(empty_mind(body, exps, c['qs']))
        say(body, 'EMPTY', dict(ea))
        rows.append({'held': body, 'cond': 'EMPTY', 'k': None, **ea})
        both = cipher(tr + qs, random.Random(f'{body}-c'))
        tr_c, qs_c = both[:len(tr)], both[len(tr):]
        for k in a.ks:
            for cond, shots, queries in (('META', tr, qs), ('META-CIPHER', tr_c, qs_c)):
                for tau in a.tau:
                    r = score(model, shots, queries, device, k, random.Random(k), tau)
                    say(body, cond, 'k', k, 'tau', tau, r)
                    rows.append({'held': body, 'cond': cond, 'k': k, 'tau': tau, **r})
        (out / 'rows.json').write_text(json.dumps(rows), encoding='utf-8')
    for body in ['generated'] + list(a.bodies):
        say('==', body)
        for r in rows:
            if r['held'] == body:
                n = sum(v for kk, v in r.items() if kk in ('right', 'wrong', 'unknown', 'never_seen'))
                say(f"  {r['cond']:12s} k={r['k']!s:5s} tau={r.get('tau', '-')!s:5s} R {r.get('right', 0) / max(n, 1):.3f} W {r.get('wrong', 0) / max(n, 1):.3f} n={n}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--bodies', nargs='+', default=list(BODIES))
    ap.add_argument('--seeds', nargs='+', type=int, default=[1, 2, 3, 4, 5])
    ap.add_argument('--ks', nargs='+', type=int, default=[1, 3, 10])
    ap.add_argument('--tau', nargs='+', type=float, default=[0.0, 0.9, 0.99])
    ap.add_argument('--worlds', type=int, default=3000)
    ap.add_argument('--per-tool', type=int, default=14)
    ap.add_argument('--steps', type=int, default=6000)
    ap.add_argument('--batch', type=int, default=16)
    ap.add_argument('--augment', action='store_true')
    a = ap.parse_args()
    if any(s > 5 for s in a.seeds):
        ap.error('development: seeds 1-5 only')
    run(a)
