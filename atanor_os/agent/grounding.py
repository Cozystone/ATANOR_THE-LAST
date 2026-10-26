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
    def __init__(self, home, mind_dir, person=None, mode='FULL', core='g1', passive=False, structure='order', source='program',
                 experiment=True):
        self.home, self.person, self.mode, self.core, self.passive = home, person, mode, core, passive
        self.structure = structure                 # 'order' (phrase positions; adopted after seed 4) or None (joint explanation only)
        self.experiment = experiment               # try other tools in a lab copy when a remembered call stops working
        self.source = source                       # whose teaching this experience comes from: 'program' (the regression
                                                   # tutor) or 'human' (a real person through the interface)
        self.body = getattr(home, 'BODY', '?')
        self.dir = Path(mind_dir)
        self.mem = Memory(self.dir, events_readable=mode in ('FULL', 'RAW'), persist_claims=mode in ('FULL', 'ONTO'),
                          stamp={'body': self.body, 'core': core, 'source': source})
        self.caps = {c: True for c in set(getattr(home, 'CAPABILITY', {}).values())}
        self.counts = Counter()
        self.scope = {'body': self.body, 'core': core, 'source': source}

    def _from_source(self, node, claim):
        """The ontology keeps where a concept, action or name came from (a real person or the program tutor)."""
        g = self.mem.graph
        g.link(node, 'learned_from', g.node(f'source:{self.source}', 'source'), claim['id'])
        g.save()

    # ---------------------------------------------------------------- perception
    def feats(self, home=None):
        home = home or self.home
        objs = home.existing()
        st = home.observe(objs)
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
        self._from_source(cid, claim)
        return claim

    def known_concept(self, lesson, phrase=None):
        """The person points while saying a name: which concept already shared is meant? The known concepts that fit the
        pointed objects are told apart by contrast questions (the object that splits them most evenly). None if no single
        one is left (the caller then learns a new concept from pointing). Concepts this world cannot split: one that
        already carries this phrase keeps it; else one with no other name (a new name is for something not yet named)."""
        feats = self.feats()
        pts = self.person.point()
        self.counts['point'] += 1
        self.mem.events.append('point', lesson=lesson, objects=pts, feats={o: sorted(feats[o]) for o in pts})
        cands = [c for c in self.mem.claims.claims('selects') if self._in_scope(c) and c['status'] == 'active'
                 and all(set(c['content']['atoms']) <= feats[o] for o in pts)]
        ext = lambda c: frozenset(self.extension(c['content']['atoms'], feats))
        asked = set(pts)
        for _ in range(QUESTION_BUDGET):
            classes = {ext(c) for c in cands}
            if len(classes) <= 1 or self.passive:
                break
            split = sorted(frozenset.union(*classes) - frozenset.intersection(*classes) - asked)
            if not split:
                break
            o = min(split, key=lambda x: abs(sum(x in e for e in classes) - len(classes) / 2))
            ans = self.person.contrast(o)
            self.counts['contrast'] += 1
            self.mem.events.append('contrast', lesson=lesson, object=o, answer=ans)
            asked.add(o)
            cands = [c for c in cands if (o in ext(c)) == ans]
        if not cands or (len({ext(c) for c in cands}) > 1 and not self.passive):
            return None
        said = [list(x) for x in (phrase,)] if phrase else []
        def names(c):
            return self._phrases(c['content']['concept'])
        return sorted(cands, key=lambda c: (not any(p in names(c) for p in said), bool(names(c)) and not any(p in names(c) for p in said),
                                            len(ext(c)), c['id']))[0]

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
        own = fb.get(x, frozenset())
        same = {self._attr(a) for a in own} - {None}
        made_rel = sorted({(f"('=x', '{self._attr(a)}')" if self._attr(a) in same and a in own else a) for a in made})   # what the
        # made object took from the object acted on is recorded as such, so two demonstrations on different objects agree
        ev = self.mem.events.append('demo', lesson=lesson, tool=demo['tool'], args=demo['args'], object=x, gained=gained, lost=lost, made=made)
        same = [c for c in self.mem.claims.claims('effect') if c['content']['tool'] == demo['tool']
                and c['content']['template'] == template and c['content']['gained'] == gained]
        if same:
            return self.mem.claims.revise(same[0]['id'], support=[ev], status='active')
        aid = f'a{len(self.mem.claims.claims(usable=False))}'
        content = {'action': aid, 'tool': demo['tool'], 'template': template, 'gained': gained, 'lost': lost, 'made': made,
                   'made_rel': made_rel, 'lesson': lesson}
        claim = self.mem.claims.add('effect', content, [ev], 'observed', self.scope)
        g = self.mem.graph
        g.node(aid, 'action')
        g.link(aid, 'uses', g.node(f"tool:{demo['tool']}", 'tool'), claim['id'])
        g.save()
        self._from_source(aid, claim)
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

    def _made_exists(self, effect, f_now, o):
        made = [r for r in effect['template'] if isinstance(r, list) and r[0] == 'C']
        return bool(made) and all(self._arg(r, o) in f_now for r in made) and o in f_now

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

    LAB_BUDGET = 12

    def _experiment(self, claim, o, task):
        """The remembered call no longer brings its change. In a lab copy, try the body's other tools that take as many
        arguments, with the same arguments in every order, on the object that failed. A call that brings the remembered
        change revises the action claim (a new version; the old one stays, and so do its names)."""
        eff = claim['content']
        args = [self._arg(r, o) for r in eff['template']]
        tools = getattr(self.home, 'tools', lambda: {})()
        lab_root = self.dir / 'lab'
        tried = 0
        for tool in sorted(t for t, n in tools.items() if n == len(args) and t != eff['tool']):
            for order in itertools.permutations(range(len(args))):
                if tried >= self.LAB_BUDGET:
                    return None
                tried += 1
                lab = self.home.lab_copy(lab_root, self.home.existing())   # the whole present world, so containers come too
                before = self.feats(lab)
                call = [args[i] for i in order]
                try:
                    res = lab.execute(tool, tuple(call), self.caps)
                except ValueError:
                    res = {'ok': False}
                self.counts['lab_actions'] += 1
                after = self.feats(lab)
                ev = self.mem.events.append('experiment', task=task, tool=tool, args=call, ok=res.get('ok'))
                brought = not self._done(eff, before, before, o) and self._done(eff, before, after, o)   # the remembered change, now
                if "('gone',)" not in eff['gained'] and o not in after:
                    brought = False                        # and nothing it never did: the object did not vanish before
                if res.get('ok') and brought:
                    template = [eff['template'][i] for i in order]
                    new = self.mem.claims.revise(claim['id'], content={**eff, 'tool': tool, 'template': template}, support=[ev],
                                                 status='active', origin='observed')
                    g = self.mem.graph
                    g.link(eff['action'], 'uses', g.node(f'tool:{tool}', 'tool'), new['id'])
                    g.save()
                    self.counts['experiments_found'] += 1
                    return new
        return None

    # ---------------------------------------------------------------- symbols
    def bind(self, symbol, node, lesson=None, replace=False):
        """The person names something. replace: the person is re-teaching what this symbol means, so its earlier links
        become superseded (kept, with this naming as their counter-evidence)."""
        ev = self.mem.events.append('name', lesson=lesson, symbol=symbol, node=node)
        old = [c for c in self.mem.claims.claims('denotes') if c['content']['symbol'] == symbol and self._in_scope(c)]   # this body only
        if any(c['content']['refers'] == node for c in old):
            c = next(c for c in old if c['content']['refers'] == node)
            if replace:
                for o in old:
                    if o['content']['refers'] != node:
                        self.mem.claims.revise(o['id'], counter=[ev], status='superseded')
                        self.mem.graph.unlink_claim(o['id'])
            return self.mem.claims.revise(c['id'], support=[ev], status='active')
        if replace:
            self._carry_over(node, [o['content']['refers'] for o in old if o['content']['refers'] != node])
            for o in old:
                self.mem.claims.revise(o['id'], counter=[ev], status='superseded')
                self.mem.graph.unlink_claim(o['id'])
        c = self.mem.claims.add('denotes', {'symbol': symbol, 'refers': node, 'lesson': lesson}, [ev], 'user_said', self.scope)
        g = self.mem.graph
        g.link(g.node(f'sym:{symbol}', 'symbol'), 'denotes', node, c['id'])
        g.save()
        self._from_source(f'sym:{symbol}', c)
        return c

    def name_phrase(self, words, node, lesson=None):
        """The person says a phrase of several words while pointing or demonstrating: each word is bound as a symbol, and
        the order in which they were said is kept as one more user_said claim (used only with structure='order')."""
        for w in words:
            self.bind(w, node, lesson)
        ev = self.mem.events.append('phrase', lesson=lesson, words=list(words), node=node)
        same = [c for c in self.mem.claims.claims('phrase') if c['content']['refers'] == node and c['content']['words'] == list(words)
                and self._in_scope(c)]
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

    def _carry_over(self, node, old_nodes):
        """The person teaches a name again on a new concept. What the person said before about that name (which objects
        were pointed at, the answers to contrast questions) still says what the name means: criteria of the new concept
        that contradict it are dropped."""
        if self.mode == 'RAW' or not old_nodes:
            return
        new = next((c for c in self.mem.claims.claims('selects') if c['content']['concept'] == node and self._in_scope(c)), None)
        if not new:
            return
        olds = [c for c in self.mem.claims.claims('selects', usable=False) if c['content']['concept'] in old_nodes and self._in_scope(c)]
        evidence, used = [], []
        for c in olds:
            for eid in c['support']:
                e = self.mem.events.get(eid)
                if not e:
                    continue
                if e['kind'] == 'contrast' and e.get('feats') is not None:
                    evidence.append((frozenset(e['feats']), bool(e['answer'])))
                    used.append(eid)
                elif e['kind'] == 'point':
                    evidence += [(frozenset(f), True) for f in (e.get('feats') or {}).values()]
                    used.append(eid)
        if not evidence:
            return
        fits = lambda h: all((set(h) <= f) == y for f, y in evidence)
        content = new['content']
        alts = [a for a in content.get('alternatives', []) if fits(a)]
        atoms = content['atoms']
        if not fits(atoms) and alts:
            atoms = min(alts, key=lambda h: (len(h), sorted(h)))
            alts = [a for a in alts if a != atoms]
        if atoms != content['atoms'] or len(alts) != len(content.get('alternatives', [])):
            self.mem.claims.revise(new['id'], content={**content, 'atoms': sorted(atoms), 'alternatives': alts},
                                   support=list(dict.fromkeys(used)), status='active')
            self.counts['carried_over'] += 1

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
        fresh = lambda n: (defs[n].get('claim') or {}).get('status', 'active') == 'active'
        pairs = [(s, a) for s in sel_n for a in act_n]
        if any(fresh(s) and fresh(a) for s, a in pairs):     # a reading the person contradicted yields to one never contradicted
            pairs = [(s, a) for s, a in pairs if fresh(s) and fresh(a)]
        scored = sorted(((key(s, a), s, a) for s, a in pairs), reverse=True)
        unknown = [w for w, ns in nodes.items() if not ns]
        if not scored:
            return None, None, unknown
        feats = self.feats()
        def does(s, a):                                    # what a reading would bring about here: which objects, what they end as
            e = defs[a]['claim']['content']                # ('lost' says only where the demonstrated object happened to come from)
            return (tuple(self.extension(defs[s]['claim']['content']['atoms'], feats)),
                    json.dumps([sorted(e.get('gained') or []), sorted(e.get('made_rel', e.get('made')) or []),
                                sorted(json.dumps(r) for r in e['template'])]))   # roles in any order: where things go
        top = [(s, a) for k, s, a in scored if k == scored[0][0]]
        self._tied = None
        if len({does(s, a) for s, a in top}) > 1:          # a tie is ambiguous only if the readings would end differently
            self._tied = {'readings': top, 'defs': defs, 'nodes': nodes, 'does': does}
            return None, None, unknown
        # the same objects and the same change: carry it out the way most recently shown (an older way may be retired)
        order = lambda n: int(''.join(ch for ch in (defs[n]['claim'].get('id') or 'c0') if ch.isdigit()) or 0)
        s, a = max(top, key=lambda r: (order(r[1]), order(r[0])))
        return defs[s], defs[a], unknown

    def _deciding_word_missing(self, words, *chosen):
        """Does the reading leave unsaid a word of its phrase that told its concept apart from others sharing the rest of
        the phrase (bound to fewer of them than the said words are), while an unheard word stands in the command?"""
        said = set(words)
        for d in chosen:
            node = (d['claim']['content'].get('concept') or d['claim']['content'].get('action'))
            kind = d['claim']['kind']
            same_kind = lambda ns: {n for n in ns if (self._definition(n) or {}).get('kind') == kind}
            phrases = self._phrases(node)
            if any(all(w in said for w in ph) for ph in phrases):
                continue                                   # one of its phrases was said whole
            for ph in phrases:
                rest = [w for w in ph if w in said]
                gone = [w for w in ph if w not in said]
                if not rest or not gone:
                    continue
                shared = set.intersection(*[same_kind(self._nodes(w)) for w in rest])
                if any(same_kind(self._nodes(w)) < shared for w in gone):
                    return True
        return False

    def _ask_between(self, task):
        """With the person there: tied readings that pick different objects are told apart by a contrast question about
        an object some of them pick and others do not. The word links that sent the command to the readings the person
        ruled out are superseded on those readings (they stay on the reading that was meant)."""
        t = self._tied
        if not t or self.person is None or self.passive:
            return None
        feats = self.feats()
        ext = lambda r: frozenset(t['does'](*r)[0])
        live = list(t['readings'])
        for _ in range(QUESTION_BUDGET):
            if len({t['does'](*r) for r in live}) <= 1:
                break
            exts = [ext(r) for r in live]
            split = sorted(frozenset.union(*exts) - frozenset.intersection(*exts))
            if not split:
                break                                      # same objects, different action: a question about objects cannot help
            o = min(split, key=lambda x: (abs(sum(x in e for e in exts) - len(exts) / 2), x))
            ans = self.person.contrast(o)
            self.counts['contrast'] += 1
            ev = self.mem.events.append('contrast', lesson=task, object=o, answer=ans, feats=sorted(feats[o]), why='between readings')
            live = [r for r, e in zip(live, exts) if (o in e) == ans]
        if not live or len({t['does'](*r) for r in live}) > 1:
            return None
        win_s, win_a = live[0]
        for s, a in t['readings']:
            if s == win_s:
                continue
            for w, ns in t['nodes'].items():               # a word that pointed at both: it does not mean the ruled-out one
                if s in ns and win_s in ns:
                    for c in self.mem.claims.claims('denotes'):
                        if c['content']['symbol'] == w and c['content']['refers'] == s:
                            self.mem.claims.revise(c['id'], counter=[ev], status='superseded')
                            self.mem.graph.unlink_claim(c['id'])
        self.mem.graph.save()
        self.counts['asked_between'] += 1
        return t['defs'][win_s], t['defs'][win_a]

    HELD = ('unresolved', 'ambiguous generalization', 'needs recheck', 'unknown word in place of a deciding word')

    def obey(self, symbols, task=None):
        """A command made of symbols or words (in any order). Never acts on an unresolved reading alone; a command held
        with nobody there is kept as an unfinished goal, to be asked about when the person is back."""
        res = self._obey(symbols, task)
        if self.person is None and not res.get('ok') and not res.get('acted') and res.get('why') in self.HELD:
            items = [x for x in self.pending() if x['words'] != list(symbols)]
            self._set_pending(items + [{'words': list(symbols), 'why': res['why'], 'task': task, 'event': res.get('event')}])
        elif res.get('ok'):
            self.drop_pending(symbols)
        return res

    def pending(self):
        p = self.dir / 'pending.json'
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else []

    def _set_pending(self, items):
        (self.dir / 'pending.json').write_text(json.dumps(items, ensure_ascii=False), encoding='utf-8')

    def drop_pending(self, symbols):
        items = self.pending()
        rest = [x for x in items if x['words'] != list(symbols)]
        if len(rest) != len(items):
            self._set_pending(rest)

    def _obey(self, symbols, task=None):
        """A command made of symbols or words (in any order). Never acts on an unresolved reading alone."""
        ev = self.mem.events.append('say', task=task, symbols=list(symbols))
        sel_d, act_d, unknown = self.resolve(symbols)
        if sel_d is None and getattr(self, '_tied', None):
            settled = self._ask_between(task)
            if settled:
                sel_d, act_d = settled
        if sel_d is None:
            self.counts['held_unresolved'] += 1
            return {'ok': False, 'why': 'unresolved', 'unknown': unknown, 'event': ev}
        sels, acts = [sel_d], [act_d]
        if unknown and self._deciding_word_missing(symbols, sel_d, act_d):
            self.counts['held_substituted'] += 1           # an unheard word stands where the deciding word should be
            return {'ok': False, 'why': 'unknown word in place of a deciding word', 'unknown': unknown, 'event': ev}
        if any((d.get('claim') or {}).get('status') == 'needs_recheck' for d in (sel_d, act_d)):
            self.counts['held_recheck'] += 1                   # contradicted by the person: to be taught again first
            return {'ok': False, 'why': 'needs recheck', 'event': ev, 'used': [sel_d['via'], act_d['via']]}
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
        now = self.feats()
        blocked = [(o, e) for o, e in failed if self._made_exists(act, now, o)]
        if blocked:                                        # what it would make is already there: a block, not a counter-example
            self.counts['blocked'] += len(blocked)
            failed = [x for x in failed if x not in blocked]
        if failed and acts[0]['claim'].get('id'):
            self.mem.counter(acts[0]['claim']['id'], failed[0][1])       # the tool did not do what the claim said
            self.counts['effect_counterexamples'] += 1
            found = self._experiment(acts[0]['claim'], failed[0][0], task) if self.experiment else None
            if found:                                                     # another way does it: carry on with that
                more, failed = self.apply(sel, found['content'], lesson=task)
                acted += more
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
            for d in self.mem.claims.claims('denotes'):            # the person's own answers fixed it: its names stand again
                if d['content']['refers'] == content.get('concept') and d['status'] == 'needs_recheck' and self._in_scope(d):
                    self.mem.claims.revise(d['id'], status='active')
        return new

    def reply(self, ok, used=(), reason=None):
        """The person's verdict on what was done (CONFIRM). A 'wrong' is a counter-example to the claims that were used:
        the selection if the person says the objects were wrong, the action if the result was, both if not said. Those
        claims (and the names that depend on them) need re-checking before ATANOR acts on them again."""
        ev = self.mem.events.append('confirm', answer=ok, reason=reason, used=list(used))
        if not ok:
            kinds = {'cards': ('selects',), 'result': ('effect',)}.get(reason, ('selects', 'effect'))
            for cid in used:
                c = self.mem.claims.current(cid)
                if c and c['kind'] in kinds and c['status'] in ('active', 'needs_recheck'):
                    self.mem.counter(cid, ev)
                    self.counts['person_counterexamples'] += 1
        return ev
