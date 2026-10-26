"""Grounding learner (first stage of language learning v2): shared meaning from non-verbal events before any word.

The person and ATANOR look at the same world. The person can POINT at some objects, DEMOnstrate an action once, answer
a CONTRAST question ("this one too?") and CONFIRM or reject what ATANOR did. From these ATANOR forms
  - selection concepts: which observed atoms the pointed objects share and the others lack; when several criteria fit
    the evidence and would pick different objects, it asks about the object that splits them most evenly;
  - action concepts: what a demonstrated tool call changed, with its arguments as roles (the object acted on, or a
    constant second object), reproduced on other objects;
  - only then symbols: a user symbol is bound to an internal concept that already exists.
Nothing here knows a word, a body name or an attribute meaning: objects are compared through anonymous observed atoms
(agent.concepts.atoms). Everything kept is in agent.memory (events, claims with evidence, ontology graph).

Memory modes (for comparison): FULL (events readable, claims kept), ONTO (claims and graph kept, past events not
readable after a restart), RAW (only events kept; concepts are re-derived from the retrieved raw events when needed).
"""
import itertools
import json
from collections import Counter
from pathlib import Path

from .concepts import FAMILIES_ALL, atoms
from .memory import ClaimLedger, Memory

MAX_ATOMS = 3
QUESTION_BUDGET = 6


