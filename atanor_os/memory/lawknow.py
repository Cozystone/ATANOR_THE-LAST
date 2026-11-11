"""CONTINUOUS_LIFE_PLAN.md: the law memory as an organ of the one mind in a life (the same place the reader has, know.py).
Everything is the Self's own lived experience in its store: experiences of the other tools, in this body and in the bodies
it lived before, give the law memory and the refusal conditions (LAW_MEMORY_PLAN.md, GUARD_PLAN.md); the experiences of
this tool are the shots. It answers only when what it would have expected of this tool's own last experiences, leaving
each out in turn, mostly came true (as live.trusted). No word, rule or answer of any body is in here.
Chosen with ATANOR_KNOW_KIND=law where the reader would be used (practice skip; learner next_know).
"""
import json
from collections import defaultdict

from .guards import Tool
from .lawlib import feats, library
from .live import Knows, came_true, trusted


def _val(v):
    return v if isinstance(v, (int, str)) and not isinstance(v, bool) else str(v)


def _exp(e, body):
    a = e.get('action') or {}
    b, af = e.get('before'), e.get('after')
    if not a or not isinstance(b, dict) or not isinstance(af, dict) or e.get('response') is None:
        return None
    args = [str(x) for x in a.get('args', [])]
    if not args or len(set(args)) != len(args) or not all(isinstance(b.get(x), dict) and isinstance(af.get(x), dict) and b[x] for x in args):
        return None
    return {'body': e.get('body', body), 'tool': a['tool'], 'args': args, 'before': {x: {k: _val(v) for k, v in b[x].items()} for x in args},
            'after': {x: {k: _val(v) for k, v in af[x].items()} for x in args}, 'ok': bool(e['response'].get('ok'))}


class LawKnower:
    def __init__(self, store, body, seed=0):
        self.store, self.body = store, body
        self.seen, self.by = 0, defaultdict(list)          # (body, tool) -> experiences
        self.built, self.lib, self.past = -1, {}, {}
        self.memo, self.trust = {}, {}
        self.counts = {'asked': 0, 'sure': 0}

    def _sync(self):
        items = self.store.items
        for e in items[self.seen:]:
            x = _exp(e, self.body)
            if x is not None:
                self.by[(x['body'], x['tool'])].append(x)
        self.seen = len(items)

    def _memory(self, key):
        """the law memory and the tools of everything lived except this tool (rebuilt when 50 more experiences came)."""
        n = sum(len(v) for k, v in self.by.items() if k != key)
        if key not in self.lib or n - self.lib[key][0] >= 50:
            groups = defaultdict(list)
            for k, v in self.by.items():
                if k != key:
                    groups[k].append(v)
            places = [{'course': [dict(e, tool=f'{k[0]}/{k[1]}') for e in v[0]], 'queries': []} for k, v in groups.items()]
            tools = []
            for p in places:
                try:
                    tools.append(Tool(p['course']))
                except Exception:
                    pass
            self.lib[key] = (n, library({'places': places}, len(places)), tools)
        return self.lib[key][1], self.lib[key][2]

    def predict(self, tool, args, before):
        if not all(isinstance(b, dict) and b for b in before):
            return None
        self._sync()
        key = (self.body, tool)
        sargs = [str(a) for a in args]
        f = {(i, k): _val(v) for i, b in enumerate(before) for k, v in b.items()}
        E = [e for e in self.by.get(key, []) if set(feats(e)) == set(f)]
        if len(E) < 2:
            return None
        mk = (tool, json.dumps(sorted((str(k), str(v)) for k, v in f.items())), len(E))
        if mk in self.memo:
            return self.memo[mk]
        self.counts['asked'] += 1
        lib, past = self._memory(key)
        tk = (tool, len(E))
        if tk not in self.trust:                           # would its expectations of this tool's own experiences have come true?
            tests = []
            for i in range(max(0, len(E) - 5), len(E)):
                p = Knows(E[:i] + E[i + 1:], lib, past).predict(feats(E[i]))
                if p is not None:
                    tests.append(came_true(p, E[i]))
            self.trust[tk] = (trusted(tests), Knows(E, lib, past))
        ok, k = self.trust[tk]
        y = None
        if ok:
            p = k.predict(f)
            if p is not None and p[0] == 'ok':             # 'it will work' only from a start like a success it lived with this tool
                good = [feats(e) for e in E if e['ok']]
                for z, v in f.items():
                    vals = [g[z] for g in good]
                    if not vals or (v not in vals and not (isinstance(v, int) and all(isinstance(x, int) for x in vals) and min(vals) <= v <= max(vals))):
                        p = None
                        break
            if p is not None:
                y = {('r',): 'failed' if p[0] == 'refused' else 'ok'}
                for (i, a), v in f.items():
                    y[(i, a)] = str(v if p[0] == 'refused' else p[1].get((i, a), v))
                self.counts['sure'] += 1
        self.memo[mk] = y
        return y
