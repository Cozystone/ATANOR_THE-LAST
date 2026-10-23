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

    def intent(self, aid, episode, step, tool, args, predicted):
        with self.db:
            self.db.execute('INSERT INTO actions VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                            (aid, episode, step, tool, json.dumps(list(args)), 'intended', time.time(), None, None, '',
                             json.dumps(predicted)))

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

    def close(self):
        self.db.close()
