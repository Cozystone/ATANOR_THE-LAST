"""Fixed exploration policies (harness-owned; identical for every condition, BOOTSTRAP_MANIFEST §5).

Body-generic: `block(rng, root)` materializes a fresh workspace of the chosen body and returns
(workspace, extra target paths). No learner is consulted; only the explorer's own records are used.
"""
import random
from pathlib import Path

from ..agent.lift import lifted_pre
from ..agent.rule_learner import learn_operator
from ..core.types import Experience
from .generator import layout, materialize

POOL = ['new.txt', 'extra.csv', 'note.md', 'box', 'box/in.txt', 'box/out.md', 'box/sub', 'box/sub/deep.csv',
        'copy.txt', 'mirror.md', 'vault', 'vault/a.txt']
BLOCK = 40
REPEAT = 2
POLICIES = ('novelty', 'scarce', 'contrast', 'contrast-role', 'contrast-kind', 'contrast-target', 'contrast-pair')
ALL_CAPS = {'destroy': True, 'close_panels': True}


def fs_block(rng, root):
    files, ddir, dfile = layout(rng, 'train')
    return materialize(root, files, ddir, dfile), rng.sample(POOL, 5)


def _near(sig, successes):
    """True when `sig` differs from some successful signature of the same tool in exactly one literal."""
    return any(len(sig - s) == 1 for s in successes)


def _near_role(sig, successes):
    """True when all literals that differ from some successful signature belong to one argument role
    (e.g. the same panel with a different value object, or the same source with a different target)."""
    for s in successes:
        roles = {l[1][0] for l in (sig ^ s)}
        if len(roles) == 1:
            return True
    return False


def targets_of(op, sigs, novel):
    """H4 targeted contrasts: novel actions that the learner's current rule predicts to succeed (some type
    group's conjunction holds) while flipping one of that group's UNTESTED generalizations (a literal every
    success so far had, dropped without contrast). Success removes the literal from the generalization
    question; failure becomes the counterexample that keeps it. Fewest flipped literals first."""
    if op is None or not op.groups:
        return []
    best, out = None, []
    for a in novel:
        s = sigs[a]
        flips = min((sum(1 for d in g['open'] if d not in s) for g in op.groups
                     if g['open'] and g['pre'] <= s and any(d not in s for d in g['open'])), default=None)
        if flips is None:
            continue
        if best is None or flips < best:
            best, out = flips, [a]
        elif flips == best:
            out.append(a)
    return out


def _pairs(sig):
    ls = sorted(sig, key=repr)
    return [(a, b) for i, a in enumerate(ls) for b in ls[i + 1:]]


