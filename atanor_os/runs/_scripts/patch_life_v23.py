"""v23: a mixed selection teaches nothing about words whose part in it is unknown. When the selected objects carry
different values on one naming attribute, a word with no identified part and no established meaning yet (fewer than
3 uses; it is not a value of the command, it names no value of its own) gets no meaning use from this command: the selection's common
atoms would only tell it 'nothing in particular', which for a word that is about to name one of the parts is wrong
(composed evaluation seed 37 of v22: 'spreadsheets' first heard in mixed selections never formed a meaning). Established
words still learn from such uses, so a meaning can still follow a use that really changed."""
import pathlib, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""                    elif len(mine) < len(sel_in):
                        own = [mine]                        # a mixed selection: the word learns from the part it names""",
    """                    elif len(mine) < len(sel_in):
                        own = [mine]                        # a mixed selection: the word learns from the part it names
                if not own and mixed and w not in values and len(self.uses.get(w, [])) < 3:
                    continue                                # a new word's part in a mixed selection is unknown: no evidence yet""")
rep("""        bringers = {i for k, am in alts.items() for a, i in am.items() if absent(k, a)}""",
    """        bringers = {i for k, am in alts.items() for a, i in am.items() if absent(k, a)}
        sel_atoms = [{repr(x) for x in view[o][0]} for o in selected if o in view]
        by_attr = defaultdict(set)
        for sa in sel_atoms:
            for a in sa:
                if self.valued(a):
                    by_attr[a.split(',')[2]].add(a)
        mixed = any(len(v) > 1 for v in by_attr.values())   # the selected objects differ on a naming attribute""")
p.write_bytes(s.encode('utf-8'))
print('v23 ok')

# part 2: mutual exclusivity - the part of a mixed selection no read value explains belongs to the one new word
s = p.read_text(encoding='utf-8')
rep("""                if not own and mixed and w not in values and len(self.uses.get(w, [])) < 3:
                    continue                                # a new word's part in a mixed selection is unknown: no evidence yet""",
    """                if not own and mixed and w not in values and len(self.uses.get(w, [])) < 3:
                    if w == residual_word and residual:
                        own = [residual]                    # the part nothing read explains belongs to the one new word
                    else:
                        continue                            # a new word's part in a mixed selection is unknown: no evidence yet""")
rep("""        mixed = any(len(v) > 1 for v in by_attr.values())   # the selected objects differ on a naming attribute""",
    """        mixed = any(len(v) > 1 for v in by_attr.values())   # the selected objects differ on a naming attribute
        residual, residual_word = [], None
        if mixed:
            vals_here = set().union(*[vs for _, vs in view.values()])
            named = set()
            for t in toks:
                if t == dest or t in view:
                    continue
                if t in vals_here:
                    named |= {repr(a) for o, (at, vs) in view.items() if t in vs for a in at if a[0] == 'U' and a[3] == t}
                elif self.strong(t):
                    named |= self.naming_atoms(t)
            residual = [o for o in selected if o in view and not named & {repr(a) for a in view[o][0]}]
            new = {t for t in toks if t != dest and t not in view and t not in vals_here and t not in self.neutral
                   and len(self.uses.get(t, [])) < 3 and not self.join_n[t]}   # a word seen standing between alternatives is not it
            sub = [{repr(a) for a in view[o][0]} for o in residual]
            if len(new) == 1 and residual and len(residual) < len([o for o in selected if o in view]) and any(self.valued(a) for a in set.intersection(*sub)):
                residual_word = next(iter(new))""")
p.write_bytes(s.encode('utf-8'))
print('v23 part 2 ok')
