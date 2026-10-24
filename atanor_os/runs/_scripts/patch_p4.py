import pathlib, sys
P = pathlib.Path(sys.argv[1])

# ---------------- core/journal.py: state snapshots on intents, episodes table, resume queries ----------------
p = P / 'atanor_os/core/journal.py'; s = p.read_text(encoding='utf-8')
old = """        self.db.execute('CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, at REAL, kind TEXT, data TEXT)')

    def intent(self, aid, episode, step, tool, args, predicted):
        with self.db:
            self.db.execute('INSERT INTO actions VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                            (aid, episode, step, tool, json.dumps(list(args)), 'intended', time.time(), None, None, '',
                             json.dumps(predicted)))
"""
new = """        self.db.execute('CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, at REAL, kind TEXT, data TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS episodes(id TEXT PRIMARY KEY, goal TEXT, root TEXT, meta TEXT, '
                        'status TEXT, started REAL, finished REAL, result TEXT)')
        cols = {r[1] for r in self.db.execute('PRAGMA table_info(actions)')}
        for c in ('pre', 'post'):                       # P4: optional state snapshots for intent/reality reconciliation
            if c not in cols:
                self.db.execute(f'ALTER TABLE actions ADD COLUMN {c} TEXT')

    def intent(self, aid, episode, step, tool, args, predicted, pre=None, post=None):
        with self.db:
            self.db.execute('INSERT INTO actions(id, episode, step, tool, args, status, intent_at, done_at, ok, error, '
                            'predicted, pre, post) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                            (aid, episode, step, tool, json.dumps(list(args)), 'intended', time.time(), None, None, '',
                             json.dumps(predicted), None if pre is None else json.dumps(pre),
                             None if post is None else json.dumps(post)))
"""
assert old in s; s = s.replace(old, new)
old = """    def counts(self):
        return dict(self.db.execute('SELECT status, COUNT(*) FROM actions GROUP BY status'))
"""
new = """    def counts(self):
        return dict(self.db.execute('SELECT status, COUNT(*) FROM actions GROUP BY status'))

    # --- episodes (P4 supervisor) ---
    def begin_episode(self, eid, goal_json, root, meta_json='{}'):
        with self.db:
            self.db.execute('INSERT INTO episodes VALUES(?,?,?,?,?,?,?,?)',
                            (eid, goal_json, root, meta_json, 'running', time.time(), None, None))

    def finish_episode(self, eid, status, result):
        with self.db:
            self.db.execute('UPDATE episodes SET status=?, finished=?, result=? WHERE id=?',
                            (status, time.time(), json.dumps(result, default=str), eid))

    def episode(self, eid):
        r = self.db.execute('SELECT id, goal, root, meta, status FROM episodes WHERE id=?', (eid,)).fetchone()
        return None if r is None else dict(zip(('id', 'goal', 'root', 'meta', 'status'), r))

    def open_episodes(self):
        return [dict(zip(('id', 'goal', 'root', 'meta', 'status'), r)) for r in
                self.db.execute("SELECT id, goal, root, meta, status FROM episodes WHERE status='running' ORDER BY started")]

    def episode_steps(self, eid):
        \"\"\"Number of steps already recorded for an episode (the next step index on resume).\"\"\"
        r = self.db.execute('SELECT MAX(step) FROM actions WHERE episode=?', (eid,)).fetchone()[0]
        return 0 if r is None else r + 1

    def count_episodes(self, any_status=False):
        \"\"\"Finished episodes (done or failed); any_status=True also counts the ones still running.\"\"\"
        q = 'SELECT COUNT(*) FROM episodes' + ('' if any_status else " WHERE status != 'running'")
        return self.db.execute(q).fetchone()[0]
"""
assert old in s; s = s.replace(old, new)
p.write_text(s, encoding='utf-8')

