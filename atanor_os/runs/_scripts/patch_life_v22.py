"""v22: what a change rewrites does not name its object; a value history is the strict majority of valued uses.
- An atom on an attribute that the confirmed change itself rewrites on its object (sort for a sort, filter for a
  filter) describes the state being replaced, not what the word names: it is not recorded as telling the objects
  apart (screen evaluation seed 18 of v21: the sort verb 'arrange' looked like it named panels sorted by 'name' - their
  state before every sort - and its readings were held as role-ambiguous).
- (A looser value history was tried and dropped: on the dev seed no threshold separated a blurred object word, 0.58,
  from function words, up to 0.64; the blurring has to be stopped where it happens.)"""
import pathlib, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""        self.kind_keys = set()                  # the body's kind attributes (given by the body, not learned)""",
    """        self.kind_keys = set()                  # the body's kind attributes (given by the body, not learned)
        self.changed_keys = {}                  # change id -> attributes it rewrites on its object (from its pattern)""")
rep("""                    self._add_use(w, part, disc=self._discriminating(part, own[0], view))
                else:
                    self._add_use(w, cur, disc=self._discriminating(cur, selected, view))""",
    """                    self._add_use(w, part, disc=self._discriminating(part, own[0], view, pid))
                else:
                    self._add_use(w, cur, disc=self._discriminating(cur, selected, view, pid))""")
rep("""    def _discriminating(self, atoms_repr, objs, view):
        \"\"\"Of these atoms, the value atoms that some other object of the same kind lacked (they told objects apart).\"\"\"""",
    """    def _discriminating(self, atoms_repr, objs, view, pid=None):
        \"\"\"Of these atoms, the value atoms that some other object of the same kind lacked (they told objects apart),
        leaving out attributes the change itself rewrites on its object.\"\"\"
        rewritten = self.changed_keys.get(pid, set())
        atoms_repr = {a for a in atoms_repr if not (a.startswith("('U'") and a.split(',')[2].strip(" '") in rewritten)}""")
rep("""    def _merge_patterns(self):""", """    def _changed_keys(self, pid):
        \"\"\"Raw attributes that this change rewrites on its object (read from its pattern through the body's mapping).\"\"\"
        preds = {it[1] for it in self.patterns.get(pid, []) if it[0] == 'o' and it[1] != 'kind' and not (len(it) > 3 and it[3] == 'keep')}
        keys = set()
        for pr in preds:
            base = {q: 'x0' for q in preds | {pr}}
            r0, r1 = raw_attrs(self.body, base), raw_attrs(self.body, {**base, pr: 'x1'})
            keys |= {k for k in r0 if r0[k] != r1[k]}
        return keys

    def _merge_patterns(self):""")
rep("""        self._merge_patterns()
        self._noticed = []""",
    """        self._merge_patterns()
        self.lex.changed_keys = {pid: self._changed_keys(pid) for pid in self.patterns}
        self._noticed = []""")
rep("""        self.save()
        self._merge_patterns()
        return True""", """        self.save()
        self._merge_patterns()
        self.lex.changed_keys = {q: self._changed_keys(q) for q in self.patterns}
        return True""")
p.write_bytes(s.encode('utf-8'))
print('v22 ok')

# part 2: a word that names a value learns only from its own part of a mixed selection
s = p.read_text(encoding='utf-8')
rep("""                own = [parts[i] for i, t in enumerate(toks) if t == w and i in parts]
                if not own and any(t == w and i in bringers for i, t in enumerate(toks)):
                    continue                                # its own part of the selection cannot be told apart: no evidence""",
    """                own = [parts[i] for i, t in enumerate(toks) if t == w and i in parts]
                if not own and any(t == w and i in bringers for i, t in enumerate(toks)):
                    continue                                # its own part of the selection cannot be told apart: no evidence
                va = self.naming_atoms(w) if w not in values and self.strong(w) else set()
                if not own and va and selected:
                    sel_in = [o for o in selected if o in view]
                    mine = [o for o in sel_in if va & {repr(a) for a in view[o][0]}]
                    if not mine:
                        if self._absent_like(va, sel_in, view):
                            continue                        # nothing it names is here today: this use says nothing about it
                    elif len(mine) < len(sel_in):
                        own = [mine]                        # a mixed selection: the word learns from the part it names""")
rep("""    def naming_atoms(self, word):""", """    def _absent_like(self, atoms, objs, view):
        \"\"\"No object like these (same kind, sharing what they all share outside these atoms' attributes) carries the atoms.\"\"\"
        insel = [{repr(x) for x in view[o][0]} for o in objs if o in view]
        keys = {a.split(',')[2] for a in atoms}
        shared = {x for x in set.intersection(*insel) if x.split(',')[2:3] not in [[k] for k in keys]} if insel else set()
        return not any(shared <= {repr(x) for x in at} and atoms & {repr(x) for x in at} for at, _ in view.values())

    def naming_atoms(self, word):""")
p.write_bytes(s.encode('utf-8'))
print('v22 part 2 ok')
