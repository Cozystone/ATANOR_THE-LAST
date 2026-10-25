"""v9: after the wrong actions of file seed 5 and screen seed 4.
1. A unit is decisive about the change only with at least three observations; a word whose strong meaning names
   a value is an object word and never a change word.
2. An irreversible change needs a selection that rests on literal naming (a value token or an object id) or on a
   strong meaning that names a value; otherwise: point with the person, hold alone.
3. An explanation may name a value seen before even if no such object is visible now.
4. A second object found through words' learned meanings is a weak reading: never through change words; with the
   person it is pointed at, alone it is held.
5. Encoding a shown change prefers a copy from the pointed second object over a coincidental copy from the object.
6. The planner's focus includes every object carrying a value the goal names."""
import pathlib, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')


def rep(a, b, count=1):
    global s
    assert s.count(a) >= count, a[:70]
    s = s.replace(a, b, count)


# ---- 1. decisive needs evidence; object words are not change words
rep("""    def _share(self, unit, pids):
        pc = self.pattern_of.get(unit)
        if not pc:
            return None, 0.0
        n = sum(pc.values())
        top, c = pc.most_common(1)[0]
        return top, (c + 0.1) / (n + 0.1 * len(pids))""", """    def _share(self, unit, pids):
        pc = self.pattern_of.get(unit)
        if not pc:
            return None, 0.0
        n = sum(pc.values())
        top, c = pc.most_common(1)[0]
        if n < 3 or self.names_value(unit):
            return top, 0.0                                 # too little evidence, or an object word: not decisive
        return top, (c + 0.1) / (n + 0.1 * len(pids))

    def names_value(self, word):
        \"\"\"A strong word whose meaning contains a value-bearing atom names objects, not a change.\"\"\"
        return self.strong(word) and any(a.startswith("('U'") and a.split(',')[3].strip(" )'") not in ('0', '1', '-') for a in self.meaning.get(word, ()))""")
# ---- 3. values seen before stay nameable
rep("""        self.dmeaning = {}                      # word -> atoms every second object it was used with had in common""",
    """        self.dmeaning = {}                      # word -> atoms every second object it was used with had in common
        self.value_atoms = {}                   # value -> the atom (repr) that carried it, from every view seen""")
rep("""    def learn(self, toks, view, pid, selected, dest):""", """    def note_values(self, view):
        for o, (at, vs) in view.items():
            for a in at:
                if a[0] == 'U' and a[3] in vs:
                    self.value_atoms[a[3]] = repr(a)

    def learn(self, toks, view, pid, selected, dest):
        self.note_values(view)""")
rep("""                'pointed': dict(self.pointed), 'defined': dict(self.defined), 'dmeaning': {w: sorted(m) for w, m in self.dmeaning.items()}}""",
    """                'pointed': dict(self.pointed), 'defined': dict(self.defined), 'dmeaning': {w: sorted(m) for w, m in self.dmeaning.items()},
                'value_atoms': dict(self.value_atoms)}""")
rep("""        x.dmeaning = {w: set(m) for w, m in d.get('dmeaning', {}).items()}
        return x""", """        x.dmeaning = {w: set(m) for w, m in d.get('dmeaning', {}).items()}
        x.value_atoms = dict(d.get('value_atoms', {}))
        return x""")
rep("""        for t in ptoks:                                       # a word of the explanation that names an observed value
            if t in values:
                cons = {a for a in cons if not a.startswith("('U', 0, 'a2'")}
                cons |= {repr(a) for o, (at, v) in view.items() if v == t for a in at if a[0] == 'U' and a[2] == 'a2'}""",
    """        self.lex.note_values(view)
        for t in ptoks:                                       # a word of the explanation that names a value (seen now or before)
            atom = self.lex.value_atoms.get(t)
            if t in values:
                named = {repr(a) for o, (at, vs) in view.items() if t in vs for a in at if a[0] == 'U' and a[3] == t}
            elif atom:
                named = {atom}
            else:
                continue
            keys = {a.split(',')[2] for a in named}
            cons = {a for a in cons if not (a.startswith("('U'") and a.split(',')[2] in keys)} | named""")
# ---- 2. irreversible changes need literally supported selections
rep("""        cons, weak_selection, support = set(), False, any(t in values and t != dest for t in toks)""",
    """        cons, weak_selection, support = set(), False, any(t in values and t != dest for t in toks)
        literal = support or any(t in view and t != dest for t in toks)""")
rep("""            if self.strong(t):
                if self.meaning.get(t):
                    cons |= self.meaning[t]
                    support = True""", """            if self.strong(t):
                if self.meaning.get(t):
                    cons |= self.meaning[t]
                    support = True
                    literal = literal or self.names_value(t)""")
rep("""                'decisive': decisive, 'weak_change': weak_change, 'weak_selection': weak_selection, 'support': support}""",
    """                'decisive': decisive, 'weak_change': weak_change, 'weak_selection': weak_selection, 'support': support,
                'literal': literal}""")
