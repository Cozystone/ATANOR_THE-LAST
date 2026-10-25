"""v12: unfinished goals. A command the core gave up on with nobody to ask is kept in mind/pending.json (raw command,
why, when). When a person is present again, the core brings each unfinished goal up, oldest first: it asks whether it
is still wanted and, if so, works on it with the usual asking/experimenting; either way the goal leaves the list (the
person has now heard it). The core does not act on a stale goal alone: the home may have changed since it was asked."""
import pathlib, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""    # ---- one command, start to finish (resumable)
    def do(self, command, task_id):""", """    # ---- unfinished goals (kept across restarts until a person has heard them)
    def pending_goals(self):
        p = self.dir / 'pending.json'
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else []

    def _set_pending(self, goals):
        (self.dir / 'pending.json').write_text(json.dumps(goals, indent=1), encoding='utf-8')

    def resume(self, goal):
        \"\"\"With a person present: bring up one unfinished goal. Returns None if it is no longer wanted.\"\"\"
        self._set_pending([g for g in self.pending_goals() if g['id'] != goal['id']])
        if self.user is None:
            raise ValueError('an unfinished goal is only resumed with the person')
        wanted = self.user.still_wanted(goal['command'])
        self.counts['recall'] += 1
        self.log(event='recall', goal=goal['id'], wanted=wanted)
        if not wanted:
            return None
        return self.do(goal['command'], goal['id'] + '/r')

    # ---- one command, start to finish (resumable)
    def do(self, command, task_id):
        r = self._do(command, task_id)
        why = r.get('reason') or ('not achieved' if r.get('achieved') is False else None)
        if why in ('not understood', 'no goal', 'not achieved') and self.user is None and not task_id.endswith('/r'):
            goals = [g for g in self.pending_goals() if g['id'] != task_id]
            self._set_pending(goals + [{'id': task_id, 'command': command, 'why': why}])
            self.log(event='unfinished', goal=task_id, why=why)
        return r

    def _do(self, command, task_id):""")
p.write_bytes(s.encode('utf-8'))
print('v12 ok')
