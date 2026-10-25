"""v17: evidence is only taken from uses it can be read from (found in the transfer evaluation, seed 19, of v16).
- Value rule: a named value counts as restricting the selection when every selected object carries one of the values
  the command named (by value tokens or object words), so a union the core does not yet read as a union is not
  counted against values.
- A word that brought one of several alternatives learns its meaning only when its own part of the selection is
  identifiable (the selection is exactly the union of the alternatives' parts); otherwise this use teaches it nothing.
- A reading that leaves named values unused is never acted on alone, reversible or not (with the person: point)."""
import pathlib, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""        parts = {}                                          # alternative atom -> the selected objects carrying it
        alts = self._alternatives(toks, view, dest)""", """        parts = {}                                          # alternative atom -> the selected objects carrying it
        alts = self._alternatives(toks, view, dest)
        bringers = {i for am in alts.values() for i in am.values()}
        alt_atoms = {a for am in alts.values() for a in am}""")
rep("""            if w not in self.neutral:
                own = [parts[i] for i, t in enumerate(toks) if t == w and i in parts]
                if own:""", """            if w not in self.neutral:
                own = [parts[i] for i, t in enumerate(toks) if t == w and i in parts]
                if not own and any(t == w and i in bringers for i, t in enumerate(toks)):
                    continue                                # its own part of the selection cannot be told apart: no evidence
                if own:""")
rep("""        for i, w in enumerate(toks):
            if w in values and w not in toks[:i]:
                carriers = {o for o, (_, vs) in view.items() if w in vs}
                own = parts.get(i)
                self.value_rule[1] += 1
                self.value_rule[0] += int(bool(selected) and (set(own or selected) <= carriers))""",
    """        named_vals = {w for w in toks if w in values and w != dest}
        any_carrier = {o for o, (at, vs) in view.items() if vs & named_vals or alt_atoms & {repr(a) for a in at}}
        for i, w in enumerate(toks):
            if w in values and w not in toks[:i]:
                carriers = {o for o, (_, vs) in view.items() if w in vs}
                own = parts.get(i)
                sel_in = {o for o in selected if o in view}
                self.value_rule[1] += 1
                self.value_rule[0] += int(bool(sel_in) and (set(own) <= carriers if own else sel_in <= any_carrier and bool(sel_in & carriers)))""")
rep("""        if union_sel is None and not value_named and any(t in values and t != dest for t in toks) and not any(t in view and t != dest for t in toks):
            weak_selection = True                               # values were named but nothing in the reading uses them""",
    """        ignores_named = union_sel is None and not value_named and any(t in values and t != dest for t in toks) and not any(t in view and t != dest for t in toks)
        if ignores_named:
            weak_selection = True                               # values were named but nothing in the reading uses them""")
rep("""                'decisive': decisive, 'weak_change': weak_change, 'weak_selection': weak_selection, 'support': support,""",
    """                'decisive': decisive, 'weak_change': weak_change, 'weak_selection': weak_selection, 'support': support and not ignores_named,""")
p.write_bytes(s.encode('utf-8'))
print('v17 ok')

# part 2: a use with words the core cannot read yet cannot show that a named value failed to restrict the selection
s = p.read_text(encoding='utf-8')
rep("""        for i, w in enumerate(toks):
            if w in values and w not in toks[:i]:
                carriers = {o for o, (_, vs) in view.items() if w in vs}
                own = parts.get(i)
                sel_in = {o for o in selected if o in view}
                self.value_rule[1] += 1
                self.value_rule[0] += int(bool(sel_in) and (set(own) <= carriers if own else sel_in <= any_carrier and bool(sel_in & carriers)))""",
    """        unread = any(t not in values and t != dest and t not in view and t not in self.neutral and not self.strong(t) for t in toks)
        for i, w in enumerate(toks):
            if w in values and w not in toks[:i]:
                carriers = {o for o, (_, vs) in view.items() if w in vs}
                own = parts.get(i)
                sel_in = {o for o in selected if o in view}
                hit = bool(sel_in) and (set(own) <= carriers if own else sel_in <= any_carrier and bool(sel_in & carriers))
                if not hit and unread:
                    continue                                # an unread word may name the rest: no evidence either way
                self.value_rule[1] += 1
                self.value_rule[0] += int(hit)""")
p.write_bytes(s.encode('utf-8'))
print('v17 part 2 ok')

# part 3: only an alternative with nothing like the selected objects in view leaves its word without evidence; an
# alternative that exists but was not selected is evidence against that word's meaning (it must be able to heal)
s = p.read_text(encoding='utf-8')
rep("""        bringers = {i for am in alts.values() for i in am.values()}""",
    """        insel0 = [{repr(x) for x in view[o][0]} for o in selected if o in view]
        def absent(key, a):                                 # nothing like the selected objects carries this alternative
            shared = {x for x in set.intersection(*insel0) if x.split(',')[2:3] != [key]} if insel0 else set()
            return not any(shared <= {repr(x) for x in at} and a in {repr(x) for x in at} for at, _ in view.values())
        bringers = {i for k, am in alts.items() for a, i in am.items() if absent(k, a)}""")
p.write_bytes(s.encode('utf-8'))
print('v17 part 3 ok')