def explore(seed, steps, root, policy='novelty', block=fs_block, type_attrs=('kind',)):
    """'novelty' (v2): tool uniform; within a tool prefer signatures tried < REPEAT times.
    'scarce'  (H1a): tool drawn with probability ~ 1/(1+successes so far); within a tool as 'novelty'.
    'contrast' (H1b): like 'scarce', but within a tool prefer untried signatures that differ from one
    of that tool's SUCCESSFUL signatures in exactly one literal (the contrasts induction needs).
    'contrast-role' (P3): as 'contrast' with the difference confined to one argument role.
    'contrast-kind' (P3, H4): as 'contrast-role'; while a tool has no success yet (or no untried
    contrast), prefer the least-tried tuple of argument KINDS, so a rare tool's first success is
    searched over types (e.g. panel x grp) instead of over instances.
    'contrast-target' (H4): as 'contrast-kind', but first prefer `targets_of` — the only policy that reads
    the learner's current rules (relearned for the chosen tool from the explorer's own log; never the
    evaluator's truth). `type_attrs` is the body's type declaration, as given to the learner.
    'contrast-pair' (H4b): as 'contrast-target', but a tool WITHOUT a success yet is searched by pairwise
    literal coverage (prefer the novel action whose signature contains the most literal pairs this tool has
    never been tried with) instead of argument-kind novelty: a first success that needs a conjunction of
    several attribute values (convert: txt source, md absent target, existing parent) is reached sooner.
    """
    if policy not in POLICIES:
        raise ValueError(policy)
    rng = random.Random(f'explore-{seed}')
    root = Path(root)
    exps, seen, kind_seen, succ, succ_sigs, tools = [], {}, {}, {}, {}, None
    by_tool, ops, n_targeted, pairs_seen = {}, {}, 0, {}
    for b in range((steps + BLOCK - 1) // BLOCK):
        ws, targets = block(rng, root / f'b{b}')
        if tools is None:
            tools = sorted(ws.TOOLS)
            succ = {t: 0 for t in tools}
            succ_sigs = {t: set() for t in tools}
        for s in range(min(BLOCK, steps - b * BLOCK)):
            universe = ws.universe(targets)
            pre = ws.observe(targets)
            if policy in ('scarce', 'contrast', 'contrast-role', 'contrast-kind', 'contrast-target', 'contrast-pair'):
                tool = rng.choices(tools, weights=[1.0 / (1 + succ[t]) for t in tools])[0]
            else:
                tool = rng.choice(tools)
            cands = [a for a in ws.actions(universe) if a[0] == tool]
            sigs = {a: lifted_pre(pre, a[1]) for a in cands}
            novel = [a for a in cands if seen.get((tool, sigs[a]), 0) < REPEAT]
            pool = novel or cands
            targeted = False
            if policy in ('contrast', 'contrast-role', 'contrast-kind', 'contrast-target', 'contrast-pair') and novel:
                near_fn = _near if policy == 'contrast' else _near_role
                near = [a for a in novel if near_fn(sigs[a], succ_sigs[tool])]
                pool = near or novel
                tg = targets_of(ops.get(tool), sigs, novel) if policy in ('contrast-target', 'contrast-pair') else []
                if tg:
                    pool, targeted = tg, True
                elif policy == 'contrast-pair' and succ[tool] == 0:
                    ps = pairs_seen.setdefault(tool, set())
                    score = {a: sum(1 for pr in _pairs(sigs[a]) if pr not in ps) for a in novel}
                    top = max(score.values())
                    pool = [a for a in novel if score[a] == top]
                elif policy in ('contrast-kind', 'contrast-target', 'contrast-pair') and not near:
                    kinds = {a: tuple(pre[x]['kind'] if pre.get(x) else None for x in a[1]) for a in novel}
                    least = min(kind_seen.get((tool, kinds[a]), 0) for a in novel)
                    pool = [a for a in novel if kind_seen.get((tool, kinds[a]), 0) == least]
            tool, args = rng.choice(pool)
            key = (tool, sigs[(tool, args)])
            seen[key] = seen.get(key, 0) + 1
            kkey = (tool, tuple(pre[x]['kind'] if pre.get(x) else None for x in args))
            kind_seen[kkey] = kind_seen.get(kkey, 0) + 1
            res = ws.execute(tool, args, ALL_CAPS)
            succ[tool] += int(res['ok'])
            if res['ok']:
                succ_sigs[tool].add(sigs[(tool, args)])
            post = ws.observe(list(pre))          # keep moved/deleted paths observable (as absent)
            exps.append(Experience(f'x{seed}-{b}-{s}', tool, tuple(args), pre, post, res['ok'], res['blocked'],
                                   res['ms'], False, f'explore-{seed}'))
            n_targeted += int(targeted)
            if policy == 'contrast-pair':
                pairs_seen.setdefault(tool, set()).update(_pairs(sigs[(tool, args)]))
            if policy in ('contrast-target', 'contrast-pair'):
                by_tool.setdefault(tool, []).append(exps[-1])
                ops[tool] = learn_operator(tool, ws.TOOLS[tool], by_tool[tool], type_attrs)
    first = {}
    for i, e in enumerate(exps):
        if e.succeeded:
            first.setdefault(e.tool, i)
    explore.last_stats = {'targeted_steps': n_targeted, 'steps': len(exps), 'first_success': first}
    return exps
