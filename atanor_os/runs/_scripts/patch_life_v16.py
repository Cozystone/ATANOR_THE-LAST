"""v16: selections compose. When a command brings two alternative values for one attribute (a contradiction for a
plain intersection), the core looks at the words between the tokens that brought them. A word it has seen, in confirmed
uses, standing between alternatives whose objects together were exactly the selection (each alternative contributing)
is learned as joining them; with enough such evidence (>= 2 uses, >= 80% of its chances) the selection is the union of
the alternatives under the shared constraints. Nothing names the joining word: it is learned like a destination marker.
When a union explains a confirmed selection, each value word learns its meaning from its own part of the objects."""
import pathlib, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""        self.defined = Counter()                # word -> explanations by the person""",
    """        self.defined = Counter()                # word -> explanations by the person
        self.join = Counter()                   # word -> confirmed uses where it stood between alternatives that were all selected
        self.join_n = Counter()                 # word -> confirmed uses where it stood between alternatives""")
rep("""    def learn(self, toks, view, pid, selected, dest):
        self.note_values(view)""", """    def _alternatives(self, toks, view, dest):
        \"\"\"Value-naming atoms brought by the tokens, by attribute: {key: {atom: first token index}}, only for
        attributes with more than one alternative.\"\"\"
        values = set().union(*[vs for _, vs in view.values()]) if view else set()
        by_key = defaultdict(dict)
        for i, t in enumerate(toks):
            if t == dest or t in view:
                continue
            if t in values:
                got = {repr(a) for o, (at, vs) in view.items() if t in vs for a in at if a[0] == 'U' and a[3] == t}
            elif self.strong(t) and self.meaning.get(t):
                got = {a for a in self.meaning[t] if a.startswith("('U'") and a.split(',')[3].strip(" )'") not in ('0', '1', '-')}
            else:
                continue
            for a in got:
                by_key[a.split(',')[2]].setdefault(a, i)
        return {k: v for k, v in by_key.items() if len(v) > 1}

    def joined(self, word):
        return self.join[word] >= 2 and self.join[word] / max(1, self.join_n[word]) >= 0.8

    def _between(self, toks, alts):
        idx = sorted(alts.values())
        bringers = set(idx)
        return {toks[i] for i in range(idx[0] + 1, idx[-1]) if i not in bringers}

    def learn(self, toks, view, pid, selected, dest):
        self.note_values(view)
        parts = {}                                          # alternative atom -> the selected objects carrying it
        alts = self._alternatives(toks, view, dest)
        if len(alts) == 1 and selected:
            (key, am), = alts.items()
            parts = {a: [o for o in selected if o in view and a in {repr(x) for x in view[o][0]}] for a in am}
            union = all(parts.values()) and set().union(*map(set, parts.values())) == {o for o in selected if o in view}
            for w in self._between(toks, am):
                self.join_n[w] += 1
                self.join[w] += int(union)
            if not union:
                parts = {}
            else:
                parts = {i: parts[a] for a, i in am.items()}     # token index -> its own objects""")
rep("""            if w not in self.neutral:
                self._add_use(w, cur)""",
    """            if w not in self.neutral:
                own = [parts[i] for i, t in enumerate(toks) if t == w and i in parts]
                if own:                                     # a value word in a union learns from its own part
                    sub = [view[o][0] for o in own[0] if o in view]
                    self._add_use(w, {repr(a) for a in frozenset.intersection(*sub)} if sub else cur)
                else:
                    self._add_use(w, cur)""")
rep("""        contradiction = any(len(v) > 1 for v in by_key.values())
        value_named""", """        contradiction = any(len(v) > 1 for v in by_key.values())
        union_sel = None
        if contradiction:
            alts = self._alternatives(toks, view, dest)
            if len(alts) == 1 and any(self.joined(w) for w in self._between(toks, next(iter(alts.values())))):
                key = next(iter(alts))
                base = {a for a in cons if not (a.startswith("('U'") and a.split(',')[2] == key)}
                union_sel = sorted(o for o, (at, _) in view.items()
                                   if base <= {repr(a) for a in at} and any(x in {repr(a) for a in at} for x in alts[key]))
                contradiction = False                       # a learned joining word: the alternatives are all wanted
        value_named""")
rep("""            sel = [] if contradiction else sorted(o for o, (at, _) in view.items() if cons <= {repr(a) for a in at})""",
    """            sel = [] if contradiction else union_sel if union_sel is not None else sorted(o for o, (at, _) in view.items() if cons <= {repr(a) for a in at})""")
rep("""                'value_atoms': dict(self.value_atoms), 'duses':""", """                'value_atoms': dict(self.value_atoms), 'join': dict(self.join), 'join_n': dict(self.join_n), 'duses':""")
rep("""        x.d_n = Counter(d.get('d_n', {}))""", """        x.d_n = Counter(d.get('d_n', {}))
        x.join, x.join_n = Counter(d.get('join', {})), Counter(d.get('join_n', {}))""")
