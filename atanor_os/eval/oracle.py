"""Evaluator-only ground truth: the real tool semantics in symbolic form, plus a reachability check
and a semantics cross-check against the actual filesystem. Never imported by agent/ (test_leakage)."""
import random
import tempfile
from pathlib import Path

from ..agent.lift import apply_effects, effect_attrs, frame_changes
from ..agent.planner import plan
from ..core.types import Goal

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


def reachable(ws, goal, nodes=4000, depth=16, seconds=20.0, model=None):
    """Length of a plan found with the true model (an upper bound on the minimum), or None."""
    state = ws.observe(goal.universe)
    g = Goal(goal.id, goal.must, goal.keep, goal.capabilities,
             {'actions': 32, 'nodes': nodes, 'depth': depth, 'seconds': seconds}, goal.universe)
    p, _ = plan(state, g, model or TrueModel(), ws.actions(sorted(state)), capability=getattr(ws, 'CAPABILITY', {}))
    return None if p is None else len(p)


def fs_sem_block(rng, root):
    from .explore import POOL
    from .generator import layout, materialize
    files, ddir, dfile = layout(rng, 'train')
    return materialize(root, files, ddir, dfile), POOL


def semantic_check(k=20, seed=7, root=None, max_blocks=400, block=fs_sem_block, model=None, pre_fn=None):
    """Real actions vs the true model, stratified: at least k checks per (tool, predicted outcome) cell.

    Any mismatch, or an unfilled cell, fails the check (`ok` False). Body-generic: `block` makes a
    fresh workspace, `model` is the body's true model, `pre_fn(state, tool, args)` its precondition.
    """
    from .explore import ALL_CAPS
    model = model or TrueModel()
    pre_fn = pre_fn or true_pre
    rng = random.Random(seed)
    root = Path(root or tempfile.mkdtemp(prefix='atanor_sem_'))
    cells, mism, checked, block_i = None, [], 0, 0
    while block_i < max_blocks and (cells is None or min(cells.values()) < k):
        ws, targets = block(rng, root / f'b{block_i}')
        if cells is None:
            cells = {f'{t}:{o}': 0 for t in ws.TOOLS for o in ('success', 'failure')}
        for _ in range(25):
            if min(cells.values()) >= k:
                break
            pre = ws.observe(targets)
            buckets = {}
            for tool, args in ws.actions(sorted(pre)):
                outcome = 'success' if pre_fn(pre, tool, args) else 'failure'
                buckets.setdefault(f'{tool}:{outcome}', []).append((tool, args))
            needy = [c for c in buckets if cells[c] < k]
            if not needy:
                break
            cell = rng.choice(needy)
            tool, args = rng.choice(buckets[cell])
            predicted, _ = model.predict(pre, tool, args)
            res = ws.execute(tool, args, ALL_CAPS)
            post = ws.observe(list(pre))
            checked += 1
            cells[cell] += 1
            ok_match = (predicted is not None) == res['ok']
            attr_match = (not res['ok']) or all(predicted[a][k_] in ('unknown', post[a].get(k_))
                                                for a in args for k_ in effect_attrs(predicted[a]))
            frame = frame_changes(pre, post, args)
            if not (ok_match and attr_match and not frame):
                mism.append({'tool': tool, 'args': args, 'real_ok': res['ok'], 'predicted_ok': predicted is not None,
                             'frame': frame})
        block_i += 1
    cells = cells or {}
    return {'ok': not mism and bool(cells) and min(cells.values()) >= k, 'checked': checked, 'cells': cells,
            'k': k, 'seed': seed, 'n_mismatch': len(mism), 'mismatches': mism[:10]}


