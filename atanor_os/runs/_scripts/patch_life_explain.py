import pathlib

p = pathlib.Path('atanor_os/agent/life.py')
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


# the voting reports how decisive its strongest word was
rep("""            weight = 1.0 - ent                              # a word used with every change says little about which one
            for q, x in zip(pids, probs):""", """            weight = 1.0 - ent                              # a word used with every change says little about which one
            decisive = max(decisive, weight)
            for q, x in zip(pids, probs):""")
rep("""        informative = 0
        for t in toks:
            pc = self.pattern_of.get(t)""", """        informative, decisive = 0, 0.0
        for t in toks:
            pc = self.pattern_of.get(t)""")
rep("""        return {'pid': pid, 'dest': dest, 'selected': sel, 'unknown': unknown, 'contradiction': contradiction, 'ambiguous': ambiguous}""",
    """        return {'pid': pid, 'dest': dest, 'selected': sel, 'unknown': unknown, 'contradiction': contradiction, 'ambiguous': ambiguous,
                'decisive': decisive}""")
# an explanation teaches a change only through a decisive word
rep("""        pids = {self.lex.pattern_of[t].most_common(1)[0][0] for t in ptoks if t in self.lex.pattern_of and t not in self.lex.neutral
                and self.lex.pattern_of[t].most_common(1)[0][1] / sum(self.lex.pattern_of[t].values()) >= 0.75}
        known_pid = next(iter(pids)) if len(pids) == 1 and next(iter(pids)) in self.patterns else None""",
    """        known_pid = r['pid'] if (r['pid'] in self.patterns and not r.get('ambiguous') and r.get('decisive', 0) >= 0.5) else None""")
# the person's pointing contradicts a change that needs a destination: the change is wrong, be shown instead
rep("""                ans = self.user.point(command)
                self.counts['point'] += 1
                self.log(event='ask_point', why='contradiction' if r['contradiction'] else ('nothing selected' if not r['selected'] else 'no destination'))
                self.lex.learn(toks, view, r['pid'], ans['objects'], ans['dest'])
                continue""", """                ans = self.user.point(command)
                self.counts['point'] += 1
                self.log(event='ask_point', why='contradiction' if r['contradiction'] else ('nothing selected' if not r['selected'] else 'no destination'))
                if needs_dest and not ans['dest']:
                    self._teach_from_demo(toks, command)          # no destination meant: the change itself was misread
                    continue
                self.lex.learn(toks, view, r['pid'], ans['objects'], ans['dest'])
                continue""")
p.write_bytes(s.encode('utf-8'))
print('ok')
