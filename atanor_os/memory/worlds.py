"""H_LEARNED_MEMORY_PLAN.md, the diversity the five bodies cannot give: a family of generated worlds to learn HOW TO READ
EXAMPLES from. Nothing here is a real body's rule: every world draws its attributes, words, tools and effects at random
from a small grammar of what an action can do to an argument's attribute (keep, set a word, copy another argument's
attribute, blank, step a digit) under an optional precondition (an attribute must or must not hold a value, else the body
answers 'failed' and nothing changes). A model trained on thousands of these can only succeed by reading the examples in
front of it, and is then met with the six real bodies as worlds it has never seen.
"""
import random

from .relational import BLANK, Scene

CONS = 'bcdfghjklmnprstvz'
VOW = 'aeiou'


def word(rng, n=2):
    return ''.join(rng.choice(CONS) + rng.choice(VOW) for _ in range(n))


class World:
    def __init__(self, seed):
        rng = self.rng = random.Random(seed)
        self.name = f'w{seed}'
        n_attr = rng.randint(3, 6)
        self.attrs = []
        while len(self.attrs) < n_attr:
            w = word(rng)
            if w not in self.attrs:
                self.attrs.append(w)
        self.digit = {a: rng.random() < 0.25 for a in self.attrs}
        self.vocab = {a: ([str(i) for i in range(10)] if self.digit[a] else [word(rng, rng.randint(1, 3)) for _ in range(rng.randint(2, 6))])
                      for a in self.attrs}
        self.blankable = {a: rng.random() < 0.4 for a in self.attrs}
        self.tools = {}
        for _ in range(rng.randint(2, 5)):
            self.tools[word(rng, 2)] = self._program(rng)

    def _program(self, rng):
        nargs = 1 if rng.random() < 0.55 else 2
        ops = {}
        n_eff = rng.randint(1, 3)
        for _ in range(n_eff):
            i = rng.randrange(nargs)
            a = rng.choice(self.attrs)
            kind = rng.choices(['set', 'copy_same', 'copy_other', 'blank', 'step'], [4, 3 if nargs == 2 else 0, 2 if nargs == 2 else 0, 2, 3 if self.digit[a] else 0])[0]
            if kind == 'set':
                ops[(i, a)] = ('set', rng.choice(self.vocab[a]))
            elif kind == 'copy_same':
                ops[(i, a)] = ('copy', 1 - i, a)
            elif kind == 'copy_other':
                ops[(i, a)] = ('copy', 1 - i, rng.choice(self.attrs))
            elif kind == 'blank':
                ops[(i, a)] = ('blank',)
            else:
                ops[(i, a)] = ('step', rng.choice((-1, 1)))
        pre = None
        if rng.random() < 0.5:
            i = rng.randrange(nargs)
            a = rng.choice(self.attrs)
            pre = (i, a, rng.choice(self.vocab[a] + [BLANK]), rng.random() < 0.5)      # (arg, attr, value, must_equal)
        return {'nargs': nargs, 'ops': ops, 'pre': pre}

    def state(self, rng):
        return {a: (BLANK if self.blankable[a] and rng.random() < 0.3 else rng.choice(self.vocab[a])) for a in self.attrs}

    def apply(self, tool, before):
        p = self.tools[tool]
        after = [dict(o) for o in before]
        if p['pre'] is not None:
            i, a, v, eq = p['pre']
            if (before[i][a] == v) != eq:
                return after, False
        for (i, a), op in p['ops'].items():
            if op[0] == 'set':
                after[i][a] = op[1]
            elif op[0] == 'copy':
                after[i][a] = before[op[1]][op[2]]
            elif op[0] == 'blank':
                after[i][a] = BLANK
            elif op[0] == 'step':
                v = before[i][a]
                after[i][a] = str(min(9, max(0, int(v) + op[1]))) if v.isdigit() else v
        return after, True

    def scenes(self, tool, n, rng):
        out = []
        p = self.tools[tool]
        for _ in range(n):
            args = [f'o{rng.randrange(1000)}' for _ in range(p['nargs'])]
            if len(set(args)) < len(args):
                continue
            before = [self.state(rng) for _ in args]
            after, ok = self.apply(tool, before)
            out.append(Scene(self.name, tool, args, dict(zip(args, before)), dict(zip(args, after)), 'ok' if ok else 'failed'))
        return out


def generate(n_worlds, per_tool, seed=0):
    """-> list of scenes over n_worlds worlds."""
    rng = random.Random(f'gen-{seed}')
    out = []
    for w in range(n_worlds):
        world = World(seed * 1000003 + w)
        for tool in world.tools:
            out += world.scenes(tool, per_tool, rng)
    return out