class Grounder:
    def __init__(self, home, mind_dir, person=None, mode='FULL', core='g1', passive=False, structure=None):
        self.home, self.person, self.mode, self.core, self.passive = home, person, mode, core, passive
        self.structure = structure                 # None (joint explanation only) or 'order' (phrase positions)
        self.body = getattr(home, 'BODY', '?')
        self.dir = Path(mind_dir)
        self.mem = Memory(self.dir, events_readable=mode in ('FULL', 'RAW'), persist_claims=mode in ('FULL', 'ONTO'),
                          stamp={'body': self.body, 'core': core})
        self.caps = {c: True for c in set(getattr(home, 'CAPABILITY', {}).values())}
        self.counts = Counter()
        self.scope = {'body': self.body, 'core': core}

    # ---------------------------------------------------------------- perception
    def feats(self):
        objs = self.home.existing()
        st = self.home.observe(objs)
        return {o: frozenset(repr(a) for a in atoms(self.body, st, (o,), FAMILIES_ALL) if a[0] != 'E') for o in objs}

    @staticmethod
    def extension(cond, feats):
        return sorted(o for o, f in feats.items() if set(cond) <= f)

    # ---------------------------------------------------------------- selection concepts
    @staticmethod
    def hypotheses(pos, neg, feats):
        common = frozenset.intersection(*[feats[p] for p in pos]) if pos else frozenset()
        out = []
        for k in range(1, MAX_ATOMS + 1):
            for h in itertools.combinations(sorted(common), k):
                if not any(set(h) <= feats[n] for n in neg if n in feats):
                    out.append(frozenset(h))
        return out

    def _query(self, hyps, feats, labelled):
        """The unlabelled object whose answer splits the hypotheses' prior weight most evenly (simpler = likelier)."""
        w = {h: 2.0 ** -len(h) for h in hyps}
        total = sum(w.values())
        best, best_s = None, 0.0
        for o, f in feats.items():
            if o in labelled:
                continue
            p_in = sum(v for h, v in w.items() if h <= f)
            s = min(p_in, total - p_in)
            if s > best_s + 1e-12:
                best, best_s = o, s
        return best

    def settle(self, pos, neg, feats, budget=QUESTION_BUDGET, lesson=None):
        """Ask contrast questions until the surviving criteria agree on which objects they pick (or nothing splits them)."""
        evs = []
        for _ in range(budget):
            hyps = self.hypotheses(pos, neg, feats)
            classes = {tuple(self.extension(h, feats)) for h in hyps}
            if len(classes) <= 1 or self.person is None or self.passive:
                break
            x = self._query(hyps, feats, pos | neg)
            if x is None:
                break
            ans = self.person.contrast(x)
            self.counts['contrast'] += 1
            evs.append(self.mem.events.append('contrast', lesson=lesson, object=x, answer=ans, feats=sorted(feats[x])))
            (pos if ans else neg).add(x)
        hyps = self.hypotheses(pos, neg, feats)
        if not hyps:
            return None, evs
        if self.passive:                                     # baseline: the most specific criterion, no questions
            common = frozenset.intersection(*[feats[p] for p in pos])
            return {'atoms': sorted(common), 'alternatives': []}, evs
        best = min(hyps, key=lambda h: (len(h), sorted(h)))
        ext = self.extension(best, feats)
        alts = [sorted(h) for h in hyps if h != best and self.extension(h, feats) == ext]
        return {'atoms': sorted(best), 'alternatives': alts[:8]}, evs

    def learn_selection(self, lesson):
        feats = self.feats()
        pts = self.person.point()
        self.counts['point'] += 1
        ev = self.mem.events.append('point', lesson=lesson, objects=pts, feats={o: sorted(feats[o]) for o in pts})
        crit, evs = self.settle(set(pts), set(), feats, lesson=lesson)
        if crit is None:
            return None
        # two lessons whose evidence could not be told apart are still two concepts (the person may name them apart);
        # a symbol taught again replaces its earlier link (bind(replace=True)), so no node is reused here
        cid = f'k{len(self.mem.claims.claims(usable=False))}'
        claim = self.mem.claims.add('selects', {'concept': cid, **crit, 'lesson': lesson}, [ev] + evs, 'inferred', self.scope)
        g = self.mem.graph
        g.node(cid, 'concept')
        for a in crit['atoms']:
            g.link(cid, 'defined_by', g.node(a, 'atom'), claim['id'])
        for o in pts:
            g.link(g.node(o, 'object'), 'pointed_as', cid, claim['id'])
        g.save()
        return claim

    # ---------------------------------------------------------------- action concepts
    def learn_action(self, lesson):
        fb = self.feats()
        demo = self.person.demo()
        self.counts['demo'] += 1
        fa = self.feats()
        x = demo['object']
        template = [self._role(a, x, fb) for a in demo['args']]
        gained = sorted(fa[x] - fb.get(x, frozenset())) if x in fa else ["('gone',)"]
        lost = sorted(fb.get(x, frozenset()) - fa.get(x, frozenset()))
        made = sorted({a for r in template if isinstance(r, list) and r[0] == 'C' for a in fa.get(self.home.compose(r[1], x), ())})
        ev = self.mem.events.append('demo', lesson=lesson, tool=demo['tool'], args=demo['args'], object=x, gained=gained, lost=lost, made=made)
        same = [c for c in self.mem.claims.claims('effect') if c['content']['tool'] == demo['tool']
                and c['content']['template'] == template and c['content']['gained'] == gained]
        if same:
            return self.mem.claims.revise(same[0]['id'], support=[ev], status='active')
        aid = f'a{len(self.mem.claims.claims(usable=False))}'
        content = {'action': aid, 'tool': demo['tool'], 'template': template, 'gained': gained, 'lost': lost, 'made': made, 'lesson': lesson}
        claim = self.mem.claims.add('effect', content, [ev], 'observed', self.scope)
        g = self.mem.graph
        g.node(aid, 'action')
        g.link(aid, 'uses', g.node(f"tool:{demo['tool']}", 'tool'), claim['id'])
        g.save()
        return claim

    def _role(self, a, x, feats):
        """An argument of a demonstrated call, as a role: the object acted on, an object the world composes from a
        container and it (when the body offers composition), or a constant object."""
        if a == x:
            return 'X'
        compose = getattr(self.home, 'compose', None)
        if compose:
            for k in feats:
                if k != x and compose(k, x) == a:
                    return ['C', k]
        return ['K', a]

    def _arg(self, r, o):
        return o if r == 'X' else (self.home.compose(r[1], o) if r[0] == 'C' else r[1])

    def _done(self, effect, f_before, f_now, o):
        """The object already shows what the action produces."""
        made = [r for r in effect['template'] if isinstance(r, list) and r[0] == 'C']
        if made and not all(self._arg(r, o) in f_now for r in made):
            return False
        if any(a == "('gone',)" for a in effect['gained']):
            return o not in f_now
        if made:
            return True
        gained = {a for a in effect['gained'] if a != "('gone',)"}
        return o in f_now and gained <= f_now[o]

    @staticmethod
    def _attr(atom_repr):
        parts = atom_repr.split(',')
        return parts[2].strip(" '") if atom_repr.startswith("('U'") and len(parts) > 3 else None

    def _rewritten(self, effect):
        """Attributes the action changes on its object: a criterion over them describes the old state, not the objects."""
        return {self._attr(a) for a in effect.get('gained', []) + effect.get('lost', [])} - {None}

    def apply(self, sel, effect, lesson=None):
        """Do the action on every object the concept picks that does not show its effect yet."""
        feats = self.feats()
        ext = self.extension(sel['atoms'], feats)
        acted, failed = [], []
        for o in ext:
            if self._done(effect, feats, feats, o):
                continue
            args = tuple(self._arg(a, o) for a in effect['template'])
            if len(set(args)) != len(args):
                continue
            try:
                res = self.home.execute(effect['tool'], args, self.caps)
            except ValueError:
                res = {'ok': False, 'error': 'invalid action'}
            ev = self.mem.events.append('act', lesson=lesson, tool=effect['tool'], args=list(args), ok=res['ok'], error=res.get('error'))
            (acted if res['ok'] else failed).append((o, ev))
            self.counts['actions'] += 1
        return acted, failed

    # ---------------------------------------------------------------- symbols
    def bind(self, symbol, node, lesson=None, replace=False):
        """The person names something. replace: the person is re-teaching what this symbol means, so its earlier links
        become superseded (kept, with this naming as their counter-evidence)."""
        ev = self.mem.events.append('name', lesson=lesson, symbol=symbol, node=node)
        old = [c for c in self.mem.claims.claims('denotes') if c['content']['symbol'] == symbol]
        if any(c['content']['refers'] == node for c in old):
            c = next(c for c in old if c['content']['refers'] == node)
            if replace:
                for o in old:
                    if o['content']['refers'] != node:
                        self.mem.claims.revise(o['id'], counter=[ev], status='superseded')
                        self.mem.graph.unlink_claim(o['id'])
            return self.mem.claims.revise(c['id'], support=[ev], status='active')
        if replace:
            for o in old:
                self.mem.claims.revise(o['id'], counter=[ev], status='superseded')
                self.mem.graph.unlink_claim(o['id'])
        c = self.mem.claims.add('denotes', {'symbol': symbol, 'refers': node, 'lesson': lesson}, [ev], 'user_said', self.scope)
        g = self.mem.graph
        g.link(g.node(f'sym:{symbol}', 'symbol'), 'denotes', node, c['id'])
        g.save()
        return c

    def name_phrase(self, words, node, lesson=None):
        """The person says a phrase of several words while pointing or demonstrating: each word is bound as a symbol, and
        the order in which they were said is kept as one more user_said claim (used only with structure='order')."""
        for w in words:
            self.bind(w, node, lesson)
        ev = self.mem.events.append('phrase', lesson=lesson, words=list(words), node=node)
        same = [c for c in self.mem.claims.claims('phrase') if c['content']['refers'] == node and c['content']['words'] == list(words)]
        if same:
            return self.mem.claims.revise(same[0]['id'], support=[ev])
        c = self.mem.claims.add('phrase', {'words': list(words), 'refers': node, 'lesson': lesson}, [ev], 'user_said', self.scope)
        g = self.mem.graph
        g.link(node, 'said_as', g.node(f'phrase:{c["id"]}', 'phrase'), c['id'])
        g.save()
        return c

    def _phrases(self, node):
        if self.mode == 'RAW':
            ps = [e['words'] for e in self.mem.events.all() if e['kind'] == 'phrase' and e.get('node') == node and e.get('body') in (None, self.body)]
        else:
            ps = [c['content']['words'] for c in self.mem.claims.claims('phrase') if c['content']['refers'] == node and self._in_scope(c)]
        return [list(p) for p in {tuple(p) for p in ps}]

    @staticmethod
    def _align(words, p, q):
        """Most command words that can be read as two phrases at once: each phrase's words in the order it was said
        (words may be left out or come between), every command word read at most once, and the two readings not crossing
        (one phrase may sit inside the other, but p q p q is not a reading). Positions only; no word is known."""
        from functools import lru_cache
        n = len(words)

        @lru_cache(maxsize=None)
        def best(i, jp, jq, runs):
            if i == n:
                return 0
            out = best(i + 1, jp, jq, runs)                         # this word is read by neither phrase
            for lab, ph, j in (('p', p, jp), ('q', q, jq)):
                r = runs if runs and runs[-1] == lab else runs + lab
                if len(r) > 3:                                     # p q p q: the phrases would cross
                    continue
                for k in range(j, len(ph)):
                    if ph[k] == words[i]:
                        nxt = (k + 1, jq) if lab == 'p' else (jp, k + 1)
                        out = max(out, 1 + best(i + 1, nxt[0], nxt[1], r))
                        break                                      # the earliest match leaves the most room
            return out
        return best(0, 0, 0, '')

    def _order_score(self, words, s, a):
        """(words read in order, minus words of the two phrases left unsaid): a phrase said only in part is a weaker
        reading than one said whole."""
        ps, pa = self._phrases(s), self._phrases(a)
        if not ps or not pa:
            return (0, 0)
        out = []
        for x in ps:
            for y in pa:
                k = self._align(tuple(words), tuple(x), tuple(y))
                out.append((k, k - len(x) - len(y)))
        return max(out)

    def _in_scope(self, c):
        """A claim learned in another body (or under another core) says nothing about this one."""
        sc = c.get('scope') or {}
        return sc.get('body') in (None, self.body)

    def _definition(self, node):
        """The claim that defines an internal concept or action (claims memory), or re-derived from raw events (RAW)."""
        for c in self.mem.claims.claims():
            if not self._in_scope(c):
                continue
            if c['kind'] in ('selects', 'effect') and c['content'].get('concept', c['content'].get('action')) == node:
                return c
        return None

    def lookup(self, symbol):
        """What a symbol refers to, from claims (FULL/ONTO) or from retrieved raw events (RAW)."""
        if self.mode == 'RAW':
            return self._from_events(symbol)
        hits = [r for r in self.mem.retrieve([f'sym:{symbol}'], depth=2) if r['claim']['kind'] == 'denotes']
        self.counts['retrievals'] += 1
        if not hits:
            return None
        node = hits[0]['claim']['content']['refers']
        d = self._definition(node)
        return d and {'kind': d['kind'], 'claim': d, 'via': hits[0]['claim']['id'], 'is': hits[0]['is']}

    def _from_events(self, symbol, node=None):
        """RAW memory: find the naming event, then re-derive the concept from that lesson's own raw events."""
        evs = [e for e in self.mem.events.all() if e.get('body') in (None, self.body)]      # this body's own experience
        names = [e for e in evs if e['kind'] == 'name' and e.get('symbol') == symbol and (node is None or e['node'] == node)]
        if not names:
            return None
        e = names[-1]
        lesson, node = e['lesson'], e['node']
        les = [x for x in evs if x.get('lesson') == lesson]
        if node.startswith('k'):
            pts = next((x for x in les if x['kind'] == 'point'), None)
            if pts is None:
                return None
            feats = {o: frozenset(f) for o, f in pts['feats'].items()}
            pos = set(pts['objects'])
            neg = set()
            for x in les:
                if x['kind'] == 'contrast':
                    feats[x['object']] = frozenset(x['feats'])
                    (pos if x['answer'] else neg).add(x['object'])
            hyps = self.hypotheses(pos, neg, feats)
            if not hyps:
                return None
            best = min(hyps, key=lambda h: (len(h), sorted(h)))
            return {'kind': 'selects', 'claim': {'content': {'atoms': sorted(best), 'alternatives': []}, 'id': None}, 'via': e['id'], 'is': 'fact'}
        demo = next((x for x in les if x['kind'] == 'demo'), None)
        if demo is None:
            return None
        template = ['X' if a == demo['object'] else ['K', a] for a in demo['args']]
        return {'kind': 'effect', 'claim': {'content': {'tool': demo['tool'], 'template': template, 'gained': demo['gained'], 'lost': demo['lost']}, 'id': None},
                'via': e['id'], 'is': 'fact'}

    def _nodes(self, word):
        """Internal nodes a word has been bound to (claims memory, or the raw naming events in RAW)."""
        if self.mode == 'RAW':
            return {e['node'] for e in self.mem.events.all() if e['kind'] == 'name' and e.get('symbol') == word and e.get('body') in (None, self.body)}
        hits = [r['claim'] for r in self.mem.retrieve([f'sym:{word}'], depth=2) if r['claim']['kind'] == 'denotes' and self._in_scope(r['claim'])]
        return {c['content']['refers'] for c in hits if c['content']['symbol'] == word}

    def resolve(self, words):
        """Which one selection concept and one action, together, explain the most words (a word bound to several nodes
        counts for whichever of them is chosen). A tie between different readings is unresolved."""
        self.counts['retrievals'] += 1
        nodes = {w: self._nodes(w) for w in words}
        defs = {}
        for ns in nodes.values():
            for n in ns:
                if n not in defs:
                    if self.mode == 'RAW':
                        sym = next(w for w, x in nodes.items() if n in x)
                        d = self._from_events(sym, node=n)
                    else:
                        c = self._definition(n)
                        d = c and {'kind': c['kind'], 'claim': c, 'via': c['id'], 'is': 'user_said'}
                    defs[n] = d
        sel_n = [n for n, d in defs.items() if d and d['kind'] == 'selects']
        act_n = [n for n, d in defs.items() if d and d['kind'] == 'effect']
        def key(s, a):
            base = sum(1 for ns in nodes.values() if s in ns or a in ns)
            return (base, self._order_score(words, s, a)) if self.structure == 'order' else (base,)
        scored = sorted(((key(s, a), s, a) for s in sel_n for a in act_n), reverse=True)
        unknown = [w for w, ns in nodes.items() if not ns]
        if not scored or (len(scored) > 1 and scored[0][0] == scored[1][0]):
            return None, None, unknown
        _, s, a = scored[0]
        return defs[s], defs[a], unknown

    def obey(self, symbols, task=None):
        """A command made of symbols or words (in any order). Never acts on an unresolved reading alone."""
        ev = self.mem.events.append('say', task=task, symbols=list(symbols))
        sel_d, act_d, unknown = self.resolve(symbols)
        if sel_d is None:
            self.counts['held_unresolved'] += 1
            return {'ok': False, 'why': 'unresolved', 'unknown': unknown, 'event': ev}
        sels, acts = [sel_d], [act_d]
        sel, act = sels[0]['claim']['content'], acts[0]['claim']['content']
        feats = self.feats()
        alts = sel.get('alternatives', [])
        todo = lambda cond: [o for o in self.extension(cond, feats) if not self._done(act, feats, feats, o)]
        ext = self.extension(sel['atoms'], feats)
        disagree = any(todo(a) != todo(sel['atoms']) for a in alts)   # only objects still to act on matter
        if disagree:                                          # criteria that fitted the lesson pick different objects now
            if self.person is None:
                self.counts['held_ambiguous'] += 1
                return {'ok': False, 'why': 'ambiguous generalization', 'event': ev}
            sel = self._resettle({**sels[0], 'claim': {**sels[0]['claim'], 'content': {**sel, 'alternatives': alts}}}, feats, task)
        acted, failed = self.apply(sel, act, lesson=task)
        if failed and acts[0]['claim'].get('id'):
            self.mem.counter(acts[0]['claim']['id'], failed[0][1])       # the tool did not do what the claim said
            self.counts['effect_counterexamples'] += 1
        return {'ok': not failed, 'acted': [o for o, _ in acted], 'failed': [o for o, _ in failed], 'selection': ext,
                'used': [sels[0]['via'], acts[0]['via']], 'retrieved_as': [sels[0]['is'], acts[0]['is']], 'event': ev}

    def _resettle(self, sel_hit, feats, task):
        """With the person: ask contrast questions now to choose between criteria that disagree on the present objects."""
        c = sel_hit['claim']
        content = c['content']
        cands = [frozenset(content['atoms'])] + [frozenset(a) for a in content.get('alternatives', [])]
        pos, neg = set(), set()
        for _ in range(QUESTION_BUDGET):
            classes = {tuple(self.extension(h, feats)) for h in cands}
            if len(classes) <= 1:
                break
            x = self._query(cands, feats, pos | neg)
            if x is None:
                break
            ans = self.person.contrast(x)
            self.counts['contrast'] += 1
            e = self.mem.events.append('contrast', lesson=task, object=x, answer=ans, feats=sorted(feats[x]))
            (pos if ans else neg).add(x)
            cands = [h for h in cands if (h <= feats[x]) == ans]
            if c.get('id'):
                if ans != (frozenset(content['atoms']) <= feats[x]):
                    self.mem.counter(c['id'], e)
        if not cands:
            return content
        best = min(cands, key=lambda h: (len(h), sorted(h)))
        new = {**content, 'atoms': sorted(best), 'alternatives': [sorted(h) for h in cands if h != best]}
        if c.get('id'):
            self.mem.claims.revise(c['id'], content=new, status='active')
        return new

    def reply(self, ok):
        """The person's verdict on what was done (CONFIRM)."""
        return self.mem.events.append('confirm', answer=ok)