rep("""            weak = r.get('weak_change') or r.get('weak_selection')
            if self.user is None and ((weak and self._irreversible(r['pid'])) or not r.get('support')):""",
    """            weak = r.get('weak_change') or r.get('weak_selection') or r.get('dest_by_meaning')
            if r['pid'] in self.patterns and self._irreversible(r['pid']) and not r.get('literal') and pointed is None:
                if self.user is None:
                    self.counts['refused_weak'] += 1
                    self.log(event='refuse_weak', why='irreversible without literal naming')
                    return None
                ans = self.user.point(command)
                self.counts['point'] += 1
                self.log(event='ask_point', why='irreversible without literal naming')
                self._learn_pointing(toks, view, ans)
                pointed = ans
                continue
            if self.user is None and ((weak and self._irreversible(r['pid'])) or not r.get('support')):""")
rep("""            if self.user is not None and (r.get('weak_selection') or not r.get('support')) and pointed is None:""",
    """            if self.user is not None and (r.get('weak_selection') or not r.get('support') or r.get('dest_by_meaning')) and pointed is None:""")
rep("""        if self.user is None:
            weak = r.get('weak_change') or r.get('weak_selection')
            if (weak and self._irreversible(r['pid'])) or not r.get('support', True):
                return False                                  # nobody to ask: no irreversible or unsupported guess""",
    """        if self.user is None:
            weak = r.get('weak_change') or r.get('weak_selection') or r.get('dest_by_meaning')
            if (weak and self._irreversible(r['pid'])) or not r.get('support', True) or r.get('dest_by_meaning'):
                return False                                  # nobody to ask: no irreversible, unsupported or meaning-guessed reading
            if self._irreversible(r['pid']) and not r.get('literal', True):
                return False""")
# ---- 4. second object through meanings: never change words, and a weak reading
rep("""        if len(cands) != 1:                                   # no token names it: words that describe the second object
            cons = set()
            for t in toks:
                if t not in view and t not in self.lex.neutral and self.lex.strong(t) and self.lex.dmeaning.get(t):
                    cons |= self.lex.dmeaning[t]
            if cons:
                cands = [o for o, (at, vs) in view.items() if o not in r['selected'] and kind_ok(at) and cons <= {repr(a) for a in at}]
        return {**r, 'dest': cands[0]} if len(cands) == 1 else r""",
    """        if len(cands) == 1:
            return {**r, 'dest': cands[0]}
        pids = sorted({q for c in self.lex.pattern_of.values() for q in c})
        change_words = {w for t in toks for w in t.split(' ') if self.lex._share(t, pids)[1] >= DECISIVE}
        cons = set()
        for t in toks:
            if t not in view and t not in self.lex.neutral and t not in change_words and self.lex.strong(t) and self.lex.dmeaning.get(t):
                cons |= self.lex.dmeaning[t]
        if cons:
            cands = [o for o, (at, vs) in view.items() if o not in r['selected'] and kind_ok(at) and cons <= {repr(a) for a in at}]
            if len(cands) == 1:
                return {**r, 'dest': cands[0], 'dest_by_meaning': True}   # a guess from meanings: ask or hold
        return r""")
# ---- 5. prefer the pointed second object for cross-attribute copies
rep("""            for rel, q in roles:
                if before[q].get(k) == value:
                    return f'={rel}.{k}'
            for rel, q in roles:
                for k2, v2 in before[q].items():
                    if v2 == value and k2 != 'kind':
                        return f'={rel}.{k2}'
            return value""", """            for rel, q in roles:
                if before[q].get(k) == value:
                    return f'={rel}.{k}'
            for rel, q in sorted(roles, key=lambda x: (x[0] != 'D', x[0])):   # the pointed second object first
                for k2, v2 in before[q].items():
                    if v2 == value and k2 != 'kind':
                        return f'={rel}.{k2}'
            return value""")
# ---- 6. focus includes objects that carry a value the goal names
rep("""    def _focus(self, goal):
        \"\"\"The objects a goal is about, with their ancestors: actions are considered over these only.\"\"\"
        out = set()
        for p in goal.universe:
            parts = p.split('/')
            out |= {'/'.join(parts[:i]) for i in range(1, len(parts) + 1)}
        return sorted(out)""", """    def _focus(self, goal):
        \"\"\"The objects a goal is about, with their ancestors, and every object carrying a value the goal names.\"\"\"
        out = set()
        for p in goal.universe:
            parts = p.split('/')
            out |= {'/'.join(parts[:i]) for i in range(1, len(parts) + 1)}
        wanted = {str(l.value) for l in goal.must}
        objs = self.home.existing()
        st = self.home.observe(objs)
        out |= {o for o in objs if names_of(self.body, st[o]) & wanted}
        return sorted(out)""")

# ---- ambiguity means disagreement between decisive units; having none is the weak-change case
rep("""            ambiguous = len(tops) != 1 or pid not in tops   # decisive units disagree, or none exists""",
    """            ambiguous = len(tops) > 1 or (len(tops) == 1 and pid not in tops)   # decisive units disagree""")
p.write_bytes(s.encode('utf-8'))
print('v9 ok')
