"""H_LEARNED_MEMORY_PLAN.md, the diversity the five bodies cannot give: a family of generated worlds to learn HOW TO READ
EXAMPLES from. Nothing here is a real body's rule: every world draws its attributes, words, tools and effects at random
from a small grammar of what an action can do to an argument's attribute (keep, set a word, copy another argument's
attribute, blank, step a digit, send each value to a value of its own) under optional preconditions (one or two
attributes must or must not hold a value, else the body answers 'failed' and nothing changes). A model trained on thousands of these can only succeed by reading the examples in
front of it, and is then met with the six real bodies as worlds it has never seen.
"""
import random

from .relational import BLANK, Scene

CONS = 'bcdfghjklmnprstvz'
VOW = 'aeiou'


def word(rng, n=2):
    return ''.join(rng.choice(CONS) + rng.choice(VOW) for _ in range(n))


class World:
    def __init__(self, seed, rich=True, kinds=False):
        self.rich, self.kinds = rich, kinds
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
        self.kind_attr, self.kind_of = None, {}
        if kinds and len(self.attrs) >= 4:
            self.kind_attr = self.attrs[0]
            self.digit[self.kind_attr] = False
            ks = []
            while len(ks) < rng.randint(2, 3):
                w = word(rng)
                if w not in ks:
                    ks.append(w)
            self.vocab[self.kind_attr] = ks
            self.blankable[self.kind_attr] = False
            rest = self.attrs[1:]
            for kd in ks:                                   # the attributes a kind has; the others are '-' for it
                self.kind_of[kd] = [a for a in rest if rng.random() < 0.7] or [rest[0]]
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
            kind = rng.choices(['set', 'copy_same', 'copy_other', 'blank', 'step', 'map'],
                               [4, 3 if nargs == 2 else 0, 2 if nargs == 2 else 0, 2, 3 if self.digit[a] else 0, 3 if self.rich else 0])[0]
            if kind == 'set':
                ops[(i, a)] = ('set', rng.choice(self.vocab[a]))
            elif kind == 'copy_same':
                ops[(i, a)] = ('copy', 1 - i, a)
            elif kind == 'copy_other':
                ops[(i, a)] = ('copy', 1 - i, rng.choice(self.attrs))
            elif kind == 'blank':
                ops[(i, a)] = ('blank',)
            elif kind == 'map':                            # each value goes to a value of its own (a scale, a cycle, a table)
                voc = sorted(set(self.vocab[a]))
                to = voc[:]
                rng.shuffle(to)
                ops[(i, a)] = ('map', dict(zip(voc, to)))
            else:
                ops[(i, a)] = ('step', rng.choice((-1, 1)))
        pre = None
        if rng.random() < (0.65 if self.rich else 0.5):
            pre = []
            for _ in range(2 if self.rich and rng.random() < 0.3 else 1):
                i = rng.randrange(nargs)
                a = rng.choice(self.attrs)
                pre.append((i, a, rng.choice(self.vocab[a] + [BLANK]), rng.random() < 0.5))   # (arg, attr, value, must_equal)
        if self.kind_attr and rng.random() < 0.5:           # this tool is for one kind of object
            pre = (pre or []) + [(rng.randrange(nargs), self.kind_attr, rng.choice(self.vocab[self.kind_attr]), True)]
        alt = {}
        if self.kind_attr and rng.random() < 0.4:           # for another kind, one effect is different
            (i, a), op = rng.choice(sorted(ops.items(), key=str))
            kd = rng.choice(self.vocab[self.kind_attr])
            alt[(i, a)] = (kd, ('blank',) if op[0] != 'blank' else ('set', rng.choice(self.vocab[a])))
        return {'nargs': nargs, 'ops': ops, 'pre': pre, 'alt': alt}

    def state(self, rng):
        st = {a: (BLANK if self.blankable[a] and rng.random() < 0.3 else rng.choice(self.vocab[a])) for a in self.attrs}
        if self.kind_attr:
            kd = st[self.kind_attr]
            for a in self.attrs[1:]:
                if a not in self.kind_of[kd]:
                    st[a] = BLANK
        return st

    def apply(self, tool, before):
        p = self.tools[tool]
        after = [dict(o) for o in before]
        for i, a, v, eq in p['pre'] or ():
            if (before[i][a] == v) != eq:
                return after, False
        for (i, a), op in p['ops'].items():
            kd_alt = p.get('alt', {}).get((i, a))
            if kd_alt and before[i].get(self.kind_attr) == kd_alt[0]:
                op = kd_alt[1]
            if op[0] == 'set':
                after[i][a] = op[1]
            elif op[0] == 'copy':
                after[i][a] = before[op[1]][op[2]]
            elif op[0] == 'blank':
                after[i][a] = BLANK
            elif op[0] == 'map':
                after[i][a] = op[1].get(before[i][a], before[i][a])
            elif op[0] == 'step':
                v = before[i][a]
                after[i][a] = str(min(9, max(0, int(v) + op[1]))) if v.isdigit() else v
        return after, True

    def scenes(self, tool, n, rng, teacher=False):
        out = []
        p = self.tools[tool]
        for _ in range(n):
            args = [f'o{rng.randrange(1000)}' for _ in range(p['nargs'])]
            if len(set(args)) < len(args):
                continue
            for _try in range(8 if teacher else 1):           # a teacher mostly shows uses that work
                before = [self.state(rng) for _ in args]
                after, ok = self.apply(tool, before)
                if ok or rng.random() < 0.1:
                    break
            out.append(Scene(self.name, tool, args, dict(zip(args, before)), dict(zip(args, after)), 'ok' if ok else 'failed'))
        return out


def generate(n_worlds, per_tool, seed=0, rich=True, kinds=False):
    """-> list of scenes over n_worlds worlds."""
    rng = random.Random(f'gen-{seed}')
    out = []
    for w in range(n_worlds):
        world = World(seed * 1000003 + w, rich, kinds and w % 2 == 0)   # half the worlds have kinds
        for tool in world.tools:
            out += world.scenes(tool, per_tool, rng)
    return out
