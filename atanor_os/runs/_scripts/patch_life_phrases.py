"""v4: phrase units in the lexicon. Adjacent word pairs get their own statistics; when a pair is itself decisive about
the change (mostly used with one change), it speaks for its words. Nothing names which pairs are verbs."""
import pathlib

p = pathlib.Path('atanor_os/agent/life.py')
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


# learning: pairs are counted like words (change statistics only; selection meaning stays per word)
rep("""        for w in set(t for i, t in enumerate(toks) if i != d_idx):
            self.word_n[w] += 1
            if pid is not None:
                self.pattern_of[w][pid] += 1
            if w not in self.neutral:
                self.meaning[w] = cur if w not in self.meaning else (self.meaning[w] & cur)""",
    """        for w in set(t for i, t in enumerate(toks) if i != d_idx):
            self.word_n[w] += 1
            if pid is not None:
                self.pattern_of[w][pid] += 1
            if w not in self.neutral:
                self.meaning[w] = cur if w not in self.meaning else (self.meaning[w] & cur)
        for pair in self.pairs(toks, dest, values):
            if pid is not None:
                self.pattern_of[pair][pid] += 1""")
rep("""    def learn_word(self, word, pids=None, meaning=None, neutral=False):""", """    @staticmethod
    def pairs(toks, dest=None, values=()):
        \"\"\"Adjacent word pairs that name neither the destination nor an observed value.\"\"\"
        return [f'{a} {b}' for a, b in zip(toks, toks[1:]) if dest not in (a, b) and a not in values and b not in values]

    def _share(self, unit, pids):
        pc = self.pattern_of.get(unit)
        if not pc:
            return None, 0.0
        n = sum(pc.values())
        top, c = pc.most_common(1)[0]
        return top, (c + 0.1) / (n + 0.1 * len(pids))

    def learn_word(self, word, pids=None, meaning=None, neutral=False):""")
# voting: a decisive pair replaces its two words; remaining words vote alone; decisive = mostly one change
rep("""        pids = sorted({q for c in self.pattern_of.values() for q in c})
        logp = {q: 0.0 for q in pids}
        informative, decisive = 0, 0.0
        for t in toks:
            pc = self.pattern_of.get(t)
            if t in values or t == dest or not pc or t in self.neutral:
                continue                                    # a word that names objects does not name the change
            informative += 1""", """        pids = sorted({q for c in self.pattern_of.values() for q in c})
        logp = {q: 0.0 for q in pids}
        informative, decisive = 0, 0.0
        units, i = [], 0
        while i < len(toks):
            pair = f'{toks[i]} {toks[i + 1]}' if i + 1 < len(toks) else None
            top, share = self._share(pair, pids) if pair else (None, 0.0)
            if pair and share >= DECISIVE and dest not in (toks[i], toks[i + 1]) and toks[i] not in values and toks[i + 1] not in values:
                units.append(pair)                          # the pair speaks for both words
                i += 2
                continue
            units.append(toks[i])
            i += 1
        for t in units:
            pc = self.pattern_of.get(t)
            if t in values or t == dest or not pc or t in self.neutral:
                continue
            informative += 1""")
rep("""            pid = max(logp, key=logp.get)
            tops = set()
            for t in toks:
                pc = self.pattern_of.get(t)
                if t in values or t == dest or not pc or t in self.neutral:
                    continue
                n = sum(pc.values())
                probs = [(pc[q] + 0.1) / (n + 0.1 * len(pids)) for q in pids]
                ent = -sum(x * math.log(x) for x in probs) / math.log(len(pids)) if len(pids) > 1 else 0.0
                if 1.0 - ent >= 0.3:                        # an informative word: it mostly goes with one change
                    tops.add(pc.most_common(1)[0][0])
            ambiguous = len(tops) != 1 or pid not in tops   # informative words disagree, or none exists""",
    """            pid = max(logp, key=logp.get)
            tops = set()
            for t in units:
                if t in values or t == dest or t in self.neutral:
                    continue
                top, share = self._share(t, pids)
                if top is not None and share >= DECISIVE:   # a decisive unit: mostly used with one change
                    tops.add(top)
            ambiguous = len(tops) != 1 or pid not in tops   # decisive units disagree, or none exists""")
rep("""            for t in toks:                                  # a decisive word confirmed only with another change: conflict
                pc = self.pattern_of.get(t)
                if t in values or t == dest or not pc or t in self.neutral:
                    continue
                top, n = pc.most_common(1)[0]
                if top != pid and n / sum(pc.values()) >= 0.9 and self.confirmed.get(f'{t}|{top}', 0) and not self.confirmed.get(f'{t}|{pid}', 0):
                    ambiguous = True""", """            for t in units:                                 # a decisive unit confirmed only with another change: conflict
                pc = self.pattern_of.get(t)
                if t in values or t == dest or not pc or t in self.neutral:
                    continue
                top, n = pc.most_common(1)[0]
                if top != pid and n / sum(pc.values()) >= 0.9 and self.confirmed.get(f'{t}|{top}', 0) and not self.confirmed.get(f'{t}|{pid}', 0):
                    ambiguous = True""")
rep("""LAB_COST = 1 / 20          # provided preference: one question to the person costs as much as 20 lab actions""",
    """LAB_COST = 1 / 20          # provided preference: one question to the person costs as much as 20 lab actions
DECISIVE = 0.75            # provided: a unit is decisive about the change when it mostly goes with one change""")
# confirmations: pairs are confirmed with their words
rep("""        if confirmed:
            for w in set(toks):
                self.lex.confirmed[w] += 1
                self.lex.confirmed[f"{w}|{interp['pid']}"] += 1    # confirmed together with this change""",
    """        if confirmed:
            for w in set(toks) | set(self.lex.pairs(toks, interp['dest'])):
                self.lex.confirmed[w] += 1
                self.lex.confirmed[f"{w}|{interp['pid']}"] += 1    # confirmed together with this change""")
# an explanation's decisive unit teaches the change of the explained word (phrases included)
rep("""        known_pid = r['pid'] if (r['pid'] in self.patterns and not r.get('ambiguous') and r.get('decisive', 0) >= 0.5) else None""",
    """        known_pid = r['pid'] if (r['pid'] in self.patterns and not r.get('ambiguous') and r.get('decisive', 0) >= 0.3) else None""")
p.write_bytes(s.encode('utf-8'))
print('ok')
