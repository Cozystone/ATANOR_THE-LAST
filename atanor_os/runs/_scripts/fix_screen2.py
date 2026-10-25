"""v7: case-mode guard; a pointing is applied to the current reading at once; words learn what the second object
they were pointed to has in common (a D-meaning), so a value synonym can name it."""
import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding='utf-8')
def rep(a, b):
    global s
    assert a in s, a[:70]; s = s.replace(a, b, 1)
rep("""            keys = {a.split(',')[2] for a in named}
            cons = {a for a in cons if a.split(',')[2] not in keys} | named""",
    """            keys = {a.split(',')[2] for a in named}
            cons = {a for a in cons if not (a.startswith("('U'") and a.split(',')[2] in keys)} | named""")
# D-meaning: learned from uses whose second object exists in the view
rep("""        self.pointed = Counter()                # word -> uses in which the person pointed at the objects""",
    """        self.pointed = Counter()                # word -> uses in which the person pointed at the objects
        self.dmeaning = {}                      # word -> atoms every second object it was used with had in common""")
rep("""        for pair in self.pairs(toks, dest, values):
            if pid is not None:
                self.pattern_of[pair][pid] += 1""", """        for pair in self.pairs(toks, dest, values):
            if pid is not None:
                self.pattern_of[pair][pid] += 1
        if dest in view:                                    # the second object exists: words may describe it
            dcur = {repr(a) for a in view[dest][0]}
            for w in set(toks):
                if w in self.neutral or w in view or w == dest:
                    continue
                self.dmeaning[w] = dcur if w not in self.dmeaning else (self.dmeaning[w] & dcur)""")
rep("""                'pointed': dict(self.pointed), 'defined': dict(self.defined)}""",
    """                'pointed': dict(self.pointed), 'defined': dict(self.defined), 'dmeaning': {w: sorted(m) for w, m in self.dmeaning.items()}}""")
rep("""        x.pointed, x.defined = Counter(d.get('pointed', {})), Counter(d.get('defined', {}))
        return x""", """        x.pointed, x.defined = Counter(d.get('pointed', {})), Counter(d.get('defined', {}))
        x.dmeaning = {w: set(m) for w, m in d.get('dmeaning', {}).items()}
        return x""")
rep("""        cands = [o for o, (at, vs) in view.items() if o not in r['selected'] and vs & set(toks)
                 and any(a[0] == 'U' and a[2] == 'a0' and a[3] == meta.get('D_kind') for a in at)]
        return {**r, 'dest': cands[0]} if len(cands) == 1 else r""",
    """        kind_ok = lambda at: any(a[0] == 'U' and a[2] == 'a0' and a[3] == meta.get('D_kind') for a in at)
        cands = [o for o, (at, vs) in view.items() if o not in r['selected'] and vs & set(toks) and kind_ok(at)]
        if len(cands) != 1:                                   # no token names it: words that describe the second object
            cons = set()
            for t in toks:
                if t not in view and t not in self.lex.neutral and self.lex.strong(t) and self.lex.dmeaning.get(t):
                    cons |= self.lex.dmeaning[t]
            if cons:
                cands = [o for o, (at, vs) in view.items() if o not in r['selected'] and kind_ok(at) and cons <= {repr(a) for a in at}]
        return {**r, 'dest': cands[0]} if len(cands) == 1 else r""")
# a pointing is applied to the reading within the loop
rep("""            r = self._resolve_dest(self.lex.interpret(toks, view, True), toks, view)
            if r['unknown'] and self.user is not None:
                if not self.patterns or '<shape>' in r['unknown']:""", """            r = self._resolve_dest(self.lex.interpret(toks, view, True), toks, view)
            if pointed is not None and r['pid'] in self.patterns:
                r = {**r, 'selected': [o for o in pointed['objects'] if o in view], 'dest': pointed['dest'] or r['dest'],
                     'contradiction': False, 'weak_selection': False, 'support': True}
            if r['unknown'] and self.user is not None:
                if not self.patterns or '<shape>' in r['unknown']:""")
p.write_bytes(s.encode('utf-8')); print('fixed', p)
