"""v11: meanings heal. A word's meaning is no longer a monotone intersection over all its uses (one bad use removed
the discriminating atom forever); the lexicon keeps the common atoms of each use (last 24) and the meaning is what at
least three quarters of those uses share, so a single bad use cannot poison it and good uses restore it. A person's
definition replaces the remembered uses and counts as three. A selection that names no value and rests on no literal naming is unspecific:
with the person it is pointed at, alone it is held."""
import pathlib, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""        self.meaning = {}                       # word -> set(repr(atom)) intersected over selections""",
    """        self.meaning = {}                       # word -> set(repr(atom)) shared by most of its recent uses
        self.uses = {}                          # word -> list of per-use common-atom sets (repr strings), last 24""")
rep("""    def learn(self, toks, view, pid, selected, dest):
        self.note_values(view)""", """    def _derive(self, word):
        \"\"\"The meaning is what at least three quarters of the word's remembered uses share.\"\"\"
        us = self.uses.get(word, [])
        if not us:
            return
        need = max(1, -(-3 * len(us) // 4))
        counts = Counter(a for u in us for a in u)
        self.meaning[word] = {a for a, c in counts.items() if c >= need}

    def _add_use(self, word, atoms_repr, times=1):
        us = self.uses.setdefault(word, [])
        for _ in range(times):
            us.append(set(atoms_repr))
        del us[:-24]
        self._derive(word)

    def learn(self, toks, view, pid, selected, dest):
        self.note_values(view)""")
rep("""            if w not in self.neutral:
                self.meaning[w] = cur if w not in self.meaning else (self.meaning[w] & cur)""",
    """            if w not in self.neutral:
                self._add_use(w, cur)""")
rep("""            old_m = self.meaning.get(word)
            if old_m is not None and specific(old_m) and not specific(meaning):
                pass                                         # the explanation names no value: keep the more specific meaning
            else:
                self.meaning[word] = set(meaning)""", """            old_m = self.meaning.get(word)
            if old_m is not None and specific(old_m) and not specific(meaning):
                pass                                         # the explanation names no value: keep the more specific meaning
            else:
                self.uses[word] = []                         # the person's definition supersedes what co-occurrence suggested
                self._add_use(word, set(meaning), times=3)   # and weighs three uses: later uses can still heal it""")
rep("""                'meaning': {w: sorted(m) for w, m in self.meaning.items()}, 'neutral': sorted(self.neutral),""",
    """                'meaning': {w: sorted(m) for w, m in self.meaning.items()}, 'neutral': sorted(self.neutral),
                'uses': {w: [sorted(u) for u in us] for w, us in self.uses.items()},""")
rep("""        x.meaning = {w: set(m) for w, m in d['meaning'].items()}""",
    """        x.meaning = {w: set(m) for w, m in d['meaning'].items()}
        x.uses = {w: [set(u) for u in us] for w, us in d.get('uses', {}).items()}""")
rep("""            self.neutral.add(word)
            self.meaning.pop(word, None)""", """            self.neutral.add(word)
            self.meaning.pop(word, None)
            self.uses.pop(word, None)""")
# unspecific selection: no value named, no literal naming
rep("""        by_key = defaultdict(set)
        for a in cons:
            if a.startswith("('U'"):
                by_key[a.split(',')[2]].add(a)
        contradiction = any(len(v) > 1 for v in by_key.values())""", """        by_key = defaultdict(set)
        for a in cons:
            if a.startswith("('U'"):
                by_key[a.split(',')[2]].add(a)
        contradiction = any(len(v) > 1 for v in by_key.values())
        value_named = any(a.startswith("('U'") and a.split(',')[3].strip(" )'") not in ('0', '1', '-') for a in cons)
        if not value_named and not literal:
            weak_selection = True                               # 'everything' with no value named: ask or hold""")
p.write_bytes(s.encode('utf-8'))
print('v11 ok')
