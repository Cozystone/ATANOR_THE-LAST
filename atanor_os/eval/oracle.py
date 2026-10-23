"""Evaluator-only ground truth: the real tool semantics in symbolic form, plus a reachability check
and a semantics cross-check against the actual filesystem. Never imported by agent/ (test_leakage)."""
import random
import tempfile
from pathlib import Path

from ..agent.lift import apply_effects, frame_changes
from ..agent.planner import plan
from ..core.types import Goal
from ..world.fs_world import Workspace

TRUE_EFFECTS = {
    'mkdir':   [(0, 'kind', ('const', 'dir'))],
    'copy':    [(1, 'kind', ('const', 'file')), (1, 'hash', ('copy', 0))],
    'move':    [(0, 'kind', ('const', 'absent')), (0, 'hash', ('const', '-')),
                (1, 'kind', ('const', 'file')), (1, 'hash', ('copy', 0))],
    'delete':  [(0, 'kind', ('const', 'absent')), (0, 'hash', ('const', '-'))],
    'convert': [(1, 'kind', ('const', 'file')), (1, 'hash', ('unknown',))],
}


def true_pre(state, tool, args):
    o = [state.get(a) for a in args]
    if any(x is None for x in o):
        return False
    if tool == 'mkdir':
        return o[0]['kind'] == 'absent' and o[0]['parent_kind'] == 'dir'
    if tool in ('copy', 'move'):
        return o[0]['kind'] == 'file' and o[1]['kind'] == 'absent' and o[1]['parent_kind'] == 'dir'
    if tool == 'delete':
        return o[0]['kind'] == 'file'
    return (o[0]['kind'] == 'file' and o[0]['ext'] == 'txt' and o[1]['ext'] == 'md'
            and o[1]['kind'] == 'absent' and o[1]['parent_kind'] == 'dir')


class TrueModel:
    name = 'ORACLE'

    def predict(self, state, tool, args):
        if not true_pre(state, tool, args):
            return None, 'oracle_fail'
        return apply_effects(state, args, TRUE_EFFECTS[tool]), 'oracle'

    def update(self, exp):
        pass

    def describe(self):
        return {'condition': self.name}


def reachable(ws, goal, nodes=4000, depth=16, seconds=20.0):
    """Length of a plan found with the true model (an upper bound on the minimum), or None."""
    state = ws.observe(goal.universe)
    g = Goal(goal.id, goal.must, goal.keep, goal.capabilities,
             {'actions': 32, 'nodes': nodes, 'depth': depth, 'seconds': seconds}, goal.universe)
    p, _ = plan(state, g, TrueModel(), Workspace.actions(sorted(state)))
    return None if p is None else len(p)


def semantic_check(k=20, seed=7, root=None, max_blocks=400):
    """Real actions vs TrueModel predictions, stratified: at least k checks per (tool, predicted outcome) cell.

    Any mismatch, or an unfilled cell, fails the check (`ok` False). v2 after review: the old version
    sampled uniformly, re-used one seed and never guaranteed that each tool's success case was exercised.
    """
    from ..world.fs_world import TOOLS
    from .explore import POOL
    from .generator import layout, materialize
    rng = random.Random(seed)
    root = Path(root or tempfile.mkdtemp(prefix='atanor_sem_'))
    cells = {f'{t}:{o}': 0 for t in TOOLS for o in ('success', 'failure')}
    mism, checked, block = [], 0, 0
    while block < max_blocks and min(cells.values()) < k:
        files, ddir, dfile = layout(rng, 'train')
        ws = materialize(root / f'b{block}', files, ddir, dfile)
        for _ in range(25):
            if min(cells.values()) >= k:
                break
            pre = ws.observe(POOL)
            buckets = {}
            for tool, args in Workspace.actions(sorted(pre)):
                outcome = 'success' if true_pre(pre, tool, args) else 'failure'
                buckets.setdefault(f'{tool}:{outcome}', []).append((tool, args))
            needy = [c for c in buckets if cells[c] < k]
            if not needy:
                break
            cell = rng.choice(needy)
            tool, args = rng.choice(buckets[cell])
            predicted, _ = TrueModel().predict(pre, tool, args)
            res = ws.execute(tool, args, {'destroy': True})
            post = ws.observe(list(pre))
            checked += 1
            cells[cell] += 1
            ok_match = (predicted is not None) == res['ok']
            attr_match = (not res['ok']) or all(predicted[a][k_] in ('unknown', post[a][k_])
                                                for a in args for k_ in ('kind', 'ext', 'hash'))
            frame = frame_changes(pre, post, args)
            if not (ok_match and attr_match and not frame):
                mism.append({'tool': tool, 'args': args, 'real_ok': res['ok'], 'predicted_ok': predicted is not None,
                             'frame': frame})
        block += 1
    return {'ok': not mism and min(cells.values()) >= k, 'checked': checked, 'cells': cells, 'k': k, 'seed': seed,
            'n_mismatch': len(mism), 'mismatches': mism[:10]}
