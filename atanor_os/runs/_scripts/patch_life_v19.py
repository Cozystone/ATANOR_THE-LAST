"""v19: a reading uses every value the command names, and the value rule only learns from uses it can explain.
- A word names values if it is a value of some object or if at least half of its remembered uses carried a value
  (its history, even when its current meaning has lost the value; at least 3 uses, and not a word whose
  uses mostly go with one change, which v18 handles). If objects carrying such a word's values are in
  view but none of its values restricts the reading, the reading drops part of the command: with the person it is pointed, alone it is held
  (replaces v17's coarser 'no named value used at all').
- Value rule: a use whose selection contains objects that no value named in the command explains is no evidence for
  or against values restricting the selection (found on transfer seed 25: unions with a still-unread word and days
  without one kind of file were counted as failures and trust fell to 73%)."""
import pathlib, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""                hit = bool(sel_in) and (set(own) <= carriers if own else sel_in <= any_carrier and bool(sel_in & carriers))
                if not hit and unread:
                    continue                                # an unread word may name the rest: no evidence either way""",
    """                hit = bool(sel_in) and (set(own) <= carriers if own else sel_in <= any_carrier and bool(sel_in & carriers))
                if not hit and (unread or not sel_in <= any_carrier):
                    continue                                # part of the selection is named by nothing read: no evidence either way""")
rep("""    def joined(self, word):""", """    def value_history(self, word):
        \"\"\"The value a word has kept naming: of its remembered uses that carried a value (at least 4), three quarters
        carried the same one, and that value was in at least half of all its uses (a function word co-occurs with
        whatever is selected, so its values spread).\"\"\"
        us = self.uses.get(word, [])
        vals = [{a for a in u if a.startswith("('U'") and a.split(',')[3].strip(" )'") not in ('0', '1', '-')} for u in us]
        valued = [v for v in vals if v]
        if len(valued) < 4:
            return set()
        c = Counter(a for v in valued for a in v)
        return {a for a, n in c.items() if 4 * n >= 3 * len(valued) and 2 * n >= len(us)}

    def joined(self, word):""")
rep("""        ignores_named = union_sel is None and not value_named and any(t in values and t != dest for t in toks) and not any(t in view and t != dest for t in toks)""",
    """        ignores_named = False
        if ids_named := [t for t in toks if t in view and t != dest]:
            pass                                                # objects named by their ids: nothing to drop
        else:
            used = set(cons) | ({x for am in self._alternatives(toks, view, dest).values() for x in am} if union_sel is not None else set())
            for t in set(toks):
                if t == dest or t in self.neutral:
                    continue
                if t in values:
                    va = {repr(a) for o, (at, vs) in view.items() if t in vs for a in at if a[0] == 'U' and a[3] == t}
                else:
                    pc = self.pattern_of.get(t)
                    n = sum(pc.values()) if pc else 0
                    names_change = n >= 3 and (pc.most_common(1)[0][1] + 0.1) / (n + 0.1 * len(pids)) >= DECISIVE
                    va = self.value_history(t) if self.strong(t) and len(self.uses.get(t, [])) >= 3 and not names_change else set()
                if not va:
                    continue
                present = any(va & {repr(a) for a in at} for at, _ in view.values())
                if present and not va & used:
                    ignores_named = True                    # a word that names values restricts nothing in this reading""")
p.write_bytes(s.encode('utf-8'))
print('v19 ok')
