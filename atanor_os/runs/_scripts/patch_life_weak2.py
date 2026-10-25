"""v5b: weakness weighed by risk. After a demonstration, act on what was shown. With the person: point first, then
check the change with the pointed objects. Alone: hold a weak reading only when the change is irreversible or the
selection has no support at all (no value token, no strong object word); a reversible reading with some support is
acted on, and nothing is learned from it until the person confirms."""
import pathlib

p = pathlib.Path('atanor_os/agent/life.py')
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


# interpret: report whether the selection has any support
rep("""        cons, weak_selection = set(), False
        for t in toks:
            if t == dest or t in values or t in self.neutral or t in change_words or self.word_n[t] == 0:
                continue
            if self.strong(t):
                if self.meaning.get(t):
                    cons |= self.meaning[t]
            else:
                weak_selection = True                       # an object word with little evidence: ask or hold""",
    """        cons, weak_selection, support = set(), False, any(t in values and t != dest for t in toks)
        for t in toks:
            if t == dest or t in values or t in self.neutral or t in change_words or self.word_n[t] == 0:
                continue
            if self.strong(t):
                if self.meaning.get(t):
                    cons |= self.meaning[t]
                    support = True
            else:
                weak_selection = True                       # an object word with little evidence: ask or hold""")
rep("""                'decisive': decisive, 'weak_change': weak_change, 'weak_selection': weak_selection}""",
    """                'decisive': decisive, 'weak_change': weak_change, 'weak_selection': weak_selection, 'support': support}""")
# _understand: act on what was shown as soon as it was shown
rep("""        for _ in range(8):
            if self.fixed:                                    # fixed human procedure: always ask to be shown""",
    """        for _ in range(8):
            taught = self._from_taught(command, view)
            if taught is not None:
                return taught                                 # the person showed what this command means: do that
            if self.fixed:                                    # fixed human procedure: always ask to be shown""")
# point first, then check; alone, weigh by risk
rep("""            if r.get('weak_change') and key(r) not in checked and not r['unknown']:
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
                continue""", """            weak = r.get('weak_change') or r.get('weak_selection')
            if self.user is None and ((weak and self._irreversible(r['pid'])) or not r.get('support')):
                self.counts['refused_weak'] += 1
                self.log(event='refuse_weak', why='irreversible' if r.get('support') else 'no selection support')
                return None
            if self.user is not None and (r.get('weak_selection') or not r.get('support')) and pointed is None:
                ans = self.user.point(command)
                self.counts['point'] += 1
                self.log(event='ask_point', why='weak selection')
                self._learn_pointing(toks, view, ans)
                pointed = ans
                continue
            if self.user is not None and r.get('weak_change') and key(r) not in checked and not r['unknown']:
                checked.add(key(r))
                rr = {**r, 'selected': [o for o in pointed['objects'] if o in view], 'dest': pointed['dest'] or r['dest']} if pointed else r
                ok = self.user.check(self._proposal(rr))
                self.counts['check'] += 1
                self.methods['check'][0] += int(ok)
                self.methods['check'][1] += 1
                self.log(event='ask_check', why='weak change', ok=ok)
                if not ok:
                    rejected.add(key(r))
                    self._teach_from_demo(toks, command)
                    return self._from_taught(command, view)
                accepted = r['pid']""")
rep("""        if self.user is None and (r.get('weak_change') or r.get('weak_selection')):
            return False                                      # nobody to ask: a weak reading is not acted on""",
    """        if self.user is None:
            weak = r.get('weak_change') or r.get('weak_selection')
            if (weak and self._irreversible(r['pid'])) or not r.get('support', True):
                return False                                  # nobody to ask: no irreversible or unsupported guess""")
p.write_bytes(s.encode('utf-8'))
print('ok')
