"""Ontology long-term memory: what ATANOR keeps from its own experience, in separate layers (body-free, word-free).

1. EventLog      - observations, point, demo, contrast, confirm, actions and their actual results. Append only: an
                   event is never edited or replaced by a summary.
2. ClaimLedger   - claims derived from events: 'selects' (a set of objects is what shares these observed atoms),
                   'effect' (this tool, on these argument roles, changes these attributes), 'denotes' (this user
                   symbol refers to this internal concept or action). Each claim keeps its supporting events, its
                   counter-events, its scope (body, core version), its origin and a status. Revising a claim makes a
                   new version; the old one stays (status 'superseded'). Observation and inference are never mixed:
                   origin is 'observed' (seen happen), 'inferred' (a hypothesis from evidence), 'user_said' (the
                   person's word) or 'proposal' (an outside suggestion, e.g. from Claude: never used for acting until
                   ATANOR's own observation turns it into a claim).
3. Ontology      - a graph of objects, observed atoms, internal concepts, actions, tools and user symbols. Node ids
                   come from observation (object ids, anonymous attribute atoms) or are minted for concepts; no body
                   name or English word is part of a fixed ontology.
4. retrieve()    - from cues (symbols, object ids, concepts, tools) follows graph edges to the claims that bear on
                   them; every result says whether it is a raw fact (event), a hypothesis (inferred claim) or what
                   the person said.
5. Revision      - a counter-example marks the claim and the claims that depend on it 'needs_recheck'; a re-derived
                   claim is a new version with all old evidence carried over.
"""
import json
from collections import defaultdict, deque
from pathlib import Path

ACTIVE = ('active', 'needs_recheck')


class EventLog:
    def __init__(self, path, readable=True, stamp=None):
        self.path = Path(path) if path else None
        self.readable = readable
        self.stamp = dict(stamp or {})             # e.g. the body and core version every event of this session belongs to
        self._events = []
        self._n = 0
        if self.path and self.path.exists():
            lines = self.path.read_text(encoding='utf-8').splitlines()
            self._n = len(lines)
            if readable:
                self._events = [json.loads(l) for l in lines]

    def append(self, kind, **data):
        e = {'id': f'e{self._n}', 'kind': kind, **self.stamp, **data}
        self._n += 1
        self._events.append(e)
        if self.path:
            with open(self.path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(e, default=str) + '\n')
        return e['id']

    def all(self):
        return list(self._events)

    def get(self, eid):
        return next((e for e in self._events if e['id'] == eid), None)


class ClaimLedger:
    def __init__(self, path):
        self.path = Path(path) if path else None
        self.versions = []                      # every version of every claim, in order
        if self.path and self.path.exists():
            self.versions = [json.loads(l) for l in self.path.read_text(encoding='utf-8').splitlines() if l.strip()]

    def _write(self, c):
        self.versions.append(c)
        if self.path:
            with open(self.path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(c, default=str) + '\n')
        return c

    def current(self, cid):
        vs = [c for c in self.versions if c['id'] == cid]
        return vs[-1] if vs else None

    def claims(self, kind=None, usable=True):
        latest = {}
        for c in self.versions:
            latest[c['id']] = c
        out = [c for c in latest.values() if (kind is None or c['kind'] == kind)]
        return [c for c in out if c['status'] in ACTIVE] if usable else out

    def add(self, kind, content, support, origin, scope):
        n = len({c['id'] for c in self.versions})
        return self._write({'id': f'c{n}', 'v': 1, 'kind': kind, 'content': content, 'support': list(support), 'counter': [],
                            'scope': scope, 'origin': origin, 'status': 'proposal' if origin == 'proposal' else 'active', 'prev': None})

    def revise(self, cid, content=None, support=(), counter=(), status=None, origin=None):
        old = self.current(cid)
        if old['status'] == 'active' or old['status'] == 'needs_recheck' or old['status'] == 'proposal':
            self._write({**old, 'status': 'superseded', 'v': old['v']})
        new = {**old, 'v': old['v'] + 1, 'content': content if content is not None else old['content'],
               'support': old['support'] + [e for e in support if e not in old['support']],
               'counter': old['counter'] + [e for e in counter if e not in old['counter']],
               'status': status or 'active', 'origin': origin or old['origin'], 'prev': f"{cid}.v{old['v']}"}
        return self._write(new)

    @staticmethod
    def confidence(c):
        return (len(c['support']) + 1) / (len(c['support']) + len(c['counter']) + 2)


class Ontology:
    def __init__(self, path):
        self.path = Path(path) if path else None
        self.nodes, self.edges = {}, []
        if self.path and self.path.exists():
            d = json.loads(self.path.read_text(encoding='utf-8'))
            self.nodes, self.edges = d['nodes'], [tuple(e) for e in d['edges']]

    def save(self):
        if self.path:
            self.path.write_text(json.dumps({'nodes': self.nodes, 'edges': self.edges}), encoding='utf-8')

    def node(self, nid, ntype):
        self.nodes.setdefault(nid, {'type': ntype})
        return nid

    def link(self, src, rel, dst, claim=None):
        e = (src, rel, dst, claim)
        if e not in self.edges:
            self.edges.append(e)

    def unlink_claim(self, claim):
        self.edges = [e for e in self.edges if e[3] != claim]

    def neighbours(self, nid):
        for s, r, d, c in self.edges:
            if s == nid:
                yield d, r, c
            elif d == nid:
                yield s, r, c


class Memory:
    """The three layers together, with retrieval and revision."""

    def __init__(self, mind_dir, events_readable=True, persist_claims=True, stamp=None):
        d = Path(mind_dir)
        d.mkdir(parents=True, exist_ok=True)
        self.events = EventLog(d / 'events.jsonl', readable=events_readable, stamp=stamp)
        self.claims = ClaimLedger(d / 'claims.jsonl' if persist_claims else None)
        self.graph = Ontology(d / 'ontology.json' if persist_claims else None)

    def retrieve(self, cues, depth=2):
        """Claims connected to the cue nodes within `depth` graph steps, most confident first, each tagged with what it is."""
        seen, q, found = set(cues), deque((c, 0) for c in cues if c in self.graph.nodes), {}
        while q:
            n, k = q.popleft()
            for m, rel, cid in self.graph.neighbours(n):
                if cid:
                    c = self.claims.current(cid)
                    if c and c['status'] in ACTIVE:
                        found[cid] = c
                if m not in seen and k + 1 < depth:
                    seen.add(m)
                    q.append((m, k + 1))
        tag = {'observed': 'fact', 'inferred': 'hypothesis', 'user_said': 'user_said'}
        return sorted(({'claim': c, 'is': tag.get(c['origin'], c['origin'])} for c in found.values()),
                      key=lambda r: -ClaimLedger.confidence(r['claim']))

    def counter(self, cid, event):
        """A counter-example: the claim and every claim that refers to what it is about must be re-verified."""
        c = self.claims.revise(cid, counter=[event], status='needs_recheck')
        about = set(json.dumps(c['content'], sort_keys=True, default=str).split('"'))
        for other in self.claims.claims():
            if other['id'] != cid and other['kind'] == 'denotes' and other['content'].get('refers') in about:
                self.claims.revise(other['id'], counter=[event], status='needs_recheck')
        return c

    def propose(self, kind, content, note):
        """An outside suggestion (e.g. Claude reading the graph): stored, never acted on until verified."""
        return self.claims.add(kind, {**content, 'note': note}, [], 'proposal', {'body': None, 'core': None})
