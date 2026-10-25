"""v18: role ambiguity is ambiguity. A word whose experience says both 'it goes with one change' (most of its uses, at
least 3, with one change) and 'it names objects' (its meaning carries a value) is read as an object word since v9; when
the value it would add to the selection is brought by no other word of the command, the reading depends on which role
it has, and the evidence does not say. That reading is marked ambiguous: with the person it is checked (and the
confirmed use is the contrast that heals the word), alone it is held. No new structure: the existing ambiguity path."""
import pathlib, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""        change_words = {w for u in units if self._share(u, pids)[1] >= DECISIVE and u not in values for w in u.split(' ')}
        weak_change =""", """        def value_atoms_of(t):
            if t in values:
                return {repr(a) for o, (at, vs) in view.items() if t in vs for a in at if a[0] == 'U' and a[3] == t}
            if self.names_value(t):
                return {a for a in self.meaning.get(t, ()) if a.startswith("('U'") and a.split(',')[3].strip(" )'") not in ('0', '1', '-')}
            return set()
        for t in set(toks):
            if t in values or t in view or t == dest or t in self.neutral or not self.names_value(t):
                continue
            pc = self.pattern_of.get(t)
            n = sum(pc.values()) if pc else 0
            if n < 3 or (pc.most_common(1)[0][1] + 0.1) / (n + 0.1 * len(pids)) < DECISIVE:
                continue
            others = set().union(*[value_atoms_of(u) for u in set(toks) if u != t and u != dest]) if len(toks) > 1 else set()
            if value_atoms_of(t) - others:
                ambiguous = True                            # change word or object word? the reading depends on it
        change_words = {w for u in units if self._share(u, pids)[1] >= DECISIVE and u not in values for w in u.split(' ')}
        weak_change =""")
p.write_bytes(s.encode('utf-8'))
print('v18 ok')
