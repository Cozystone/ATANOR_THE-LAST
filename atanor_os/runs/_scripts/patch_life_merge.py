import pathlib

p = pathlib.Path('atanor_os/agent/life.py')
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""        self._model = None
        self._cache = {'atoms': {}, 'rules': {}}""", """        self._model = None
        self._cache = {'atoms': {}, 'rules': {}}
        self._merge_patterns()""")
rep("""    def _implied(self, kind, attr, value):""", """    def _canonical(self, pattern):
        \"\"\"A change without the entries that are now known to follow from the kind (learned implication).\"\"\"
        kind_of = {it[0]: it[2] for it in pattern if it[1] == 'kind'}
        return sorted(it for it in pattern if it[1] == 'kind' or not self._implied(kind_of.get(it[0]), it[1], it[2]))

    def _merge_patterns(self):
        \"\"\"Changes that turn out to be the same once more is known get one identity; their word statistics and
        procedures are combined (so one intent is not split across ids learned at different times).\"\"\"
        if not self.patterns:
            return
        canon = {}
        for pid, pat in self.patterns.items():
            c = self._canonical(pat)
            canon.setdefault(json.dumps(c), []).append(pid)
        alias = {}
        for c, pids in canon.items():
            keep = sorted(pids)[0]
            self.patterns[keep] = json.loads(c)
            for q in pids:
                if q != keep:
                    alias[q] = keep
        if not alias:
            return
        for q, keep in alias.items():
            self.patterns.pop(q, None)
            if q in self.procedures and keep not in self.procedures:
                self.procedures[keep] = self.procedures[q]
            self.procedures.pop(q, None)
        for w, c in self.lex.pattern_of.items():
            for q, keep in alias.items():
                if q in c:
                    c[keep] += c.pop(q)
        self.lex.cases = {k: (alias.get(v[0], v[0]), v[1]) for k, v in self.lex.cases.items()}
        self.log(event='merged_changes', alias=alias)
        self.save()

    def _implied(self, kind, attr, value):""")
rep("""        self.log(event='demonstration', pid=pid, pattern=pattern, steps=steps)
        self.save()
        return True""", """        self.log(event='demonstration', pid=pid, pattern=pattern, steps=steps)
        self.save()
        self._merge_patterns()
        return True""")
p.write_bytes(s.encode('utf-8'))
print('ok')
