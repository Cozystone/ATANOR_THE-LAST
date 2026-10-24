"""Durable research supervisor and independent native-action replay verifier.

The learner proposes predictions, never completion/authority. Hashes and worker
separation are not an OS security sandbox or proof of correct learning.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import uuid

from .world import Action, Frame, Sandbox
from .model import Forecast
from .schema import bind_schema
from .relations import validate_spec


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _goal_data(goal):
    return json.loads(canonical(goal.to_dict()))


def encode_config(config):
    if set(config) - {'paths', 'initial', 'protected', 'operations', 'relation_spec', 'initial_links', 'context_initial'} or not {'paths', 'initial'} <= set(config):
        raise ValueError('unexpected body configuration fields')
    result = {'paths': list(config['paths']),
            'initial': {k: None if v is None else v.hex() for k, v in config['initial'].items()},
            'protected': sorted(config.get('protected', ())) }
    if 'operations' in config:
        result['operations'] = bind_schema(config['operations']).to_data()
    if 'relation_spec' in config:
        result['relation_spec'] = validate_spec(config['relation_spec'])
    if 'initial_links' in config:
        result['initial_links'] = dict(config['initial_links'])
    if 'context_initial' in config:
        result['context_initial'] = {k: None if v is None else v.hex() for k,v in config['context_initial'].items()}
    return result


def _complete(goal, evidence, initial, protected):
    return bool(goal.holds(evidence) and all(evidence[h] == initial[h] for h in protected))


def _history_encode(history):
    return [[frame.to_dict(), action.to_dict()] for frame, action in history]


def _history_decode(history):
    return [(Frame.from_dict(f), Action.from_dict(a)) for f, a in history]


class Episode:
    def __init__(self, path, body, goal, client, *, config, budget):
        if type(budget) is not int or budget < 0:
            raise ValueError('invalid action budget')
        self.body, self.goal, self.client = body, goal, client
        self.config, self.budget = encode_config(config), budget
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, kind TEXT, payload TEXT, digest TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT)')
        row = self.db.execute('SELECT payload FROM state WHERE id=1').fetchone()
        if row:
            self.state = json.loads(row[0])
            if (self.state['config'] != self.config or self.state['goal'] != _goal_data(goal) or
                    self.state['budget'] != budget or self.state['body_root'] != str(body.root)):
                raise ValueError('resume identity/configuration mismatch')
            if self.state['pending'] is not None:
                self._record('RECONCILE', {'frame': body.observe().to_dict(), 'evidence': body.evidence()})
                self._stop('interrupted')  # Do not retry either action or learning blindly.
            elif self.state['stop'] is None:
                client.restore(json.loads(canonical(self.state['model'])))
        else:
            frame, evidence = body.observe().to_dict(), body.evidence()
            model = json.loads(canonical(client.snapshot()))
            revision = model.get('revision')
            if type(revision) is not int or revision < 0:
                raise ValueError('invalid learner revision')
            self.state = {'config': self.config, 'goal': _goal_data(goal), 'budget': budget,
                          'episode_id': uuid.uuid4().hex,
                          'body_root': str(body.root), 'steps': 0, 'history': [], 'model': model,
                          'initial': evidence, 'frame': frame, 'evidence': evidence,
                          'observation_seq': 1, 'pending': None, 'stop': None}
            self._record('BEGIN', {'config': self.config, 'goal': _goal_data(goal), 'budget': budget,
                                  'episode_id': self.state['episode_id'],
                                  'frame': frame, 'evidence': evidence,
                                  'model_digest': digest(model), 'reported_revision': revision})

    def _record(self, kind, payload, **updates):
        with self.db:
            prev = self.db.execute('SELECT seq,digest FROM events ORDER BY seq DESC LIMIT 1').fetchone()
            seq, previous = (prev[0] + 1, prev[1]) if prev else (1, '')
            text = canonical(payload)
            sha = hashlib.sha256((previous + kind + text).encode()).hexdigest()
            self.state.update(updates)
            self.db.execute('INSERT INTO events VALUES(?,?,?,?)', (seq, kind, text, sha))
            self.db.execute('INSERT OR REPLACE INTO state VALUES(1,?)', (canonical(self.state),))
        return seq

    def _stop(self, reason):
        evidence = self.body.evidence()
        payload = {'reason': reason, 'steps': self.state['steps'], 'evidence': evidence,
                   'completed': _complete(self.goal, evidence, self.state['initial'], self.config['protected'])}
        self._record('STOP', payload, stop=payload)
        return payload

    def step(self):
        if self.state['stop'] is not None:
            return self.state['stop']
        evidence, frame = self.body.evidence(), self.body.observe()
        if evidence != self.state['evidence'] or frame.to_dict() != self.state['frame']:
            return self._stop('observation_mismatch')
        if _complete(self.goal, evidence, self.state['initial'], self.config['protected']):
            return self._stop('goal_reached')
        if self.state['steps'] >= self.budget:
            return self._stop('step_budget_exceeded')
        history = _history_decode(self.state['history'])
        actions = self.body.actions()
        try:
            result = self.client.choose(Frame.from_dict(frame.to_dict()), self.goal, list(actions),
                                        _history_decode(_history_encode(history)))
            if result is None:
                return self._stop('policy_abstained')
            if type(result) is not tuple or len(result) != 3:
                raise ValueError('invalid proposal shape')
            action, forecast, nodes = result
            if type(action) is not Action or action not in actions or type(nodes) is not int or nodes < 0:
                raise ValueError('invalid action or planning count')
            prediction = Forecast.from_dict(forecast.to_dict())
            if prediction.handles != frame.handles or prediction.parent != frame.parent:
                raise ValueError('prediction scope mismatch')
            self.body._validate(action)
        except Exception:
            return self._stop('invalid_proposal')
        payload = {'action': action.to_dict(), 'forecast': prediction.to_dict(), 'nodes': nodes,
                   'source': self.state['observation_seq'], 'step': self.state['steps'],
                   'goal_id': self.goal.id, 'reported_revision': self.state['model']['revision']}
        seq = self._record('FORECAST', payload, pending={'phase': 'proposed'})
        self._record('DISPATCH', {'forecast': seq, 'step': self.state['steps'] + 1},
                     steps=self.state['steps'] + 1, pending={'phase': 'dispatched', 'forecast': seq})
        succeeded = self.body.step(action)
        after, evidence = self.body.observe(), self.body.evidence()
        result_payload = {'forecast': seq, 'operation_success': succeeded,
                          'frame': after.to_dict(), 'evidence': evidence,
                          'completed': _complete(self.goal, evidence, self.state['initial'], self.config['protected'])}
        observation = self._record('RESULT', result_payload, frame=after.to_dict(), evidence=evidence)
        event_id = f'{self.state["episode_id"]}:action:{observation}'
        try:
            accepted = self.client.learn(event_id, Frame.from_dict(frame.to_dict()), action,
                                         Frame.from_dict(after.to_dict()),
                                         _history_decode(_history_encode(history)))
            model = json.loads(canonical(self.client.snapshot()))
            if (accepted is not True or type(model.get('revision')) is not int or
                    model['revision'] != self.state['model']['revision'] + 1):
                raise ValueError('missing learner update acknowledgement')
        except Exception:
            return self._stop('learner_error')
        self._record('REVISION', {'forecast': seq, 'observation': observation, 'event_id': event_id,
                                 'model_digest': digest(model), 'reported_revision': model['revision']},
                     model=model, history=_history_encode((history + [(frame, action)])[-3:]),
                     observation_seq=observation, pending=None)
        return result_payload

    def run(self):
        while self.state['stop'] is None:
            self.step()
        return self.state['stop']

    def close(self):
        self.db.close()


def verify_episode(path, *, expected_config, expected_goal, expected_budget):
    """Replay native operations from externally supplied configuration, not trace authority."""
    errors = []
    steps, completed = 0, False
    try:
        db = sqlite3.connect('file:' + Path(path).resolve().as_posix() + '?mode=ro', uri=True)
        rows = list(db.execute('SELECT seq,kind,payload,digest FROM events ORDER BY seq'))
        state = json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
        db.close()
        previous = ''
        for number, (seq, kind, text, sha) in enumerate(rows, 1):
            if seq != number or sha != hashlib.sha256((previous + kind + text).encode()).hexdigest():
                errors.append('chain')
            previous = sha
        config = encode_config(expected_config)
        with tempfile.TemporaryDirectory(prefix='atanor_action_replay_') as temp:
            body = Sandbox(Path(temp) / 'body', **expected_config)
            frame, native = body.observe(), body.evidence()
            initial, observation = native, 1
            pending, phase, model_digest, reported_revision = None, 'begin', None, None
            history, stopped = [], False
            for seq, kind, text, _ in rows:
                p = json.loads(text)
                if stopped:
                    raise ValueError('event_after_stop')
                if kind == 'BEGIN':
                    if seq != 1 or phase != 'begin' or p['config'] != config or p['goal'] != _goal_data(expected_goal) or p['budget'] != expected_budget:
                        raise ValueError('external_binding')
                    if p['frame'] != frame.to_dict() or p['evidence'] != native:
                        raise ValueError('initial_observation')
                    episode_id = p['episode_id']
                    if uuid.UUID(hex=episode_id).hex != episode_id:
                        raise ValueError('episode_identity')
                    model_digest, reported_revision, phase = p['model_digest'], p['reported_revision'], 'ready'
                elif kind == 'FORECAST':
                    if phase != 'ready' or steps >= expected_budget or _complete(expected_goal, native, initial, config['protected']):
                        raise ValueError('forecast_order_or_budget')
                    if set(p) != {'action', 'forecast', 'nodes', 'source', 'step', 'goal_id', 'reported_revision'}:
                        raise ValueError('proposal_metadata')
                    pred = Forecast.from_dict(p['forecast'])
                    action = Action.from_dict(p['action'])
                    if (action not in body.actions() or pred.handles != frame.handles or pred.parent != frame.parent or
                            p['source'] != observation or p['step'] != steps or p['goal_id'] != expected_goal.id or
                            p['reported_revision'] != reported_revision or type(p['nodes']) is not int or p['nodes'] < 0):
                        raise ValueError('proposal_binding')
                    pending, phase = (seq, action, frame), 'proposed'
                elif kind == 'DISPATCH':
                    if phase != 'proposed' or p != {'forecast': pending[0], 'step': steps + 1} or steps >= expected_budget:
                        raise ValueError('dispatch_order_or_budget')
                    succeeded = body.step(pending[1])
                    steps += 1
                    frame, native, phase = body.observe(), body.evidence(), 'dispatched'
                elif kind == 'RESULT':
                    actual = {'forecast': pending[0], 'operation_success': succeeded,
                              'frame': frame.to_dict(), 'evidence': native,
                              'completed': _complete(expected_goal, native, initial, config['protected'])}
                    if phase != 'dispatched' or p != actual:
                        raise ValueError('actual_result_mismatch')
                    observation, phase = seq, 'observed'
                elif kind == 'REVISION':
                    if (phase != 'observed' or p['forecast'] != pending[0] or p['observation'] != observation or
                            p['event_id'] != f'{episode_id}:action:{observation}' or p['reported_revision'] != reported_revision + 1):
                        raise ValueError('revision_binding')
                    history = (history + [(pending[2], pending[1])])[-3:]
                    model_digest, reported_revision, phase, pending = p['model_digest'], p['reported_revision'], 'ready', None
                elif kind == 'STOP':
                    completed = _complete(expected_goal, native, initial, config['protected'])
                    if phase != 'ready' or p['steps'] != steps or p['evidence'] != native or p['completed'] is not completed:
                        raise ValueError('unverified_stop')
                    reason = p['reason']
                    if reason == 'goal_reached' and not completed:
                        raise ValueError('false_completion')
                    if reason == 'step_budget_exceeded' and (steps != expected_budget or completed):
                        raise ValueError('false_budget_stop')
                    if reason not in {'goal_reached', 'step_budget_exceeded', 'policy_abstained', 'invalid_proposal'}:
                        raise ValueError('incomplete_episode')
                    if completed and reason != 'goal_reached':
                        raise ValueError('wrong_stop_reason')
                    stopped = True
                    if state['stop'] != p:
                        raise ValueError('durable_stop')
                else:
                    raise ValueError('unexpected_or_interrupted_event')
            if (not stopped or state['pending'] is not None or state['steps'] != steps or state['episode_id'] != episode_id or
                    state['config'] != config or state['goal'] != _goal_data(expected_goal) or state['budget'] != expected_budget or
                    state['frame'] != frame.to_dict() or state['evidence'] != native or state['initial'] != initial or
                    state['observation_seq'] != observation or state['history'] != _history_encode(history) or
                    digest(state['model']) != model_digest or state['model']['revision'] != reported_revision):
                raise ValueError('durable_state_mismatch')
    except Exception as exc:
        errors.append(str(exc) or type(exc).__name__)
    return {'green': not errors, 'errors': errors, 'steps': steps, 'completed': completed}
