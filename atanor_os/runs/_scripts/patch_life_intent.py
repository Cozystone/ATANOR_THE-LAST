import pathlib

p = pathlib.Path('atanor_os/agent/life.py')
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


# 1. a shown change is stored as end-state requirements: every role path that changed, and every role path that is an
#    ancestor of one that changed (its end state is part of the change), so the same intent gets the same identity
rep("""        pat = []
        for p in sorted(set(before) | set(after)):
            b, a = before.get(p, {}), after.get(p, {})
            for k in ('kind', 'hash'):
                if b.get(k) != a.get(k):
                    if k != 'kind' and self._implied(a.get('kind'), k, a.get(k)):
                        continue                               # learned: every object of this kind seen so far had this value
                    if p not in rels:
                        return None
                    v = '=o' if k == 'hash' and a.get(k) == before[o].get('hash') and a.get(k) != '-' else a.get(k)
                    pat.append([rels[p], k, v])""", """        pat = []
        changed = [p for p in sorted(set(before) | set(after)) if any(before.get(p, {}).get(k) != after.get(p, {}).get(k) for k in ('kind', 'hash'))]
        if any(p not in rels for p in changed):
            return None
        needed = set(changed) | {q for q in rels if any(c.startswith(q + '/') for c in changed)}
        for p in sorted(needed):
            b, a = before.get(p, {}), after.get(p, {})
            for k in ('kind', 'hash'):
                if k == 'kind' or b.get(k) != a.get(k):
                    if k != 'kind' and self._implied(a.get('kind'), k, a.get(k)):
                        continue                               # learned: every object of this kind seen so far had this value
                    v = '=o' if k == 'hash' and a.get(k) == before[o].get('hash') and a.get(k) != '-' else a.get(k)
                    pat.append([rels[p], k, v])""")
# 2. a word votes for the change it is mostly used with (>= 75 % of its uses), not only when it was never used otherwise
rep("""            if pc and len(pc) == 1 and t not in self.neutral:
                votes[next(iter(pc))] += 1""", """            if pc and t not in self.neutral:
                top, n = pc.most_common(1)[0]
                if n / sum(pc.values()) >= 0.75:
                    votes[top] += 1""")
rep("""        pids = {next(iter(self.lex.pattern_of[t])) for t in ptoks if len(self.lex.pattern_of.get(t, {})) == 1 and t not in self.lex.neutral}""",
    """        pids = {self.lex.pattern_of[t].most_common(1)[0][0] for t in ptoks if t in self.lex.pattern_of and t not in self.lex.neutral
                and self.lex.pattern_of[t].most_common(1)[0][1] / sum(self.lex.pattern_of[t].values()) >= 0.75}""")
p.write_bytes(s.encode('utf-8'))
print('ok')