# ---------------- agent/loop.py: resumable start, optional state snapshots, crash hook ----------------
p = P / 'atanor_os/agent/loop.py'; s = p.read_text(encoding='utf-8')
old = """def run_episode(ws, goal, model, journal, episode_id, adapt=False):
"""
new = """class SimulatedCrash(BaseException):
    \"\"\"Test hook: the process dies between a real action and its verification (not an Exception on purpose,
    so the loop's 'outcome unknown' handling does not see it, exactly like a real kill).\"\"\"


def run_episode(ws, goal, model, journal, episode_id, adapt=False, start_step=0, record_states=False, fault=None):
    \"\"\"start_step > 0 resumes an episode whose earlier steps are already in the journal (P4 supervisor);
    record_states stores the pre-state and predicted post-state with each intent for later reconciliation;
    fault(step) may raise SimulatedCrash right after the real action (tests only).\"\"\"
"""
assert old in s; s = s.replace(old, new)
old = "    for step in range(goal.budget['actions']):\n"
new = "    for step in range(start_step, goal.budget['actions']):\n"
assert old in s; s = s.replace(old, new)
old = """        journal.intent(aid, episode_id, step, tool, args, {'status': status, 'ok': predicted is not None})
"""
new = """        journal.intent(aid, episode_id, step, tool, args, {'status': status, 'ok': predicted is not None},
                       pre=state if record_states else None, post=predicted if record_states else None)
"""
assert old in s; s = s.replace(old, new)
old = """            res = ws.execute(tool, args, goal.capabilities)
            journal.mark(aid, 'executed', res['ok'], res['error'])
            post = ws.observe(goal.universe)
"""
new = """            res = ws.execute(tool, args, goal.capabilities)
            if fault is not None:
                fault(step)
            journal.mark(aid, 'executed', res['ok'], res['error'])
            post = ws.observe(goal.universe)
"""
assert old in s; s = s.replace(old, new)
p.write_text(s, encoding='utf-8')

# ---------------- eval/run.py: supervise / crash subcommands ----------------
p = P / 'atanor_os/eval/run.py'; s = p.read_text(encoding='utf-8')
old = """def main(argv=None):
    ap = argparse.ArgumentParser(prog='atanor_os')
    sub = ap.add_subparsers(dest='cmd', required=True)
"""
new = """def cmd_supervise(a):
    from .supervise import run_supervisor
    summary = run_supervisor(a.root, a.body, a.experiences, a.episodes, adapt=not a.frozen, stop_file=a.stop_file)
    print(json.dumps(summary, default=str))


def cmd_crash(a):
    from .supervise import crash_test
    r = crash_test(a.root, a.body, a.experiences, a.episodes, a.kill_min, a.kill_max, seed=a.seed, max_restarts=a.max_restarts)
    (Path(a.root) / 'crash_report.json').write_text(json.dumps(r, indent=1, default=str), encoding='utf-8')
    print(json.dumps({'ok': r['ok'], 'crash_log': r['crash_log'], 'verify': r['verify']}, default=str))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='atanor_os')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sv = sub.add_parser('supervise', help='P4: run a stream of episodes under one durable, resumable journal')
    sv.add_argument('--root', required=True)
    sv.add_argument('--body', default='fs', choices=tuple(BODIES))
    sv.add_argument('--experiences', required=True, help='frozen exploration log (jsonl) the model starts from')
    sv.add_argument('--episodes', type=int, default=20)
    sv.add_argument('--frozen', action='store_true', help='no online learning during the stream')
    sv.add_argument('--stop-file', default=None)
    sv.set_defaults(func=cmd_supervise)
    cr = sub.add_parser('crash', help='P4: kill/restart the supervisor at random moments and verify from disk')
    cr.add_argument('--root', required=True)
    cr.add_argument('--body', default='fs', choices=tuple(BODIES))
    cr.add_argument('--experiences', required=True)
    cr.add_argument('--episodes', type=int, default=10)
    cr.add_argument('--kill-min', type=float, default=0.5)
    cr.add_argument('--kill-max', type=float, default=3.0)
    cr.add_argument('--seed', type=int, default=1)
    cr.add_argument('--max-restarts', type=int, default=200)
    cr.set_defaults(func=cmd_crash)
"""
assert old in s; s = s.replace(old, new)
old = """     'compare': cmd_compare}[a.cmd](a)"""
new = """     'compare': cmd_compare, 'supervise': cmd_supervise, 'crash': cmd_crash}[a.cmd](a)"""
assert old in s; s = s.replace(old, new)
p.write_text(s, encoding='utf-8')
print('p4 patched')
