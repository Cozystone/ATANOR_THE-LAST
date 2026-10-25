"""v5: a reading rests on evidence per word. A word is strong after three confirmed uses or pointings (a definition by
the person counts for three). The change must rest on a strong decisive unit and the selection on strong object words
(or on tokens that name observed values); otherwise the reading is weak: with the person, ask (check the change /
point at the objects); alone, hold. Words that decide the change carry no object meaning. Pointing teaches the
selection only, never ATANOR's own guess of the change."""
import pathlib

p = pathlib.Path('atanor_os/agent/life.py')
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""        self.confirmed = Counter()              # word -> confirmed uses (the result was what the person wanted)""",
    """        self.confirmed = Counter()              # word -> confirmed uses (the result was what the person wanted)
        self.pointed = Counter()                # word -> uses in which the person pointed at the objects
        self.defined = Counter()                # word -> explanations by the person""")
rep("""    def learn_word(self, word, pids=None, meaning=None, neutral=False):
        self.word_n[word] += 1""", """    def strong(self, unit):
        return self.confirmed[unit] + self.pointed[unit] + 3 * self.defined[unit] >= 3

    def learn_word(self, word, pids=None, meaning=None, neutral=False):
        self.word_n[word] += 1
        self.defined[word] += 1""")
# interpretation: roles rest on strong units only
rep("""        cons = set()
        for i, w in enumerate(toks):
            if w == dest:
                continue
            if self.word_n[w] >= MIN_WORD_COUNT and self.meaning.get(w):
                cons |= self.meaning[w]""", """        cons = set()
        for i, w in enumerate(toks):
            if w == dest:
                continue
            if self.word_n[w] >= MIN_WORD_COUNT and self.meaning.get(w):
                cons |= self.meaning[w]""") if 'MIN_WORD_COUNT' in s else None
rep("""        cons = set()
        for t in toks:
            if t != dest and t not in self.neutral and self.word_n[t] >= 2 and self.meaning.get(t):
                cons |= self.meaning[t]""", """        change_words = {w for u in units if self._share(u, pids)[1] >= DECISIVE and u not in values for w in u.split(' ')}
        weak_change = not any(self.strong(u) for u in units if self._share(u, pids)[1] >= DECISIVE and u not in values and u not in self.neutral)
        cons, weak_selection = set(), False
        for t in toks:
            if t == dest or t in values or t in self.neutral or t in change_words or self.word_n[t] == 0:
                continue
            if self.strong(t):
                if self.meaning.get(t):
                    cons |= self.meaning[t]
            else:
                weak_selection = True                       # an object word with little evidence: ask or hold""")
rep("""        return {'pid': pid, 'dest': dest, 'selected': sel, 'unknown': unknown, 'contradiction': contradiction, 'ambiguous': ambiguous,
                'decisive': decisive}""", """        return {'pid': pid, 'dest': dest, 'selected': sel, 'unknown': unknown, 'contradiction': contradiction, 'ambiguous': ambiguous,
                'decisive': decisive, 'weak_change': weak_change, 'weak_selection': weak_selection}""")
# the pairs/units must exist before the selection block: move the selection block after the voting block
start = s.index("        change_words = {w for u in units")
end = s.index("        hits, opp = self.value_rule")
block = s[start:end]
s = s[:start] + s[end:]
anchor = "        return {'pid': pid, 'dest': dest, 'selected': sel, 'unknown': unknown, 'contradiction': contradiction, 'ambiguous': ambiguous,"
# selection depends on cons: compute value rule and selection after the block; restructure the tail of interpret
tail_start = s.index("        hits, opp = self.value_rule")
tail_end = s.index(anchor)
tail = s[tail_start:tail_end]
s = s[:tail_start] + s[tail_end:]
vote_end = s.index(anchor)                       # the final return (the case-mode return comes earlier in the file)
s = s[:vote_end] + block + tail + s[vote_end:]
# pointing: learn the selection, never the guessed change; the pointed words gain evidence
rep("""                if needs_dest and not ans['dest']:
                    self._teach_from_demo(toks, command)          # no destination meant: the change itself was misread
                    continue
                self.lex.learn(toks, view, r['pid'], ans['objects'], ans['dest'])
                continue""", """                if needs_dest and not ans['dest']:
                    self._teach_from_demo(toks, command)          # no destination meant: the change itself was misread
                    continue
                self._learn_pointing(toks, view, ans)
                pointed = ans
                continue""")
