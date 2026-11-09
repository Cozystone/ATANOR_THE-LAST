"""H_LEARNED_MEMORY_PLAN.md, second form: leave one body out with the episodic model (no weight update in the new body).
  LIFE         trained on five bodies' episodes; the sixth body's queries answered with k of its course experiences as examples
  LIFE-CIPHER  the same, every word of the sixth body replaced consistently (structure only)
  ALONE        the same model trained on the sixth body's own course episodes only (what the body alone can teach)
  EMPTY        the symbolic predictor from the sixth body's course only (today's core)
  python -m atanor_os.memory.lobo2 <out> [--bodies ...] [--seeds 1 2 3 4 5] [--ks 1 3 10] [--steps 3000] [--tau 0.0]
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


def run(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    log = open(out / 'log.txt', 'a', encoding='utf-8')

    def say(*x):
        print(*x, flush=True)
        log.write(' '.join(map(str, x)) + '\n')
        log.flush()
    data = {(b, s): load(b, s) for b in BODIES for s in a.seeds}     # every body is lived; --bodies says which are held out
    rows = []
    for held in a.bodies:
        others = [sc for (b, s), (_, tr, _) in data.items() if b != held for sc in tr]
        held_tr = [sc for (b, s), (_, tr, _) in data.items() if b == held for sc in tr]
        held_q = [q for (b, s), (_, _, qs) in data.items() if b == held for q in qs]
        ea = Counter()
        for s in a.seeds:
            c = pickle.loads(Path(f'{CACHE}/{held}-s{s}.pkl').read_bytes())
            ea.update(empty_mind(held, data[(held, s)][0], c['qs']))
        say(held, 'EMPTY', dict(ea))
        rows.append({'held': held, 'cond': 'EMPTY', 'k': None, **ea})
        torch.manual_seed(0)
        t0 = time.time()
        life = train(Episodic(), others, device, steps=a.steps, k=max(a.ks), seed=0, log=lambda s: say(held, 'LIFE', s))
        say(held, 'LIFE trained', len(others), 'scenes', f'{time.time() - t0:.0f}s')
        torch.manual_seed(0)
        alone = train(Episodic(), held_tr, device, steps=a.steps, k=max(a.ks), seed=0)
        say(held, 'ALONE trained', len(held_tr), 'scenes')
        rng = random.Random(f'{held}-cipher')
        both = cipher(held_tr + held_q, rng)
        held_tr_c, held_q_c = both[:len(held_tr)], both[len(held_tr):]
        for k in a.ks:
            for cond, model, shots, qs in (('LIFE', life, held_tr, held_q), ('LIFE-CIPHER', life, held_tr_c, held_q_c), ('ALONE', alone, held_tr, held_q)):
                r = score(model, shots, qs, device, k, random.Random(k), a.tau)
                say(held, cond, 'k', k, r)
                rows.append({'held': held, 'cond': cond, 'k': k, **r})
        (out / 'rows.json').write_text(json.dumps(rows), encoding='utf-8')
    for held in a.bodies:
        say('==', held)
        for r in rows:
            if r['held'] == held:
                n = sum(v for kk, v in r.items() if kk in ('right', 'wrong', 'unknown', 'never_seen'))
                say(f"  {r['cond']:12s} k={r['k']!s:5s} R {r.get('right', 0) / max(n, 1):.3f} W {r.get('wrong', 0) / max(n, 1):.3f} n={n}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--bodies', nargs='+', default=list(BODIES))
    ap.add_argument('--seeds', nargs='+', type=int, default=[1, 2, 3, 4, 5])
    ap.add_argument('--ks', nargs='+', type=int, default=[1, 3, 10])
    ap.add_argument('--steps', type=int, default=3000)
    ap.add_argument('--tau', type=float, default=0.0)
    a = ap.parse_args()
    if any(s > 5 for s in a.seeds):
        ap.error('development: seeds 1-5 only')
    run(a)
