"""V_TWO_SELVES_PLAN.md V2 (second form): two Selves in ONE world. A and B take turns in the same live world of a body;
between B's looks, hidden from B, either A acts with a tool (a random call of the body's menu) or the world moves by
itself (a tick: time passes), or both, in a random order. B looks again and, for every attribute it sees changed and did
not change itself, says OTHER or WORLD (whose_change's rule: only what its own life showed its tools and the world do).
The truth is on the hidden record, change by change. B also acts in its turn (its own changes are known to it).
  python -m atanor_os.memory.coexist <cache_dir> <out.json> --bodies ... --seeds ... [--rounds 60]
"""
import argparse
import json
import pickle
import random
import shutil
from collections import Counter
from pathlib import Path

from ..eval.tutor_life import DRIFT
from ..rebuild.explore import _calls
from ..repr.run_act6 import _install, worlds
from .whose_change import stream


def diff(s0, s1):
    """-> {(object, attr): (old, new)}"""
    out = {}
    for o, v in s1.items():
        old = s0.get(o)
        if isinstance(v, dict) and isinstance(old, dict):
            for k, w in v.items():
                if old.get(k) != w and k != 'kind':
                    out[(o, k)] = (str(old.get(k)), str(w))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cache')
    ap.add_argument('out')
    ap.add_argument('--bodies', nargs='+', required=True)
    ap.add_argument('--seeds', nargs='+', type=int, required=True)
    ap.add_argument('--rounds', type=int, default=60)
    ap.add_argument('--many', type=int, default=3)
    a = ap.parse_args()
    _install()
    tot, rows = Counter(), []
    for body in a.bodies:
        c = Counter()
        for seed in a.seeds:
            f = Path(a.cache) / f'{body}-s{seed}.pkl'
            if not f.exists():
                continue
            cc = pickle.loads(f.read_bytes())
            names = json.loads((Path(cc['course']) / body / 'names.json').read_text(encoding='utf-8'))
            tool, world = Counter(), Counter()
            for k, ch in stream(a.cache, body, seed):       # B's own life: what its tools did, what the world did
                (tool if k == 'act' else world).update(ch)
            nt, nw = sum(tool.values()) or 1, sum(world.values()) or 1
            root = Path(a.out).with_suffix('') / f'{body}-{seed}'
            shutil.rmtree(root, ignore_errors=True)
            h = worlds(body, root, seed + 500, [DRIFT[body]])[0]()     # a world of this body nobody has used
            caps = {x: True for x in set(getattr(h, 'CAPABILITY', {}).values())}
            rng = random.Random(f'coexist-{body}-{seed}')
            for _ in range(a.rounds):
                hidden = rng.choice([['A'], ['W'], ['A', 'W'], ['W', 'A']])
                start, cause = h.observe(h.existing()), {}
                for who in hidden:
                    s0 = h.observe(h.existing())
                    if who == 'W':
                        h.tick()
                    else:
                        calls = _calls(body, names, h)
                        if not calls:
                            continue
                        _, t, args = rng.choice(calls)
                        try:
                            h.execute(t, tuple(args), caps)
                        except Exception:
                            continue
                    for key in diff(s0, h.observe(h.existing())):
                        cause[key] = 'BOTH' if key in cause else ('WORLD' if who == 'W' else 'OTHER')
                seen = diff(start, h.observe(h.existing()))    # what B sees when it looks again: the whole interval at once
                many = Counter(k for (_, k) in seen)           # how many objects changed in the same attribute
                for (o, k), (old, new) in seen.items():
                    truth = cause.get((o, k))
                    if truth in (None, 'BOTH'):
                        continue
                    x = (k, old, new)
                    pt, pw = tool[x] / nt, world[x] / nw
                    said = 'unknown' if not pt and not pw else ('OTHER' if pt > pw else 'WORLD')
                    c[f'{truth}:n'] += 1
                    c[f'{truth}:MODEL'] += said == truth
                    c[f'{truth}:unknown'] += said == 'unknown'
                    c[f'{truth}:MANY'] += ('WORLD' if many[k] >= a.many else said) == truth   # one actor touches few objects; the world many
                calls = _calls(body, names, h)             # B's own turn
                if calls:
                    _, t, args = rng.choice(calls)
                    try:
                        h.execute(t, tuple(args), caps)
                    except Exception:
                        pass
            shutil.rmtree(root, ignore_errors=True)
        rows.append({'body': body, **c})
        tot.update(c)
        print(body, dict(c), flush=True)
    for t in ('OTHER', 'WORLD'):
        n = tot[f'{t}:n'] or 1
        print(f"ALL {t:5s} n {tot[f'{t}:n']:5d}  MODEL {tot[f'{t}:MODEL'] / n:.3f} (unknown {tot[f'{t}:unknown'] / n:.3f})  MANY {tot[f'{t}:MANY'] / n:.3f}")
    Path(a.out).write_text(json.dumps(rows), encoding='utf-8')


if __name__ == '__main__':
    main()
