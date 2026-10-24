"""Fixed exploration policies (harness-owned; identical for every condition, BOOTSTRAP_MANIFEST §5).

Body-generic: `block(rng, root)` materializes a fresh workspace of the chosen body and returns
(workspace, extra target paths). No learner is consulted; only the explorer's own records are used.
"""
import random
from pathlib import Path

from ..agent.lift import lifted_pre
from ..core.types import Experience
from .generator import layout, materialize

POOL = ['new.txt', 'extra.csv', 'note.md', 'box', 'box/in.txt', 'box/out.md', 'box/sub', 'box/sub/deep.csv',
        'copy.txt', 'mirror.md', 'vault', 'vault/a.txt']
BLOCK = 40
REPEAT = 2
POLICIES = ('novelty', 'scarce', 'contrast', 'contrast-role', 'contrast-kind')
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


def explore(seed, steps, root, policy='novelty', block=fs_block):
    """'novelty' (v2): tool uniform; within a tool prefer signatures tried < REPEAT times.
    'scarce'  (H1a): tool drawn with probability ~ 1/(1+successes so far); within a tool as 'novelty'.
    'contrast' (H1b): like 'scarce', but within a tool prefer untried signatures that differ from one
    of that tool's SUCCESSFUL signatures in exactly one literal (the contrasts induction needs).
    'contrast-role' (P3): as 'contrast' with the difference confined to one argument role.
    'contrast-kind' (P3, H4): as 'contrast-role'; while a tool has no success yet (or no untried
    contrast), prefer the least-tried tuple of argument KINDS, so a rare tool's first success is
    searched over types (e.g. panel x grp) instead of over instances.
    """
    if policy not in POLICIES:
        raise ValueError(policy)
    rng = random.Random(f'explore-{seed}')
    root = Path(root)
    exps, seen, kind_seen, succ, succ_sigs, tools = [], {}, {}, {}, {}, None
    for b in range((steps + BLOCK - 1) // BLOCK):
        ws, targets = block(rng, root / f'b{b}')
        if tools is None:
            tools = sorted(ws.TOOLS)
            succ = {t: 0 for t in tools}
            succ_sigs = {t: set() for t in tools}
        for s in range(min(BLOCK, steps - b * BLOCK)):
            universe = ws.universe(targets)
            pre = ws.observe(targets)
            if policy in ('scarce', 'contrast', 'contrast-role', 'contrast-kind'):
                tool = rng.choices(tools, weights=[1.0 / (1 + succ[t]) for t in tools])[0]
            else:
                tool = rng.choice(tools)
            cands = [a for a in ws.actions(universe) if a[0] == tool]
            sigs = {a: lifted_pre(pre, a[1]) for a in cands}
            novel = [a for a in cands if seen.get((tool, sigs[a]), 0) < REPEAT]
            pool = novel or cands
            if policy in ('contrast', 'contrast-role', 'contrast-kind') and novel:
                near_fn = _near if policy == 'contrast' else _near_role
                near = [a for a in novel if near_fn(sigs[a], succ_sigs[tool])]
                pool = near or novel
                if policy == 'contrast-kind' and not near:
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
    return exps
