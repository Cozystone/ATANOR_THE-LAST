"""v13: two confusions after a world change.
(1) A plan search stopped by its budget is not read as 'enough is known' when no known tool's learned effects make the
    kind of change the goal needs: then no budget would find a plan, so it is a gap in knowledge and the core experiments.
(2) After the person corrects a result and shows the change, the core tries once more with what it was just shown
    (and asks again), instead of leaving the request undone."""
import pathlib, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""            p, pst = self._plan(ws, goal, avoid)
            if not p and (pst['stop'] != 'exhausted' or pst.get('depth_hits')):""",
    """            p, pst = self._plan(ws, goal, avoid)
            if not p and (pst['stop'] != 'exhausted' or pst.get('depth_hits')) and not self._relevant_tools(goal):
                self.log(event='no_known_effect', task=task_id, stop=pst['stop'])
                pst = {**pst, 'stop': 'exhausted', 'depth_hits': 0}   # no known tool makes this change: a gap, not a budget stop
            if not p and (pst['stop'] != 'exhausted' or pst.get('depth_hits')):""")
rep("""            self._teach_from_demo(toks, command, interp_hint=interp)     # the counter-example corrects the words""",
    """            tt = self._taught = None
            if self._teach_from_demo(toks, command, interp_hint=interp):    # the counter-example corrects the words
                tt = self._taught if self._taught and self._taught['pid'] in self.patterns else None
            if tt is not None:
                again = {**interp, 'pid': tt['pid'], 'selected': tt['selected'], 'dest': tt['dest'], 'view_at_start': interp['view_at_start']}
                g2 = self._goal(again)
                if g2 is not None:                                   # try once more with what was just shown, and ask again
                    self.counts['retry_after_correction'] += 1
                    done = self._achieve(g2, task_id)
                    confirmed = self.user.confirm(command)
                    self.counts['confirm'] += 1
                    self.log(event='retry_after_correction', achieved=done, confirmed=confirmed)
                    if confirmed:
                        interp = again
                        self.lex.learn(toks, view_from_json(interp['view_at_start']), interp['pid'], interp['selected'], interp['dest'])
                        for w in set(toks) | set(self.lex.pairs(toks, interp['dest'])):
                            self.lex.confirmed[w] += 1
                            self.lex.confirmed[f"{w}|{interp['pid']}"] += 1""")
p.write_bytes(s.encode('utf-8'))
print('v13 ok')
