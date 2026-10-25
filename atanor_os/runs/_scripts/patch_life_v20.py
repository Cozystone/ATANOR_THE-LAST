"""v20: an unheard word standing where joining words stand is offered as one, and checked. When a command brings
alternatives for one attribute, nothing known between them joins, but an unknown word stands between them and the
core already knows some joining word, the core forms the reading in which that word joins (the union) and asks the
person to check it, instead of asking what the word means and then to be pointed at the objects. The check decides;
a confirmed use is ordinary joining evidence for the new word. Alone the reading is never used (unknown words hold).
No new structure: the union reading of v16, proposed by analogy and verified by the existing check question."""
import pathlib, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""    def interpret(self, toks, view, takes_dest):""", """    def interpret(self, toks, view, takes_dest, join_unknown=False):""")
rep("""            if len(alts) == 1 and any(self.joined(w) for w in self._between(toks, next(iter(alts.values())))):""",
    """            between = self._between(toks, next(iter(alts.values()))) if len(alts) == 1 else set()
            by_analogy = join_unknown and any(self.joined(w) for w in self.join) and any(self.word_n[w] == 0 for w in between)
            if len(alts) == 1 and (any(self.joined(w) for w in between) or by_analogy):""")
rep("""            if r['unknown'] and self.user is not None:
                if not self.patterns or '<shape>' in r['unknown']:
                    self._teach_from_demo(toks, command)          # nothing known yet to explain it with: be shown
                    continue""", """            if r['unknown'] and self.user is not None:
                if not self.patterns or '<shape>' in r['unknown']:
                    self._teach_from_demo(toks, command)          # nothing known yet to explain it with: be shown
                    continue
                if r['contradiction'] and 'join_tried' not in checked:
                    checked.add('join_tried')                     # an unheard word where joining words stand: offer that reading
                    rj = self._resolve_dest(self.lex.interpret(toks, view, True, join_unknown=True), toks, view)
                    if not rj['contradiction'] and rj['selected'] and rj['pid'] in self.patterns:
                        ok = self.user.check(self._proposal(rj))
                        self.counts['check'] += 1
                        self.counts['join_by_analogy'] += 1
                        self.methods['check'][0] += int(ok)
                        self.methods['check'][1] += 1
                        self.log(event='ask_check', why='unheard word read as joining', unknown=r['unknown'], ok=ok)
                        if ok:
                            return self._result(rj, view)""")
p.write_bytes(s.encode('utf-8'))
print('v20 ok')
