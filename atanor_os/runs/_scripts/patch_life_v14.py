"""v14: a second object named by well-evidenced words is not a guess, and every hold says why.
- The words' meaning for a second object (dmeaning) heals like a selection meaning (v11): it is what at least 3/4 of
  the word's last 24 confirmed uses with a second object shared, and the number of such uses is kept (d_n).
- A second object found through those meanings is a guess (ask or hold) only while some contributing word has fewer
  than 3 such uses; with enough evidence it is a reading like a selection by a strong word. Irreversible changes still
  need literal naming.
- Every alone-day hold records its reason (unknown words, no known change, incomplete reading)."""
import pathlib, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""        self.dmeaning = {}                      # word -> atoms every second object it was used with had in common""",
    """        self.dmeaning = {}                      # word -> atoms most second objects it was used with had in common
        self.duses = {}                         # word -> per-use atoms of the second object (last 24)
        self.d_n = Counter()                    # word -> confirmed uses with a second object""")
rep("""                self.dmeaning[w] = dcur if w not in self.dmeaning else (self.dmeaning[w] & dcur)""",
    """                us = self.duses.setdefault(w, [])
                us.append(set(dcur))
                del us[:-24]
                self.d_n[w] += 1
                need = max(1, -(-3 * len(us) // 4))
                cnt = Counter(a for u in us for a in u)
                self.dmeaning[w] = {a for a, c in cnt.items() if c >= need}""")
rep("""                'value_atoms': dict(self.value_atoms)}""",
    """                'value_atoms': dict(self.value_atoms), 'duses': {w: [sorted(u) for u in us] for w, us in self.duses.items()},
                'd_n': dict(self.d_n)}""")
rep("""        x.value_atoms = dict(d.get('value_atoms', {}))""",
    """        x.value_atoms = dict(d.get('value_atoms', {}))
        x.duses = {w: [set(u) for u in us] for w, us in d.get('duses', {}).items()}
        x.d_n = Counter(d.get('d_n', {}))""")
rep("""        cons = set()
        for t in toks:
            if t not in view and t not in self.lex.neutral and t not in change_words and self.lex.strong(t) and self.lex.dmeaning.get(t):
                cons |= self.lex.dmeaning[t]
        if cons:
            cands = [o for o, (at, vs) in view.items() if o not in r['selected'] and kind_ok(at) and cons <= {repr(a) for a in at}]
            if len(cands) == 1:
                return {**r, 'dest': cands[0], 'dest_by_meaning': True}   # a guess from meanings: ask or hold""",
    """        cons, by = set(), []
        for t in toks:
            if t not in view and t not in self.lex.neutral and t not in change_words and self.lex.strong(t) and self.lex.dmeaning.get(t):
                cons |= self.lex.dmeaning[t]
                by.append(t)
        if cons:
            cands = [o for o, (at, vs) in view.items() if o not in r['selected'] and kind_ok(at) and cons <= {repr(a) for a in at}]
            if len(cands) == 1:
                guess = any(self.lex.d_n[t] < 3 for t in by)       # too few uses naming a second object: a guess, ask or hold
                return {**r, 'dest': cands[0], 'dest_by_meaning': guess}""")
# every alone hold says why
rep("""            if r['pid'] is None or r['pid'] not in self.patterns or (key(r) in rejected and self.user is not None):
                if self.user is None:
                    return None""",
    """            if r['pid'] is None or r['pid'] not in self.patterns or (key(r) in rejected and self.user is not None):
                if self.user is None:
                    why = 'unknown' if r['unknown'] else 'no_change'
                    self.counts[f'refused_{why}'] += 1
                    self.log(event=f'refuse_{why}', words=r['unknown'])
                    return None""")
rep("""            if r['contradiction'] or not r['selected'] or (needs_dest and not r['dest']):
                if self.user is None:
                    return None""",
    """            if r['contradiction'] or not r['selected'] or (needs_dest and not r['dest']):
                if self.user is None:
                    self.counts['refused_incomplete'] += 1
                    self.log(event='refuse_incomplete', why='contradiction' if r['contradiction'] else ('nothing selected' if not r['selected'] else 'no second object'))
                    return None""")
rep("""        if not self._complete(r) or key(r) in rejected:
            return None                                       # never act on an interpretation the person rejected""",
    """        if not self._complete(r) or key(r) in rejected:
            if self.user is None:
                self.counts['refused_incomplete'] += 1
                self.log(event='refuse_incomplete', why='rejected' if key(r) in rejected else 'weak or incomplete reading',
                         dest_by_meaning=bool(r.get('dest_by_meaning')))
            return None                                       # never act on an interpretation the person rejected""")
p.write_bytes(s.encode('utf-8'))
print('v14 ok')
