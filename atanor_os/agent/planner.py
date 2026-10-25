"""Budgeted best-first search over a model's predictions (provided machinery, identical for every condition).

f = g + h; h = unsatisfied goal literals; a step predicted from documentation alone costs +0.5.
Predicted failures and states violating a `keep` literal are pruned. Tools without the required
capability are never planned. `avoid` lists root actions that already failed in this exact state.

The binding budget is `predictions` (model calls, deterministic). `nodes` caps expansions and
`seconds` is a safety guard; whichever stops the search is reported in stats['stop']
('found' | 'exhausted' | 'predictions' | 'nodes' | 'seconds').
"""
import heapq
import itertools
import time

from ..world.fs_world import CAPABILITY as FS_CAPABILITY
from .lift import DERIVED_ATTRS


def canon(state):
    """Canonical state key over non-derived attributes (body-generic)."""
    return tuple(sorted((p, tuple(sorted((k, v) for k, v in o.items() if k not in DERIVED_ATTRS)))
                        for p, o in state.items()))


def unsatisfied(state, goal):
    return sum(not l.holds(state) for l in goal.must)


def plan(state, goal, model, actions, avoid=frozenset(), capability=FS_CAPABILITY):
    b = goal.budget
    cap = b.get('predictions', 10 ** 9)
    t0 = time.perf_counter()
    stats = {'expanded': 0, 'predicted': 0, 'seconds': 0.0, 'stop': None, 'depth_hits': 0}
    if unsatisfied(state, goal) == 0 and all(l.holds(state) for l in goal.keep):
        stats['stop'] = 'found'
        return [], stats
    tick = itertools.count()
    heap = [(unsatisfied(state, goal), 0.0, 0, next(tick), state, [])]
    seen = {canon(state)}
    while heap and stats['stop'] is None:
        if stats['expanded'] >= b['nodes']:
            stats['stop'] = 'nodes'
            break
        if time.perf_counter() - t0 > b['seconds']:
            stats['stop'] = 'seconds'
            break
        _, g, depth, _, s, path = heapq.heappop(heap)
        stats['expanded'] += 1
        if depth >= b['depth']:
            stats['depth_hits'] += 1                 # a path was cut by the depth limit: exhaustion is then not proof
            continue
        for tool, args in actions:
            if stats['predicted'] >= cap:
                stats['stop'] = 'predictions'
                break
            steps = args if tool == 'macro' else ((tool, args),)
            if any(capability.get(t) and not goal.capabilities.get(capability[t]) for t, _ in steps):
                continue
            if not path and steps[0] in avoid:
                continue
            post, cost = s, 0.0
            for t, a in steps:                       # a macro is predicted step by step, keep checked on the way
                post, status = model.predict(post, t, a)
                stats['predicted'] += 1
                if post is None or any(not l.holds(post) for l in goal.keep):
                    post = None
                    break
                cost += 1 + (0.5 if status.endswith('documented') else 0.0)
            if post is None:
                continue
            key = canon(post)
            if key in seen:
                continue
            seen.add(key)
            g2 = g + cost
            h = unsatisfied(post, goal)
            p2 = path + [(tool, args)]
            if h == 0:
                stats['stop'] = 'found'
                stats['seconds'] = time.perf_counter() - t0
                return p2, stats
            heapq.heappush(heap, (g2 + h, g2, depth + 1, next(tick), post, p2))
    if stats['stop'] is None:
        stats['stop'] = 'exhausted'
    stats['seconds'] = time.perf_counter() - t0
    return None, stats
