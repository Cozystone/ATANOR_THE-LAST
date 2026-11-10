"""V_TWO_SELVES_PLAN.md V2 (first form): whose change is this? B sees a change it did not make (an object's attribute
went from v to w) and says OTHER (someone acted with a tool) or WORLD (it happened by itself: time, inflow, use).
B's knowledge is its own life only: what its tools did (its course's actions) and what the world did by itself while
it watched (the first half of its course's outside events). Test items, with the truth on record:
  WORLD: the outside events of the second half of B's course;  OTHER: the effects of another Self's actions (A's course).
Rules: MODEL: the larger of (share of B's known tool effects with this change) and (share of B's known world changes
with it); neither known -> 'unknown'. CORE: today's core, every unexplained change is 'outside' (WORLD).
  python -m atanor_os.memory.whose_change <cache_dir> <out.json> --bodies ... --seeds ...   (A is seed + 1)
"""
import argparse
import json
import pickle
from collections import Counter
from pathlib import Path

from ..rebuild.experience import load_course


def stream(cache, body, seed):
    """-> [(kind, [(attr, old, new)])] in course order: 'act' for an action that worked, 'world' for an outside event."""
    c = pickle.loads((Path(cache) / f'{body}-s{seed}.pkl').read_bytes())
    state, out = {}, []
    for e in load_course(c['course'], body):
        before, after = e.get('before') or {}, e.get('after') or {}
        for o, v in before.items():
            if isinstance(v, dict):
                state[o] = dict(v)
        ch = []
        for o, v in after.items():
            if not isinstance(v, dict):
                continue
            old = state.get(o)
            if old is not None:
                ch += [(k, str(old.get(k)), str(w)) for k, w in v.items() if old.get(k) != w and k != 'kind']
            state[o] = dict(v)
        if not ch:
            continue
        if e.get('action'):
            if (e.get('response') or {}).get('ok'):
                out.append(('act', ch))
        elif e.get('external') or e.get('actor') == 'outside':
            out.append(('world', ch))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cache')
    ap.add_argument('out')
    ap.add_argument('--bodies', nargs='+', required=True)
    ap.add_argument('--seeds', nargs='+', type=int, required=True)
    a = ap.parse_args()
    tot, rows = Counter(), []
    for body in a.bodies:
        c = Counter()
        for seed in a.seeds:
            if not all((Path(a.cache) / f'{body}-s{s}.pkl').exists() for s in (seed, seed + 1)):
                continue
            mine, theirs = stream(a.cache, body, seed), stream(a.cache, body, seed + 1)
            worlds = [ch for k, ch in mine if k == 'world']
            half = len(worlds) // 2
            tool, world = Counter(), Counter()
            for k, ch in mine:
                if k == 'act':
                    tool.update(ch)
            for ch in worlds[:half]:
                world.update(ch)
            nt, nw = sum(tool.values()) or 1, sum(world.values()) or 1
            items = [('WORLD', x) for ch in worlds[half:] for x in ch] + [('OTHER', x) for k, ch in theirs if k == 'act' for x in ch]
            for truth, x in items:
                pt, pw = tool[x] / nt, world[x] / nw
                said = 'unknown' if not pt and not pw else ('OTHER' if pt > pw else 'WORLD')
                c[f'{truth}:n'] += 1
                c[f'{truth}:MODEL'] += said == truth
                c[f'{truth}:unknown'] += said == 'unknown'
                c[f'{truth}:CORE'] += truth == 'WORLD'
        rows.append({'body': body, **c})
        tot.update(c)
        print(body, dict(c), flush=True)
    for t in ('OTHER', 'WORLD'):
        n = tot[f'{t}:n'] or 1
        print(f"ALL {t:5s} n {tot[f'{t}:n']:5d}  MODEL {tot[f'{t}:MODEL'] / n:.3f} (unknown {tot[f'{t}:unknown'] / n:.3f})  CORE {tot[f'{t}:CORE'] / n:.3f}")
    Path(a.out).write_text(json.dumps(rows), encoding='utf-8')


if __name__ == '__main__':
    main()