rep("""            needs_dest = any(it[0] != 'o' for it in self.patterns[r['pid']])
            if r['contradiction'] or not r['selected'] or (needs_dest and not r['dest']):""",
    """            needs_dest = any(it[0] != 'o' for it in self.patterns[r['pid']])
            if r.get('weak_change') and key(r) not in checked and not r['unknown']:
                if self.user is None:
                    self.counts['refused_weak'] += 1
                    self.log(event='refuse_weak', why='change')
                    return None
                checked.add(key(r))
                ok = self.user.check(self._proposal(r))
                self.counts['check'] += 1
                self.methods['check'][0] += int(ok)
                self.methods['check'][1] += 1
                self.log(event='ask_check', why='weak change', ok=ok)
                if not ok:
                    rejected.add(key(r))
                    self._teach_from_demo(toks, command)
                    return self._from_taught(command, view)
                accepted = r['pid']
            if r.get('weak_selection') and pointed is None:
                if self.user is None:
                    self.counts['refused_weak'] += 1
                    self.log(event='refuse_weak', why='selection')
                    return None
                ans = self.user.point(command)
                self.counts['point'] += 1
                self.log(event='ask_point', why='weak selection')
                self._learn_pointing(toks, view, ans)
                pointed = ans
                continue
            if r['contradiction'] or not r['selected'] or (needs_dest and not r['dest']):""")
rep("""        asked_words, checked, rejected = set(), set(), set()""", """        asked_words, checked, rejected = set(), set(), set()
        pointed, accepted = None, None""")
# after the loop: a pointed selection replaces the inferred one
rep("""        taught = self._from_taught(command, view)
        if taught is not None:
            return taught                                     # the person showed what this command means
        r = self.lex.interpret(toks, view, True)""", """        taught = self._from_taught(command, view)
        if taught is not None:
            return taught                                     # the person showed what this command means
        r = self.lex.interpret(toks, view, True)
        if pointed is not None and r['pid'] in self.patterns:
            r = {**r, 'selected': [o for o in pointed['objects'] if o in view], 'dest': pointed['dest'] or r['dest'],
                 'contradiction': False, 'weak_selection': False}""")
rep("""    def _learn_explanation(self, word, answer, view):""", """    def _learn_pointing(self, toks, view, ans):
        \"\"\"The person pointed at the objects: the words learn what those objects share; no change is attributed.\"\"\"
        self.lex.learn(toks, view, None, ans['objects'], ans['dest'])
        values = {v for _, v in view.values()}
        for w in set(toks):
            if w != ans['dest'] and w not in values:
                self.lex.pointed[w] += 1

    def _learn_explanation(self, word, answer, view):""")
rep("""                'cases': {k: [v[0], v[1]] for k, v in self.cases.items()}, 'confirmed': dict(self.confirmed)}""",
    """                'cases': {k: [v[0], v[1]] for k, v in self.cases.items()}, 'confirmed': dict(self.confirmed),
                'pointed': dict(self.pointed), 'defined': dict(self.defined)}""")
rep("""        x.confirmed = Counter(d.get('confirmed', {}))
        return x""", """        x.confirmed = Counter(d.get('confirmed', {}))
        x.pointed, x.defined = Counter(d.get('pointed', {})), Counter(d.get('defined', {}))
        return x""")
# a complete reading must not be weak (alone) — _complete is used by _plannable paths and the final check
rep("""    def _complete(self, r):
        if r['pid'] is None or r['pid'] not in self.patterns or not r['selected'] or r['contradiction']:
            return False""", """    def _complete(self, r):
        if r['pid'] is None or r['pid'] not in self.patterns or not r['selected'] or r['contradiction']:
            return False
        if self.user is None and (r.get('weak_change') or r.get('weak_selection')):
            return False                                      # nobody to ask: a weak reading is not acted on""")
p.write_bytes(s.encode('utf-8'))
print('ok')
