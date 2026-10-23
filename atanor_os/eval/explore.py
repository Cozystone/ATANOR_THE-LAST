"""Fixed exploration policy (harness-owned; identical for every condition, BOOTSTRAP_MANIFEST §5).

Per step: pick a tool uniformly, then prefer an action whose lifted situation signature has been
tried fewer than REPEAT times (uniform among those), else uniform among the tool's actions. Train layouts only.
No goal, no solution path, destroy capability granted so delete semantics are observable too.
"""
import random
from pathlib import Path

from ..agent.lift import lifted_pre
from ..core.types import Experience
from ..world.fs_world import TOOLS, Workspace
from .generator import layout, materialize

POOL = ['new.txt', 'extra.csv', 'note.md', 'box', 'box/in.txt', 'box/out.md', 'box/sub', 'box/sub/deep.csv',
        'copy.txt', 'mirror.md', 'vault', 'vault/a.txt']
BLOCK = 40
REPEAT = 2


def explore(seed, steps, root):
    rng = random.Random(f'explore-{seed}')
    root = Path(root)
    exps, seen, tools = [], {}, sorted(TOOLS)
    for block in range((steps + BLOCK - 1) // BLOCK):
        files, ddir, dfile = layout(rng, 'train')
        ws = materialize(root / f'b{block}', files, ddir, dfile)
        targets = rng.sample(POOL, 5)
        for s in range(min(BLOCK, steps - block * BLOCK)):
            universe = ws.universe(targets)
            pre = ws.observe(targets)
            tool = rng.choice(tools)
            cands = [a for a in Workspace.actions(universe) if a[0] == tool]
            novel = [a for a in cands if seen.get((tool, lifted_pre(pre, a[1])), 0) < REPEAT]
            tool, args = rng.choice(novel or cands)
            key = (tool, lifted_pre(pre, args))
            seen[key] = seen.get(key, 0) + 1
            res = ws.execute(tool, args, {'destroy': True})
            post = ws.observe(list(pre))          # keep moved/deleted paths observable (as absent)
            exps.append(Experience(f'x{seed}-{block}-{s}', tool, tuple(args), pre, post, res['ok'], res['blocked'],
                                   res['ms'], False, f'explore-{seed}'))
    return exps