p.write_bytes(s.encode('utf-8'))
print('v16 ok')

# part 2: value words in a union count as naming their own part; a reading that ignores named values is weak
s = p.read_text(encoding='utf-8')
rep("""        for w in set(toks):
            if w in values:
                self.value_rule[1] += 1
                self.value_rule[0] += int(bool(selected) and set(selected) <= {o for o, (_, vs) in view.items() if w in vs})""",
    """        for i, w in enumerate(toks):
            if w in values and w not in toks[:i]:
                carriers = {o for o, (_, vs) in view.items() if w in vs}
                own = parts.get(i)
                self.value_rule[1] += 1
                self.value_rule[0] += int(bool(selected) and (set(own or selected) <= carriers))""")
rep("""        value_named = any(a.startswith("('U'") and a.split(',')[3].strip(" )'") not in ('0', '1', '-') for a in cons)""",
    """        value_named = any(a.startswith("('U'") and a.split(',')[3].strip(" )'") not in ('0', '1', '-') for a in cons)
        if union_sel is None and not value_named and any(t in values and t != dest for t in toks) and not any(t in view and t != dest for t in toks):
            weak_selection = True                               # values were named but nothing in the reading uses them""")
p.write_bytes(s.encode('utf-8'))
print('v16 part 2 ok')

# part 3: all values named in the command replace the word meanings on their attribute together (two values on one
# attribute are then visible as alternatives instead of the later one silently replacing the earlier one)
s = p.read_text(encoding='utf-8')
rep("""        if opp >= 2 and hits / opp >= 0.8:
            for t in toks:
                if t != dest and t in values:
                    named = {repr(a) for o, (at, vs) in view.items() if t in vs for a in at if a[0] == 'U' and a[3] == t}
                    keys = {a.split(',')[2] for a in named}
                    cons = {a for a in cons if not (a.startswith("('U'") and a.split(',')[2] in keys)} | named""",
    """        if opp >= 2 and hits / opp >= 0.8:
            named = {repr(a) for t in toks if t != dest and t in values
                     for o, (at, vs) in view.items() if t in vs for a in at if a[0] == 'U' and a[3] == t}
            keys = {a.split(',')[2] for a in named}
            cons = {a for a in cons if not (a.startswith("('U'") and a.split(',')[2] in keys)} | named""")
p.write_bytes(s.encode('utf-8'))
print('v16 part 3 ok')

# part 4: a strong word that names a value is a named value too: the literal values of the command do not erase it
s = p.read_text(encoding='utf-8')
rep("""            keys = {a.split(',')[2] for a in named}
            cons = {a for a in cons if not (a.startswith("('U'") and a.split(',')[2] in keys)} | named
        by_key = defaultdict(set)""",
    """            keys = {a.split(',')[2] for a in named}
            by_object_words = {a for t in toks if t != dest and t not in values and t not in self.neutral and self.names_value(t)
                               for a in self.meaning.get(t, ()) if a.startswith("('U'") and a.split(',')[3].strip(" )'") not in ('0', '1', '-')}
            cons = {a for a in cons if not (a.startswith("('U'") and a.split(',')[2] in keys) or a in by_object_words} | named
        by_key = defaultdict(set)""")
p.write_bytes(s.encode('utf-8'))
print('v16 part 4 ok')

# part 5: a pair of words is never a change unit when one of them names objects (v9's rule, applied to pairs too)
s = p.read_text(encoding='utf-8')
rep("""            if pair and share >= DECISIVE and dest not in (toks[i], toks[i + 1]) and toks[i] not in values and toks[i + 1] not in values and toks[i] not in view and toks[i + 1] not in view:""",
    """            if pair and share >= DECISIVE and dest not in (toks[i], toks[i + 1]) and toks[i] not in values and toks[i + 1] not in values and toks[i] not in view and toks[i + 1] not in view \
                    and not self.names_value(toks[i]) and not self.names_value(toks[i + 1]):""")
p.write_bytes(s.encode('utf-8'))
print('v16 part 5 ok')

# part 6: a use where some alternative is carried by no object at all says nothing about joining
s = p.read_text(encoding='utf-8')
rep("""        if len(alts) == 1 and selected:
            (key, am), = alts.items()""", """        insel = [{repr(x) for x in view[o][0]} for o in selected if o in view]
        akey = next(iter(alts)) if len(alts) == 1 else None
        shared = {a for a in set.intersection(*insel) if a.split(',')[2:3] != [akey]} if insel and akey else set()
        carried = lambda a: any(shared <= {repr(x) for x in at} and a in {repr(x) for x in at} for at, _ in view.values())
        if len(alts) == 1 and insel and all(carried(a) for a in alts[akey]):     # each alternative has objects like the selected ones
            (key, am), = alts.items()""")
p.write_bytes(s.encode('utf-8'))
print('v16 part 6 ok')
