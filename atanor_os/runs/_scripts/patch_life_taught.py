import pathlib

p = pathlib.Path('atanor_os/agent/life.py')
s = p.read_text(encoding='utf-8')


def rep(a, b, count=1):
    global s
    assert s.count(a) >= count, a[:70]
    s = s.replace(a, b)


# remember what the person showed for this command
rep("""        self.patterns[pid] = pattern
        rel = {o: 'o', dest: 'D', f'{dest}/{name_of(o)}': 'D/o'} if dest else {o: 'o'}""", """        self.patterns[pid] = pattern
        self._taught = {'command': command, 'pid': pid, 'selected': sorted(objs), 'dest': dest}
        rel = {o: 'o', dest: 'D', f'{dest}/{name_of(o)}': 'D/o'} if dest else {o: 'o'}""")
# both rejection branches: act on what was shown, never on a fresh unchecked reading
rep("""                old = key(r)
                self._teach_from_demo(toks, command)
                r = self.lex.interpret(toks, view, True)
                if not self._complete(r) or key(r) == old:
                    return None
                return self._result(r, view)""", """                self._teach_from_demo(toks, command)
                return self._from_taught(command, view)""")
rep("""                    old = key(r)
                    self._teach_from_demo(toks, command)
                    r = self.lex.interpret(toks, view, True)
                    if not self._complete(r) or key(r) == old:
                        return None                           # still the rejected reading: do not act
                    return self._result(r, view)""", """                    self._teach_from_demo(toks, command)
                    return self._from_taught(command, view)""")
# at the end of understanding: if the person showed this command, their showing is the reading
rep("""        r = self.lex.interpret(toks, view, True)
        if not self._complete(r) or key(r) in rejected:
            return None                                       # never act on an interpretation the person rejected""",
    """        taught = self._from_taught(command, view)
        if taught is not None:
            return taught                                     # the person showed what this command means
        r = self.lex.interpret(toks, view, True)
        if not self._complete(r) or key(r) in rejected:
            return None                                       # never act on an interpretation the person rejected""")
rep("""    def _proposal(self, r):""", """    def _from_taught(self, command, view):
        t = getattr(self, '_taught', None)
        if not t or t['command'] != command or t['pid'] not in self.patterns:
            return None
        sel = [o for o in t['selected'] if o in view]
        if not sel:
            return None
        return self._result({'pid': t['pid'], 'selected': sel, 'dest': t['dest']}, view)

    def _proposal(self, r):""")
p.write_bytes(s.encode('utf-8'))
print('ok')