def rule_agreement(model, k=20, seed=11, root=None, max_blocks=400, block=fs_sem_block, pre_fn=None):
    """A condition's model against the body's real tools on fresh train-distribution situations, stratified like
    `semantic_check` (>= k per (tool, true outcome) cell) plus a best-effort NEAR cell per tool: failing actions
    that differ from a successful action of the same tool in the same state by exactly one argument (the
    precondition near-misses a learner over-generalizes on; type mismatches dominate the plain failure cell).
    Per tool: fp = predicted success where the real tool failed, fn = predicted failure where it succeeded,
    eff = real successes predicted as such whose predicted attributes differ from the real post-state,
    unk = real successes whose prediction left an attribute 'unknown', docs = answers resting on documentation
    alone, near_* = the same restricted to the near cell. Labels: `exact` (the pre-registered v1 criterion:
    cells filled and fp = fn = eff = 0 over the plain cells) and `strict` (exact, unk = 0, near cell filled
    with near_fp = 0). Evaluator-side; never consulted by the agent."""
    from .explore import ALL_CAPS
    pre_fn = pre_fn or true_pre
    rng = random.Random(seed)
    root = Path(root or tempfile.mkdtemp(prefix='atanor_agree_'))
    cells, near_cells, per_tool, block_i = None, {}, {}, 0
    while block_i < max_blocks and (cells is None or min(cells.values()) < k):
        ws, targets = block(rng, root / f'b{block_i}')
        if cells is None:
            cells = {f'{t}:{o}': 0 for t in ws.TOOLS for o in ('success', 'failure')}
            near_cells = {t: 0 for t in ws.TOOLS}
            per_tool = {t: {'checks': 0, 'fp': 0, 'fn': 0, 'eff': 0, 'unk': 0, 'docs': 0, 'near_checks': 0, 'near_fp': 0}
                        for t in ws.TOOLS}
        for _ in range(25):
            if min(cells.values()) >= k:
                break
            pre = ws.observe(targets)
            buckets, succ_args = {}, {}
            for tool, args in ws.actions(sorted(pre)):
                ok = pre_fn(pre, tool, args)
                buckets.setdefault(f"{tool}:{'success' if ok else 'failure'}", []).append((tool, args))
                if ok:
                    succ_args.setdefault(tool, []).append(args)
            for tool, sa in succ_args.items():                     # near-miss failures: one argument away from a success
                near = [(t, a) for t, a in buckets.get(f'{tool}:failure', [])
                        if any(sum(x != y for x, y in zip(a, s_)) == 1 for s_ in sa)]
                if near:
                    buckets[f'{tool}:near'] = near
            needy = [c for c in buckets if (near_cells if c.endswith(':near') else cells)[c.split(':')[0] if c.endswith(':near') else c] < k]
            if not needy:
                break
            needy_near = [c for c in needy if c.endswith(':near')]
            cell = rng.choice(needy_near or needy)                  # near cells first while they are available
            tool, args = rng.choice(buckets[cell])
            predicted, status = model.predict(pre, tool, args)
            res = ws.execute(tool, args, ALL_CAPS)
            post = ws.observe(list(pre))
            is_near = cell.endswith(':near')
            if is_near:
                near_cells[tool] += 1
                cells[f'{tool}:failure'] += 1                        # a near miss is also a plain failure sample
            else:
                cells[cell] += 1
            pt = per_tool[tool]
            pt['checks'] += 1
            pt['near_checks'] += int(is_near)
            pt['docs'] += int(str(status).endswith('documented'))
            if predicted is not None and not res['ok']:
                pt['fp'] += 1
                pt['near_fp'] += int(is_near)
            elif predicted is None and res['ok']:
                pt['fn'] += 1
            elif res['ok']:
                attrs = [(a, k_) for a in args for k_ in effect_attrs(predicted[a])]
                if any(predicted[a][k_] == 'unknown' for a, k_ in attrs):
                    pt['unk'] += 1
                if not all(predicted[a][k_] in ('unknown', post[a].get(k_)) for a, k_ in attrs):
                    pt['eff'] += 1
        block_i += 1
    filled = bool(cells) and min(cells.values()) >= k
    exact = sorted(t for t, v in per_tool.items() if filled and v['checks'] and v['fp'] == v['fn'] == v['eff'] == 0)
    strict = sorted(t for t in exact if per_tool[t]['unk'] == 0 and near_cells.get(t, 0) >= k and per_tool[t]['near_fp'] == 0)
    return {'k': k, 'seed': seed, 'cells': cells or {}, 'near_cells': near_cells, 'per_tool': per_tool,
            'exact_tools': exact, 'n_exact': len(exact), 'strict_tools': strict, 'n_strict': len(strict),
            'n_tools': len(per_tool), 'filled': filled}
