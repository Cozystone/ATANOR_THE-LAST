"""v24: a reading must not drop a word that has so far only ever named one value, even before it is strong. v19's
check ('a word that names values restricts nothing in this reading -> unsupported') looked only at strong words with a
long value history; a word heard twice, both times naming log files, was left out of 'the comma separated files and
logs', and the reversible move went ahead alone (composed evaluation seed 40 of v23). Now a word that is not yet strong
counts too when it has been used at least twice and every one of its uses named the same value (and it is not a word
that mostly goes with one change)."""
import pathlib, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""                    va = self.value_history(t) if self.strong(t) and len(self.uses.get(t, [])) >= 3 and not names_change else set()""",
    """                    va = self.value_history(t) if self.strong(t) and len(self.uses.get(t, [])) >= 3 and not names_change else set()
                    if not va and not self.strong(t) and not names_change:
                        ds = self.disc_uses.get(t, [])
                        if len(ds) >= 2 and all(d and d == ds[0] for d in ds):
                            va = set(ds[0])                 # a young word that has only ever named this value""")
p.write_bytes(s.encode('utf-8'))
print('v24 ok')

# part 2: credit - an atom that another word of the command already names is not credited to this word
s = p.read_text(encoding='utf-8')
rep("""                    self._add_use(w, part, disc=self._discriminating(part, own[0], view, pid))
                else:
                    self._add_use(w, cur, disc=self._discriminating(cur, selected, view, pid))""",
    """                    self._add_use(w, part, disc=self._discriminating(part, own[0], view, pid) - credited_elsewhere(w))
                else:
                    self._add_use(w, cur, disc=self._discriminating(cur, selected, view, pid) - credited_elsewhere(w))""")
rep("""        bringers = {i for k, am in alts.items() for a, i in am.items() if absent(k, a)}""",
    """        bringers = {i for k, am in alts.items() for a, i in am.items() if absent(k, a)}
        vals0 = set().union(*[vs for _, vs in view.values()]) if view else set()
        named_by = {}
        for t in set(toks):
            if t == dest or t in view:
                continue
            if t in vals0:
                named_by[t] = {repr(a) for o, (at, vs) in view.items() if t in vs for a in at if a[0] == 'U' and a[3] == t}
            elif self.strong(t) and self.names_value(t):
                named_by[t] = self.naming_atoms(t)
        def credited_elsewhere(w):                          # what the other words of this command already name
            return set().union(*[a for t, a in named_by.items() if t != w]) if named_by else set()""")
p.write_bytes(s.encode('utf-8'))
print('v24 part 2 ok')
