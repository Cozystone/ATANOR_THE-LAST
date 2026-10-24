"""Supervisor glue for a fixed multi-episode agenda, not a new cognition organ.

Life(root, body_root, agenda, client, initial_checkpoint=..., overall_budget=...,
     mode='carry'|'reset'|'frozen'). Each agenda item has config, Goal, budget.
step() advances at most one native action; run(max_episodes=None) continues until
the agenda, total budget, requested episode boundary, or a fail-closed stop.
COMPLETE means agenda execution ended, not that every goal succeeded; inspect
each episode's native stop.completed. Its db_path exposes the complete trace.

The external agenda/roots/base checkpoint bind a persistent manifest. Actual
DISPATCH events, not life-side counters or caller success, determine expenditure.
Completed episodes must independently replay before their model state is carried.
Model/replay persistence is not a claim of unified world identity, general Self,
capability, or safe execution of hostile code. The caller owns Client lifetime.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from .episode import Episode, canonical, digest, encode_config, verify_episode
from .planner import Goal
from .world import Sandbox, _no_links


def _copy(value):
    return json.loads(canonical(value))


def _decode(config):
    return {'paths': list(config['paths']),
            'initial': {p: None if value is None else bytes.fromhex(value)
                        for p, value in config['initial'].items()},
            'protected': set(config['protected'])}


class Life:
    def __init__(self, root, body_root, agenda, client, *, initial_checkpoint,
                 overall_budget, mode='carry'):
        self.db = self._lease = self._active = None
        self._verified = {}
        self.client = client
        if mode not in ('carry', 'reset', 'frozen') or type(overall_budget) is not int or overall_budget < 0:
            raise ValueError('invalid life mode or overall action budget')
        if type(agenda) not in (list, tuple) or not agenda:
            raise ValueError('nonempty externally fixed agenda required')
        self.root, self.body_root = Path(root).absolute(), Path(body_root).absolute()
        for path in (self.root, self.body_root):
            _no_links(path)
        self.root, self.body_root = self.root.resolve(), self.body_root.resolve()
        temp = Path(tempfile.gettempdir()).resolve()
        if self.body_root == temp or not self.body_root.is_relative_to(temp) or self.root == self.body_root:
            raise ValueError('body root must be a distinct owned child of process TEMP')
        self.agenda = []
        for item in agenda:
            if type(item) is not dict or set(item) != {'config', 'goal', 'budget'}:
                raise ValueError('agenda fields must be exactly config, goal, budget')
            if type(item['goal']) is not Goal or type(item['budget']) is not int or item['budget'] < 1:
                raise ValueError('invalid agenda goal or budget')
            config = encode_config(item['config'])
            item['goal'].validate_handles(tuple(f'n{i}' for i in range(len(config['paths']))))
            self.agenda.append({'config': config, 'goal': _copy(item['goal'].to_dict()), 'budget': item['budget']})
        self.base = _copy(initial_checkpoint)
        if type(self.base) is not dict or type(self.base.get('revision')) is not int or self.base['revision'] < 0:
            raise ValueError('invalid initial checkpoint')
        if mode == 'frozen':
            if 'weights' not in self.base or 'updates' not in self.base:
                raise ValueError('frozen mode requires a weight/update checkpoint')
            self.base['updates'] = 0
        self.mode, self.overall_budget = mode, overall_budget
        self.manifest = {'schema': 1, 'root': str(self.root), 'body_root': str(self.body_root),
                         'agenda': self.agenda, 'base_digest': digest(self.base),
                         'mode': mode, 'overall_budget': overall_budget}
        fresh = not self.root.exists()
        if fresh:
            if self.body_root.exists() or not self.root.parent.is_dir() or not self.body_root.parent.is_dir():
                raise ValueError('new life needs new body root and existing parent directories')
            self.root.mkdir()
        elif not (self.root / 'life.sqlite').is_file():
            raise ValueError('ambiguous existing life directory; never reinitialize')
        try:
            self._acquire()
            db_path = self.root / 'life.sqlite'
            _no_links(db_path)
            self.db = sqlite3.connect(db_path)
            self.db.execute('PRAGMA synchronous=FULL')
            if fresh:
                with self.db:
                    self.db.execute('CREATE TABLE manifest(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT)')
                    self.db.execute('CREATE TABLE episodes(idx INTEGER PRIMARY KEY, phase TEXT NOT NULL)')
                    self.db.execute('CREATE TABLE blocked(id INTEGER PRIMARY KEY CHECK(id=1), reason TEXT)')
                    self.db.execute('INSERT INTO manifest VALUES(1,?)', (canonical(self.manifest),))
                self.body_root.mkdir()
            else:
                stored = self.db.execute('SELECT payload FROM manifest WHERE id=1').fetchone()
                if not stored or stored[0] != canonical(self.manifest):
                    raise ValueError('external life manifest mismatch; no budget/goal/checkpoint reset')
                if not self.body_root.is_dir():
                    self._block('missing owned body root')
        except BaseException:
            self.close()
            raise

    def _acquire(self):
        """Cooperating-process exclusivity, not a caller-created capability token."""
        lock = self.root / 'runner.lock'
        _no_links(lock)
        self._lease = lock.open('a+b')
        if lock.stat().st_size == 0:
            self._lease.write(b'0')
            self._lease.flush()
        self._lease.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self._lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError('another life runner owns this agenda') from error

    def _paths(self, index):
        return self.root / f'episode-{index:04d}.sqlite', self.body_root / f'episode-{index:04d}'

    def _block(self, reason):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO blocked VALUES(1,?)', (str(reason),))

    def _read(self, index, budget, expected_model):
        path, body_path = self._paths(index)
        _no_links(path)
        if not path.is_file():
            raise ValueError('missing authoritative episode database')
        db = sqlite3.connect('file:' + path.as_posix() + '?mode=ro', uri=True)
        try:
            events = list(db.execute('SELECT seq,kind,payload,digest FROM events ORDER BY seq'))
            state = json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
        finally:
            db.close()
        previous, dispatches, phase, last_model = '', 0, 'new', None
        transitions = {'new': {'BEGIN': 'ready'}, 'ready': {'FORECAST': 'proposed', 'STOP': 'stopped'},
                       'proposed': {'DISPATCH': 'dispatched', 'RECONCILE': 'interrupted'},
                       'dispatched': {'RESULT': 'observed', 'RECONCILE': 'interrupted'},
                       'observed': {'REVISION': 'ready', 'STOP': 'stopped', 'RECONCILE': 'interrupted'},
                       'interrupted': {'STOP': 'stopped'}, 'stopped': {}}
        for number, (seq, kind, text, sha) in enumerate(events, 1):
            if seq != number or sha != hashlib.sha256((previous + kind + text).encode()).hexdigest():
                raise ValueError('episode chain mismatch')
            previous = sha
            if kind not in transitions[phase]:
                raise ValueError('episode call order mismatch')
            phase = transitions[phase][kind]
            payload = json.loads(text)
            if kind == 'DISPATCH':
                dispatches += 1
                if payload.get('step') != dispatches or dispatches > budget:
                    raise ValueError('native dispatch budget mismatch')
            if kind in ('BEGIN', 'REVISION'):
                last_model = payload.get('model_digest')
            if kind == 'BEGIN' and payload.get('model_digest') != digest(expected_model):
                raise ValueError('cross-episode checkpoint lineage mismatch')
        item = self.agenda[index]
        if (not events or state['config'] != item['config'] or state['goal'] != item['goal'] or
                state['budget'] != budget or state['body_root'] != str(body_path) or
                type(state['steps']) is not int or state['steps'] != dispatches or
                digest(state['model']) != last_model):
            raise ValueError('episode scope/checkpoint/step binding mismatch')
        if phase == 'ready' and (state['pending'] is not None or state['stop'] is not None):
            raise ValueError('ready episode has contradictory pending/stop state')
        if phase in ('proposed', 'dispatched', 'observed') and state['pending'] is None:
            raise ValueError('unresolved native dispatch was hidden')
        if phase == 'stopped' and state['stop'] != json.loads(events[-1][2]):
            raise ValueError('native stop/state mismatch')
        return state, dispatches, previous

    def _scan(self):
        entries = list(self.db.execute('SELECT idx,phase FROM episodes ORDER BY idx'))
        if [i for i, _ in entries] != list(range(len(entries))) or len(entries) > len(self.agenda):
            raise ValueError('episode sequence missing/duplicated/outside agenda')
        used, model, results = 0, self.base, []
        for position, (index, phase) in enumerate(entries):
            if phase not in ('creating', 'active', 'done') or (phase != 'done' and position != len(entries)-1):
                raise ValueError('ambiguous life phase')
            if phase == 'creating':
                raise ValueError('ambiguous episode creation; inspect before any continuation')
            limit = min(self.agenda[index]['budget'], self.overall_budget - used)
            if limit < 1:
                raise ValueError('episode started after global action budget exhaustion')
            incoming = self.base if self.mode == 'reset' else model
            state, charged, chain_tip = self._read(index, limit, incoming)
            if phase == 'done':
                if state['stop'] is None or state['stop']['reason'] not in ('goal_reached', 'step_budget_exceeded'):
                    raise ValueError('life metadata cannot manufacture episode completion')
                key = (index, chain_tip, digest(state))
                if key not in self._verified:
                    result = verify_episode(self._paths(index)[0],
                        expected_config=_decode(self.agenda[index]['config']),
                        expected_goal=Goal.from_dict(self.agenda[index]['goal']), expected_budget=limit)
                    if not result['green'] or result['steps'] != charged:
                        raise ValueError('independent episode replay failed: ' + str(result['errors']))
                    self._verified[key] = True
            if self.mode == 'frozen' and state['model'].get('weights') != self.base['weights']:
                raise ValueError('frozen weights changed')
            used += charged
            model = state['model']
            results.append({'index': index, 'phase': phase, 'state': state, 'budget': limit,
                            'steps': charged, 'model_digest': digest(model)})
        return results, used, model

    def _summary(self, status, results, used, reason=None):
        return {'status': status, 'mode': self.mode, 'steps_used': used,
                'remaining_budget': self.overall_budget - used,
                'episodes': [{'index': row['index'], 'phase': row['phase'], 'steps': row['steps'],
                              'db_path': str(self._paths(row['index'])[0]),
                              'body_root': str(self._paths(row['index'])[1]),
                              'goal_id': self.agenda[row['index']]['goal']['id'],
                              'stop': row['state']['stop'], 'checkpoint_digest': row['model_digest']}
                             for row in results], 'reason': reason}

    def step(self):
        try:
            results, used, model = self._scan()
        except Exception as error:
            self._block(error)
            return {'status': 'BLOCKED', 'reason': str(error), 'steps_used': None}
        blocked = self.db.execute('SELECT reason FROM blocked WHERE id=1').fetchone()
        if blocked:
            return self._summary('BLOCKED', results, used, blocked[0])
        if results and results[-1]['phase'] == 'active':
            index, limit = results[-1]['index'], results[-1]['budget']
            if self._active is None:
                item = self.agenda[index]
                path, body_path = self._paths(index)
                try:
                    body = Sandbox.attach(body_path, item['config']['paths'], set(item['config']['protected']))
                    self._active = Episode(path, body, Goal.from_dict(item['goal']), self.client,
                                           config=_decode(item['config']), budget=limit)
                except Exception as error:
                    self._block(error)
                    return self._summary('BLOCKED', results, used, str(error))
        else:
            index = len(results)
            if index == len(self.agenda):
                return self._summary('COMPLETE', results, used)
            if used >= self.overall_budget:
                return self._summary('BUDGET_EXHAUSTED', results, used)
            path, body_path = self._paths(index)
            if path.exists() or body_path.exists():
                self._block('ambiguous preexisting episode artifacts')
                return self._summary('BLOCKED', results, used, 'ambiguous preexisting episode artifacts')
            limit = min(self.agenda[index]['budget'], self.overall_budget - used)
            incoming = self.base if self.mode == 'reset' else model
            self.client.restore(_copy(incoming))
            if digest(self.client.snapshot()) != digest(incoming):
                self._block('learner restoration mismatch')
                return self._summary('BLOCKED', results, used, 'learner restoration mismatch')
            with self.db:
                self.db.execute('INSERT INTO episodes VALUES(?,?)', (index, 'creating'))
            item = self.agenda[index]
            try:
                body = Sandbox(body_path, **_decode(item['config']))
                self._active = Episode(path, body, Goal.from_dict(item['goal']), self.client,
                                       config=_decode(item['config']), budget=limit)
                with self.db:
                    self.db.execute('UPDATE episodes SET phase=? WHERE idx=?', ('active', index))
            except Exception as error:
                self._block(error)
                return self._summary('BLOCKED', results, used, str(error))
        self._active.step()
        stop = self._active.state['stop']
        if stop is not None:
            if stop['reason'] not in ('goal_reached', 'step_budget_exceeded'):
                self._block('episode stopped without a verified boundary: ' + stop['reason'])
            else:
                # Replay first; a life-side phase is never a success certificate.
                item = self.agenda[index]
                result = verify_episode(self._paths(index)[0], expected_config=_decode(item['config']),
                    expected_goal=Goal.from_dict(item['goal']), expected_budget=limit)
                if not result['green']:
                    self._block('independent episode replay failed: ' + str(result['errors']))
                else:
                    with self.db:
                        self.db.execute('UPDATE episodes SET phase=? WHERE idx=?', ('done', index))
            self._active.close()
            self._active = None
        try:
            results, used, _ = self._scan()
        except Exception as error:
            self._block(error)
            return {'status': 'BLOCKED', 'reason': str(error), 'steps_used': None}
        blocked = self.db.execute('SELECT reason FROM blocked WHERE id=1').fetchone()
        status = 'BLOCKED' if blocked else 'COMPLETE' if len(results) == len(self.agenda) and all(r['phase'] == 'done' for r in results) else 'RUNNING'
        return self._summary(status, results, used, blocked[0] if blocked else None)

    def run(self, max_episodes=None):
        if max_episodes is not None and (type(max_episodes) is not int or max_episodes < 1):
            raise ValueError('max_episodes must be a positive integer')
        before = self.db.execute("SELECT COUNT(*) FROM episodes WHERE phase='done'").fetchone()[0]
        while True:
            result = self.step()
            if result['status'] != 'RUNNING':
                return result
            done = sum(r['phase'] == 'done' for r in result['episodes'])
            if max_episodes is not None and done - before >= max_episodes:
                return dict(result, status='PAUSED')

    def checkpoint(self):
        """Export only a replay-verified completed boundary, never an unresolved action."""
        results, _, model = self._scan()
        if self.db.execute('SELECT 1 FROM blocked').fetchone() or any(r['phase'] != 'done' for r in results):
            raise ValueError('no verified completed boundary is available')
        return _copy(model)

    def close(self):
        if self._active is not None:
            self._active.close()
            self._active = None
        if self.db is not None:
            self.db.close()
            self.db = None
        if self._lease is not None:
            self._lease.close()
            self._lease = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
