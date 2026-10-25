"""v21: a kind is not a name, on every body. Whether an atom names a value (for object words, unions, value histories,
specific meanings) was tested by excluding the values 0/1/- - the file body's encoding of its kind attributes. On the
screen body the kind attribute carries words ('panel'), so every word used with panels looked like an object word,
its change evidence was zeroed, and every command stayed a 'weak change' checked with the person, month after month
(90-day screen life, seed 16: 56 of 56 person tasks in the third month). The body already declares its kind
attributes (KIND_ATTRS, part of the body interface since v6); the test now excludes them on any body."""
import pathlib, re, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')
old = """a.startswith("('U'") and a.split(',')[3].strip(" )'") not in ('0', '1', '-')"""
n = s.count(old)
assert n == 7, n
s = s.replace(old, "self.valued(a)")


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""    def names_value(self, word):""", """    def valued(self, a):
        \"\"\"An atom that names a value: an attribute value that is neither a kind attribute of the body nor empty.\"\"\"
        if not a.startswith("('U'"):
            return False
        parts = a.split(',')
        return parts[2].strip(" '") not in self.kind_keys and parts[3].strip(" )'") not in ('0', '1', '-')

    def names_value(self, word):""")
rep("""        self.mode = mode                        # 'general' or 'case' (exact sentence-shape retrieval only)""",
    """        self.mode = mode                        # 'general' or 'case' (exact sentence-shape retrieval only)
        self.kind_keys = set()                  # the body's kind attributes (given by the body, not learned)""")
rep("""        self.lex = Lexicon.from_json(json.loads(lp.read_text(encoding='utf-8'))) if lp.exists() else Lexicon(lexicon_mode)""",
    """        self.lex = Lexicon.from_json(json.loads(lp.read_text(encoding='utf-8'))) if lp.exists() else Lexicon(lexicon_mode)
        self.lex.kind_keys = set(KIND_ATTRS.get(self.body, ()))""")
p.write_bytes(s.encode('utf-8'))
print('v21 ok')

# part 2: an atom names something only if it set the selected objects apart from others of their kind when used
s = p.read_text(encoding='utf-8')
rep("""    def _add_use(self, word, atoms_repr, times=1):
        us = self.uses.setdefault(word, [])
        for _ in range(times):
            us.append(set(atoms_repr))
        del us[:-24]
        self._derive(word)""", """    def _add_use(self, word, atoms_repr, times=1, disc=None):
        us = self.uses.setdefault(word, [])
        ds = self.disc_uses.setdefault(word, [])
        for _ in range(times):
            us.append(set(atoms_repr))
            ds.append({a for a in atoms_repr if self.valued(a)} if disc is None else set(disc))
        del us[:-24]
        del ds[:-24]
        self._derive(word)

    def _discriminating(self, atoms_repr, objs, view):
        \"\"\"Of these atoms, the value atoms that some other object of the same kind lacked (they told objects apart).\"\"\"
        objs = [o for o in objs if o in view]
        if not objs:
            return set()
        kinds = {a for a in {repr(x) for x in view[objs[0]][0]} if a.startswith("('U'") and a.split(',')[2].strip(" '") in self.kind_keys}
        peers = [{repr(x) for x in at} for o, (at, _) in view.items() if o not in objs and kinds <= {repr(x) for x in at}]
        return {a for a in atoms_repr if self.valued(a) and any(a not in pa for pa in peers)}

    def naming_atoms(self, word):
        \"\"\"Value atoms of the word's meaning that told its objects apart in at least half of its remembered uses.\"\"\"
        m = self.meaning.get(word, ())
        ds = self.disc_uses.get(word)
        if not ds:
            return {a for a in m if self.valued(a)}
        c = Counter(a for d in ds for a in d)
        return {a for a in m if self.valued(a) and 2 * c[a] >= len(ds)}""")
rep("""        self.uses = {}                          # word -> list of per-use common-atom sets (repr strings), last 24""",
    """        self.uses = {}                          # word -> list of per-use common-atom sets (repr strings), last 24
        self.disc_uses = {}                     # word -> per use, the value atoms that told the selected objects apart""")
