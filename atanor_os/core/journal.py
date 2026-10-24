"""Durable action records (charter §7): intent → executed → verified, plus experiences and events.

SQLite WAL with synchronous=FULL. This records what was intended and what was verified; it does
not make an external action and its record one atomic transaction (see charter §7).
"""
import json
import sqlite3
import time


class Journal:
    def __init__(self, path):
        self.path = str(path)
        self.db = sqlite3.connect(self.path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY, episode TEXT, step INTEGER, '
                        'tool TEXT, args TEXT, status TEXT, intent_at REAL, done_at REAL, ok INTEGER, error TEXT, predicted TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS experiences(id TEXT PRIMARY KEY, episode TEXT, data TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, at REAL, kind TEXT, data TEXT)')
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

    def mark(self, aid, status, ok=None, error=''):
        with self.db:
            self.db.execute('UPDATE actions SET status=?, done_at=?, ok=?, error=? WHERE id=?',
                            (status, time.time(), None if ok is None else int(ok), error, aid))

    def experience(self, exp, episode):
        with self.db:
            self.db.execute('INSERT INTO experiences VALUES(?,?,?)', (exp.id, episode, json.dumps(exp.to_json())))

    def event(self, kind, data):
        with self.db:
            self.db.execute('INSERT INTO events(at, kind, data) VALUES(?,?,?)', (time.time(), kind, json.dumps(data)))

    def unresolved(self):
        """Actions whose outcome was never verified: intent/reality must be reconciled before reuse."""
        return list(self.db.execute("SELECT id, episode, step, tool, args, status FROM actions "
                                    "WHERE status IN ('intended', 'executed', 'unknown') ORDER BY intent_at"))

    def counts(self):
        return dict(self.db.execute('SELECT status, COUNT(*) FROM actions GROUP BY status'))

    # --- episodes (P4 supervisor) ---
    def begin_episode(self, eid, goal_json, root, meta_json='{}', status='running'):
        with self.db:
            self.db.execute('INSERT INTO episodes VALUES(?,?,?,?,?,?,?,?)',
                            (eid, goal_json, root, meta_json, status, time.time(), None, None))

    def start_episode(self, eid, goal_json, root, meta_json='{}'):
        """A 'preparing' episode (row written before its workspace was made) becomes 'running'."""
        with self.db:
            self.db.execute("UPDATE episodes SET goal=?, root=?, meta=?, status='running', started=? WHERE id=?",
                            (goal_json, root, meta_json, time.time(), eid))

    def episodes_with_status(self, status):
        return [dict(zip(('id', 'goal', 'root', 'meta', 'status'), r)) for r in
                self.db.execute('SELECT id, goal, root, meta, status FROM episodes WHERE status=? ORDER BY started', (status,))]

    def delete_episode(self, eid):
        with self.db:
            self.db.execute('DELETE FROM episodes WHERE id=?', (eid,))

    def verify(self, aid, ok, error, exp, episode):
        """Verification and its experience in ONE transaction: a kill cannot leave one without the other."""
        with self.db:
            self.db.execute('UPDATE actions SET status=?, done_at=?, ok=?, error=? WHERE id=?',
                            ('verified', time.time(), int(ok), error, aid))
            self.db.execute('INSERT INTO experiences VALUES(?,?,?)', (exp.id, episode, json.dumps(exp.to_json())))

    def episode_totals(self, eid):
        """Actions really performed for an episode across all its processes, and how many of them failed."""
        r = self.db.execute("SELECT COUNT(*), COALESCE(SUM(CASE WHEN ok=0 THEN 1 ELSE 0 END), 0) FROM actions "
                            "WHERE episode=? AND status IN ('verified', 'reconciled')", (eid,)).fetchone()
        return {'actions_total': r[0], 'noops_total': r[1]}

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
        """Number of steps already recorded for an episode (the next step index on resume)."""
        r = self.db.execute('SELECT MAX(step) FROM actions WHERE episode=?', (eid,)).fetchone()[0]
        return 0 if r is None else r + 1

    def count_episodes(self, any_status=False):
        """Finished episodes (done or failed); any_status=True also counts the ones still running."""
        q = 'SELECT COUNT(*) FROM episodes' + ('' if any_status else " WHERE status != 'running'")
        return self.db.execute(q).fetchone()[0]

    def close(self):
        self.db.close()
