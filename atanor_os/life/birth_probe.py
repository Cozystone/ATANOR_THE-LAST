"""Representation birth, first probe (dev seeds only; not a result). The bench's observations are shown to the mind only
as text, in a format it is not told; it knows what it typed (the action's arguments) and what the body answered, and
builds its own attributes from the text. The renderers are evaluator side: the perception below never reads a format's
name, a field name, or anything written for a body.
  ADAPTER  the given fields (today's system), scored on them
  POS      attribute = ordinal position of a token in the line that names the argument
  BAG      attribute = 'this token is here' (0/1 of every token seen), nothing else
  BIRTH    attribute = a class of tokens that replaced each other under the mind's own actions; a token that never was
           replaced joins the first class of such tokens it never occurs together with (mutual exclusivity)
Scored on the text: a prediction is right if the set of tokens it says the argument's line will hold is the set it holds.
  python -m atanor_os.life.birth_probe <out_dir> [body ...]
"""
import difflib
import glob
import importlib.util
import json
import os
import pickle
import random
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from ..rebuild.bench_predict import judge
from ..rebuild.effects import Effects
from ..rebuild.experience import load_course

CACHE = os.environ.get('BIRTH_CACHE', 'D:/ATANOR-experiments/probe-work/stage1-dev/cache')
PUNCT = r'''\s=:;,|@"'(){}\[\]<>'''                # what separates words, for any text
FORMATS = ('TABLE', 'KV', 'KVS', 'PROSE')
METHODS = tuple(os.environ.get('BIRTH_METHODS', 'POS,BIRTH').split(','))                                 # BAG is far slower (368 s for one world) and answered nothing there


# ---- evaluator side: how a body happens to print ----
def line(fmt, name, obs, rng):
    items = sorted(obs.items())
    if fmt == 'TABLE':
        return ' | '.join([name] + [str(v) for _, v in items])
    if fmt == 'KV':
        return name + ' ' + ' '.join(f'{k}={v}' for k, v in items)
    items = [(k, v) for k, v in items if v not in ('-', None)]
    rng.shuffle(items)
    if fmt == 'KVS':
        return ' '.join(f'{k}:{v}' for k, v in items) + f' @ {name}'
    return f'{name} shows ' + ', '.join(f'{v} for {k}' if i % 2 else f'{k} of {v}' for i, (k, v) in enumerate(items))


if os.environ.get('BIRTH_FORMATS_FILE'):                  # a held-out renderer, written elsewhere
    _spec = importlib.util.spec_from_file_location('held_out_formats', os.environ['BIRTH_FORMATS_FILE'])
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    FORMATS, line = tuple(_mod.FORMATS), _mod.line


def screen(fmt, world, rng):
    ls = [line(fmt, n, o, rng) for n, o in world.items() if o is not None]
    rng.shuffle(ls)
    return '\n'.join(ls)


# ---- the mind's side: text in, attributes out ----
def tokens(text, name):
    """The line that holds what the mind typed, without it. None if no line does."""
    pat = r'(?<![^' + PUNCT + r'])' + re.escape(name) + r'(?![^' + PUNCT + r'])'
    for l in text.split(chr(10)):
        if re.search(pat, l):
            return re.findall(r'[^' + PUNCT + r']+', re.sub(pat, ' ', l, count=1))
    return None


class Mind:
    def __init__(self, method):
        self.method, self.cls, self.filler, self.drop, self.ctx = method, {}, set(), set(), defaultdict(Counter)
        self.vocab = set()

    def fit(self, pairs):
        """pairs: (tokens before, tokens after) for each argument of each of the mind's acts, in order."""
        if self.method != 'BIRTH':
            self.vocab = {t for p in pairs for s in p if s for t in s}
            return
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        segs = [s for p in pairs for s in p if s]
        self.filler = {t for s in segs for t, n in Counter(s).items() if n > 1}          # never one value among others
        seen_with, freq = defaultdict(set), Counter()
        for s in segs:
            u = [t for t in set(s) if t not in self.filler]
            freq.update(u)
            for t in u:
                seen_with[t].update(x for x in u if x != t)
        self.drop = {t for t, n in freq.items() if n == len(segs)}
        for b, a in pairs:                                                               # replaced under an action
            if not b or not a:
                continue
            for op, i, j, k, l in difflib.SequenceMatcher(a=b, b=a, autojunk=False).get_opcodes():
                if op == 'replace' and j - i == 1 and l - k == 1 and b[i] not in self.filler and a[k] not in self.filler \
                        and a[k] not in seen_with[b[i]]:
                    parent[find(b[i])] = find(a[k])
        groups = defaultdict(set)
        for t in list(parent):
            groups[find(t)].add(t)
        classes = sorted(groups.values(), key=lambda g: (-len(g), sorted(g)))
        still = []
        for t in sorted((t for t in freq if t not in parent and t not in self.drop), key=lambda t: (-freq[t], t)):
            for c in still:                                                              # what changed stays pure
                if not any(x in seen_with[t] for x in c):
                    c.add(t)
                    break
            else:
                still.append({t})
                classes.append(still[-1])
        self.cls = {t: f'c{i}' for i, c in enumerate(classes) for t in c}
        for s in segs:
            for i, t in enumerate(s):
                c = self.cls.get(t)
                if c:
                    self.ctx[c]['p%d' % i] += 1
                    if i:
                        self.ctx[c]['<' + s[i - 1]] += 1
                    if i + 1 < len(s):
                        self.ctx[c]['>' + s[i + 1]] += 1

    def perceive(self, s):
        if s is None:
            return None
        if self.method == 'POS':
            return {f'p{i}': t for i, t in enumerate(s)}
        if self.method == 'BAG':
            o = {f'h{t}': 1 for t in set(s) if t in self.vocab}
            o.update({f'u{i}': t for i, t in enumerate(sorted(t for t in set(s) if t not in self.vocab))})
            return o
        o, unknown = {}, []
        for i, t in enumerate(s):
            if t in self.filler or t in self.drop:
                continue
            if t in self.cls:
                o[self.cls[t]] = t
            else:
                unknown.append(i)
        for n, i in enumerate(unknown):                                                  # a new word: where would it fit
            cue = [f'p{i}'] + ([f'<{s[i - 1]}'] if i else []) + ([f'>{s[i + 1]}'] if i + 1 < len(s) else [])
            free = {c: sum(self.ctx[c][k] / (1 + sum(self.ctx[c].values())) for k in cue) for c in self.ctx if c not in o}
            best = max(sorted(free), key=free.get) if free else None
            o[best if best and free[best] > 0 else f'u{n}'] = s[i]
        for c in set(self.cls.values()):                                                 # this class has nothing here
            o.setdefault(c, '-')
        return o

    def said(self, y, i):
        """What the mind says the argument's line will hold."""
        out = set()
        for k, v in y.items():
            if k == ('r',) or k[0] != i or v == '-':
                continue
            if self.method == 'BAG' and k[1].startswith('h'):
                if v == 1:
                    out.add(k[1][1:])
            else:
                out.add(v)
        return out

    def held(self, s):
        if s is None:
            return set()
        return {t for t in s if t != '-' and (self.method != 'BIRTH' or (t not in self.filler and t not in self.drop))}


