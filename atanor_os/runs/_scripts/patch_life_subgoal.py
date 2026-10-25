"""v4: a per-object sub-goal keeps every path of the goal that belongs to that object (same base name), whether the
path is in 'must' or only in 'keep', plus their ancestors. Before, a copy's source (only in keep) was left out."""
import pathlib

p = pathlib.Path('atanor_os/agent/life.py')
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""        self.counts['subgoals'] += 1
        for l in goal.must:
            if not l.holds(state):
                group = [m for m in goal.must if set(m.args) & set(l.args) or m.args[0].rsplit('/', 1)[-1] == l.args[0].rsplit('/', 1)[-1]]
                sub = Goal(goal.id + '-sub', group, goal.keep, goal.capabilities, goal.budget, sorted({a for m in group for a in m.args}))
                return plan(state, sub, self.model, ws.actions(self._focus(sub)), avoid, cap)
        return p, pst""", """        self.counts['subgoals'] += 1
        for l in goal.must:
            if not l.holds(state):
                names = {a.rsplit('/', 1)[-1] for a in l.args}
                group = [m for m in goal.must if set(m.args) & set(l.args) or {a.rsplit('/', 1)[-1] for a in m.args} & names]
                paths = {a for m in group for a in m.args} | {q for q in goal.universe if q.rsplit('/', 1)[-1] in names}
                sub = Goal(goal.id + '-sub', group, goal.keep, goal.capabilities, goal.budget, sorted(paths))
                return plan(state, sub, self.model, ws.actions(self._focus(sub)), avoid, cap)
        return p, pst""")
p.write_bytes(s.encode('utf-8'))
print('ok')