rep("""                if own:                                     # a value word in a union learns from its own part
                    sub = [view[o][0] for o in own[0] if o in view]
                    self._add_use(w, {repr(a) for a in frozenset.intersection(*sub)} if sub else cur)
                else:
                    self._add_use(w, cur)""", """                if own:                                     # a value word in a union learns from its own part
                    sub = [view[o][0] for o in own[0] if o in view]
                    part = {repr(a) for a in frozenset.intersection(*sub)} if sub else cur
                    self._add_use(w, part, disc=self._discriminating(part, own[0], view))
                else:
                    self._add_use(w, cur, disc=self._discriminating(cur, selected, view))""")
rep("""        return self.strong(word) and any(self.valued(a) for a in self.meaning.get(word, ()))""",
    """        return self.strong(word) and bool(self.naming_atoms(word))""")
rep("""                got = {a for a in self.meaning[t] if self.valued(a)}""", """                got = self.naming_atoms(t)""")
rep("""        vals = [{a for a in u if self.valued(a)} for u in us]""", """        vals = [set(d) for d in self.disc_uses.get(word, [])] or [{a for a in u if self.valued(a)} for u in us]""")
rep("""                return {a for a in self.meaning.get(t, ()) if self.valued(a)}""", """                return self.naming_atoms(t)""")
rep("""                               for a in self.meaning.get(t, ()) if self.valued(a)}""", """                               for a in self.naming_atoms(t)}""")
rep("""                'uses': {w: [sorted(u) for u in us] for w, us in self.uses.items()},""",
    """                'uses': {w: [sorted(u) for u in us] for w, us in self.uses.items()},
                'disc_uses': {w: [sorted(u) for u in us] for w, us in self.disc_uses.items()},""")
rep("""        x.uses = {w: [set(u) for u in us] for w, us in d.get('uses', {}).items()}""",
    """        x.uses = {w: [set(u) for u in us] for w, us in d.get('uses', {}).items()}
        x.disc_uses = {w: [set(u) for u in us] for w, us in d.get('disc_uses', {}).items()}""")
rep("""            self.meaning.pop(word, None)
            self.uses.pop(word, None)""", """            self.meaning.pop(word, None)
            self.uses.pop(word, None)
            self.disc_uses.pop(word, None)""")
rep("""                self.uses[word] = []                         # the person's definition supersedes what co-occurrence suggested""",
    """                self.uses[word] = []                         # the person's definition supersedes what co-occurrence suggested
                self.disc_uses[word] = []""")
p.write_bytes(s.encode('utf-8'))
print('v21 part 2 ok')

# part 3: a word that tells the second object apart from others of its kind also names objects (not a change word)
s = p.read_text(encoding='utf-8')
rep("""                us = self.duses.setdefault(w, [])
                us.append(set(dcur))""", """                for a in self._discriminating(dcur, [dest], view):
                    self.d_disc[w][a] += 1
                us = self.duses.setdefault(w, [])
                us.append(set(dcur))""")
rep("""        self.d_n = Counter()                    # word -> confirmed uses with a second object""",
    """        self.d_n = Counter()                    # word -> confirmed uses with a second object
        self.d_disc = defaultdict(Counter)      # word -> atoms that told its second object apart, per use""")
rep("""    def names_value(self, word):""", """    def names_second(self, word):
        \"\"\"A strong word whose second-object meaning told that object apart from others of its kind in half its uses.\"\"\"
        n = self.d_n[word]
        return self.strong(word) and n >= 3 and any(2 * self.d_disc[word][a] >= n for a in self.dmeaning.get(word, ()))

    def names_value(self, word):""")
rep("""        if n < 3 or self.names_value(unit):""", """        if n < 3 or self.names_value(unit) or self.names_second(unit):""")
rep("""                'd_n': dict(self.d_n)}""", """                'd_n': dict(self.d_n), 'd_disc': {w: dict(c) for w, c in self.d_disc.items()}}""")
rep("""        x.d_n = Counter(d.get('d_n', {}))""", """        x.d_n = Counter(d.get('d_n', {}))
        x.d_disc = defaultdict(Counter, {w: Counter(c) for w, c in d.get('d_disc', {}).items()})""")
p.write_bytes(s.encode('utf-8'))
print('v21 part 3 ok')