def run(c, fmt, method):
    exps = [e for e in load_course(c['course'], c['body']) if e.get('action') and e.get('before') is not None and e.get('after') is not None]
    rng = random.Random(f'{c["body"]}{c["eval_seed"]}{fmt}')
    seen = []
    for e in exps:
        tb, ta = screen(fmt, e['before'], rng), screen(fmt, e['after'], rng)
        args = e['action']['args']
        seen.append((e, {a: tokens(tb, a) for a in args}, {a: tokens(ta, a) for a in args}))
    mind = Mind(method)
    mind.fit([(b[a], af[a]) for _, b, af in seen for a in b])
    eff = Effects(slack=1, tiered=True)
    for e, b, af in seen:
        eff.observe({**e, 'before': {a: mind.perceive(t) for a, t in b.items()}, 'after': {a: mind.perceive(t) for a, t in af.items()}})
    tally = Counter()
    for w, tool, args, before, truth, after in c['qs']:
        tb, ta = screen(fmt, dict(zip(args, before)), rng), screen(fmt, dict(zip(args, after)), rng)
        sb, sa = [tokens(tb, a) for a in args], [tokens(ta, a) for a in args]
        m = eff.model(tool, args)
        if m is None or not m.cases:
            continue
        p = eff.predict(tool, args, [mind.perceive(t) for t in sb], reader='BAYES0.99')['outcome']
        if p is None:
            tally['unknown'] += 1
        elif p.get(('r',)) == truth[('r',)] and all(mind.said(p, i) == mind.held(sa[i]) for i in range(len(args))):
            tally['right'] += 1
        else:
            tally['wrong'] += 1
    return dict(tally), sorted(set(mind.cls.values()), key=str) if method == 'BIRTH' else None


def adapter(c):
    eff = Effects(slack=1, tiered=True)
    for e in load_course(c['course'], c['body']):
        eff.observe(e)
    tally = Counter()
    for w, tool, args, before, truth, after in c['qs']:
        m = eff.model(tool, args)
        if m is None or not m.cases:
            continue
        tally[judge(eff.predict(tool, args, before, reader='BAYES0.99')['outcome'], truth)] += 1
    return dict(tally)


def one(job):
    f, fmt, method = job
    c = pickle.loads(Path(f).read_bytes())
    r = adapter(c) if method == 'ADAPTER' else run(c, fmt, method)[0]
    return c['body'], Path(f).stem, fmt, method, r


if __name__ == '__main__':
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    bodies = sys.argv[2:] or ['board', 'clime', 'desk', 'dye', 'fs', 'view']
    files = [f for b in bodies for f in sorted(glob.glob(f'{CACHE}/{b}-s*.pkl'))]
    jobs = [(f, '-', 'ADAPTER') for f in files] + [(f, fmt, m) for f in files for fmt in FORMATS for m in METHODS]
    rows = []
    with ProcessPoolExecutor(8) as ex:
        for r in ex.map(one, jobs):
            rows.append(r)
            print(*r, flush=True)
    (out / 'rows.json').write_text(json.dumps(rows))
    sumd = defaultdict(Counter)
    for b, _, fmt, m, t in rows:
        sumd[(b, fmt, m)].update(t)
    for k in sorted(sumd):
        n = sum(sumd[k].values())
        print(*k, f"R {sumd[k]['right'] / n:.3f} W {sumd[k]['wrong']}/{n}")
