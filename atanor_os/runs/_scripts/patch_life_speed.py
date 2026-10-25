import pathlib

p = pathlib.Path('atanor_os/agent/life.py')
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""            f.write(json.dumps({'t': round(time.time(), 3), **kw}, default=str) + '\\n')""",
    """            f.write(json.dumps({'t': round(time.time(), 3), 'task': getattr(self, 'task_id', None), **kw}, default=str) + '\\n')""")
rep("""    def do(self, command, task_id):
        t = self._task()""", """    def do(self, command, task_id):
        self.task_id = task_id
        t = self._task()""")
rep("""    def _plan(self, ws, goal, avoid=frozenset()):""", """    def _plannable(self, goal):
        \"\"\"A cheap check used while experimenting: is there a plan within a small search budget?\"\"\"
        small = Goal(goal.id, goal.must, goal.keep, goal.capabilities, {**goal.budget, 'predictions': 20000, 'nodes': 120}, goal.universe)
        p, _ = self._plan(self.home, small)
        return bool(p)

    def _plan(self, ws, goal, avoid=frozenset()):""")
s = s.replace("""            p, _ = self._plan(self.home, goal)
            if p:
                self.log(event='experiment_resolved', how='analogy', lab_actions=len(proc))""", """            if self._plannable(goal):
                self.log(event='experiment_resolved', how='analogy', lab_actions=len(proc))""")
s = s.replace("""                p, _ = self._plan(self.home, goal)
                if p:
                    self.log(event='experiment_resolved', lab_actions=i + 1)""", """                if self._plannable(goal):
                    self.log(event='experiment_resolved', lab_actions=i + 1)""")
s = s.replace("""            p, _ = self._plan(self.home, goal)
            if p:
                self.log(event='experiment_resolved', lab_actions=i + 1)""", """            if self._plannable(goal):
                self.log(event='experiment_resolved', lab_actions=i + 1)""")
rep("""            labgoal = Goal(goal.id, goal.must, goal.keep, goal.capabilities, goal.budget, goal.universe)""",
    """            labgoal = Goal(goal.id, goal.must, goal.keep, goal.capabilities, {**goal.budget, 'predictions': 20000, 'nodes': 120}, goal.universe)""")
p.write_bytes(s.encode('utf-8'))
print('life ok', s.count('_plannable(goal)'))

e = pathlib.Path('atanor_os/eval/life_gen.py')
s = e.read_text(encoding='utf-8')
rep("""            f.write(json.dumps(r, default=str) + '\\n')
    return rows""", """            f.write(json.dumps(r, default=str) + '\\n')
    snap = root / 'snap' / f'd{day_no}'                      # end-of-day snapshot (debugging only; never read by the mind)
    for part in ('home', 'mind'):
        if (root / part).exists():
            shutil.copytree(root / part, snap / part, dirs_exist_ok=True)
    return rows""")
e.write_bytes(s.encode('utf-8'))
print('gen ok')
