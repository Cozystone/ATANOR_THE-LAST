"""Persistent supervisor-owned world over an unchanged native body.

D1: one world owns successive goals and dated observations. A Frame is a
complete, scoped *locator view*, not persistent file identity or general 4D
perception. External changes become observations; pending side effects never
get blindly repeated. The JSON learner is untrusted for authority/completion.
The host process, authorized configuration and OS are trusted in this research
threat model. This is not a hostile-host or cross-machine security sandbox.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time

from packages.action_core.episode import canonical, digest, encode_config
from packages.action_core.planner import Goal
from packages.action_core.world import Action, Frame, Sandbox
from .contracts import parse_execution_prediction as parse_prediction


def clone(value):
    return json.loads(canonical(value))


def _actual(body):
    # Separate native acquisition; no evidence/status fields from a learner.
    return body.observe().to_dict(), body.evidence()


def _complete(goal, evidence, initial, protected, observed=None):
    # Only supervisor-acquired observations (or independent native replay) enter
    # here. A forecast never supplies relational completion evidence.
    if not all(evidence[h] == initial[h] for h in protected):
        return False
    if not goal.relations:
        return goal.holds(evidence)
    if observed is None:
        return False
    frame = Frame.from_dict(observed)
    if goal.kinds or goal.equal or goal.sizes:
        if not Goal(goal.id, goal.kinds, goal.equal, goal.sizes).holds(evidence):
            return False
    return all(channel in frame.relations
        and frame.relations[channel][frame.handles.index(left)][frame.handles.index(right)] == wanted
        for channel, left, right, wanted in goal.relations)


def _validate_body(body, config):
    if type(body) is not Sandbox:
        raise ValueError('D1 requires the authorized native adapter')
    body_config = {
        'paths': [body._paths[h].relative_to(body.root).as_posix() for h in body.handles],
        'protected': sorted(body.protected),
        'operations': body.schema.to_data(),
    }
    if (body_config['paths'] != config['paths']
            or body_config['protected'] != config['protected']
            or body_config['operations'] != config['operations']):
        raise ValueError('native body differs from supervisor configuration')
    if (body.relation_spec != config.get('relation_spec') or
            body.initial_links != config.get('initial_links', {}) or
            {k: None if v is None else v.hex() for k,v in body.context_initial.items()} != config.get('context_initial', {})):
        raise ValueError('native sensor/link configuration differs from supervisor binding')


def _read(db):
    rows = list(db.execute('SELECT seq,kind,payload,digest FROM events ORDER BY seq'))
    row = db.execute('SELECT payload FROM state WHERE id=1').fetchone()
    state = json.loads(row[0]) if row else None
    previous = ''
    for number, (seq, kind, payload, sha) in enumerate(rows, 1):
        if seq != number or sha != hashlib.sha256((previous + kind + payload).encode()).hexdigest():
            raise ValueError('journal_chain_mismatch')
        previous = sha
    if bool(rows) != bool(state):
        raise ValueError('journal_state_presence_mismatch')
    if state and (state['head'] != previous or state['seq'] != len(rows)):
        raise ValueError('journal_state_head_mismatch')
    return rows, state


def _check_resume_state(rows, state):
    """Check mutable checkpoint against the journal, not against its own claims.

    This detects checkpoint corruption; journal authenticity still relies on the
    trusted supervisor/storage. Native reexecution is a separate verification.
    """
    expected, model_digest, model_revision, prediction = None, None, None, None
    for seq, kind, text, _ in rows:
        p = json.loads(text)
        if kind == 'BEGIN':
            expected = {'binding': p['binding'], 'initial': p['evidence'],
                'frame': p['frame'], 'evidence': p['evidence'], 'observation_seq': 1,
                'world_revision': 1, 'observations': 1, 'steps': 0, 'decisions': 0,
                'active': None, 'goals': [], 'history': [], 'failed_attempts': [],
                'pending': None, 'halted': None}
            model_digest, model_revision = p['model_digest'], p['model_revision']
            if 'sensor_budget' in p['binding']:
                expected.update(sensing=0, last_sense=None)
        elif kind == 'OBSERVE':
            expected.update(frame=p['frame'], evidence=p['evidence'], observation_seq=seq,
                world_revision=expected['world_revision'] + 1, observations=expected['observations'] + 1)
        elif kind == 'GOAL':
            expected['active'] = len(expected['goals'])
            expected['goals'].append(p)
        elif kind == 'SENSE':
            expected.update(sensing=expected['sensing'] + p['cost'], last_sense=p)
        elif kind == 'DECIDE':
            expected['decisions'] += 1
        elif kind == 'PREDICT':
            prediction = [clone(expected['frame']), p['action'], clone(expected['evidence'])]
            expected['pending'] = {'phase': 'predicted'}
        elif kind == 'DISPATCH':
            expected.update(steps=expected['steps'] + 1,
                            pending={'phase': 'dispatched', 'prediction': p['prediction']})
        elif kind == 'RESULT':
            expected.update(frame=p['frame'], evidence=p['evidence'], observation_seq=seq,
                world_revision=expected['world_revision'] + 1, observations=expected['observations'] + 1,
                pending={'phase': 'observed', 'prediction': p['prediction']})
        elif kind == 'LEARN':
            expected['history'] = (expected['history'] + [prediction[:2]])[-256:]
            if prediction[0] == expected['frame'] and prediction[2] == expected['evidence']:
                expected['failed_attempts'] = (expected['failed_attempts'] + [prediction[:2]])[-256:]
            expected['pending'] = None
            model_digest, model_revision = p['model_digest'], p['model_revision']
        elif kind == 'GOAL_END':
            expected['goals'][expected['active']]['result'] = p
            expected['active'] = None
        elif kind == 'HALT':
            expected['halted'] = p['reason']
        elif kind == 'INTERRUPTED':
            expected['halted'] = 'pending_interrupted'
        else:
            raise ValueError('unknown_resume_event')
    if (expected is None or any(state.get(k) != v for k, v in expected.items())
            or digest(state['model']) != model_digest or state['model']['revision'] != model_revision
            or set(state) != set(expected) | {'model', 'seq', 'head'}):
        raise ValueError('resume_checkpoint_journal_mismatch')


class WorldSession:
    def __init__(self, path, body, client, *, config, total_budget,
                 world_id, self_id, decision_cap=None, sensor_budget=0, sensor_node_cap=8):
        if type(total_budget) is not int or total_budget < 0:
            raise ValueError('invalid total action budget')
        if (type(sensor_budget) is not int or sensor_budget < 0
                or type(sensor_node_cap) is not int or sensor_node_cap < 0):
            raise ValueError('invalid sensor budget')
        decision_cap = max(16, total_budget * 4) if decision_cap is None else decision_cap
        if type(decision_cap) is not int or decision_cap < 1:
            raise ValueError('invalid decision cap')
        if any(type(v) is not str or not v.strip() for v in (world_id, self_id)):
            raise ValueError('explicit world/self binding required')
        self.body, self.client = body, client
        config = encode_config(config)
        # Legacy configs omit an explicit schema for the four-operation body.
        if 'operations' not in config:
            config['operations'] = body.schema.to_data()
        _validate_body(body, config)
        self.binding = {'contract': 'shared-world-2', 'world_id': world_id, 'self_id': self_id, 'config': config,
                        'body_root': str(body.root), 'total_budget': total_budget,
                        'decision_cap': decision_cap}
        if sensor_budget:
            self.binding.update(sensor_budget=sensor_budget, sensor_node_cap=sensor_node_cap)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, kind TEXT, payload TEXT, digest TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT)')
        try:
            rows, self._state = _read(self.db)
            if self._state:
                if self._state['binding'].get('contract') != self.binding['contract']:
                    raise ValueError('unsupported prior world contract; no silent migration')
                _check_resume_state(rows, self._state)
                if self._state['binding'] != self.binding:
                    raise ValueError('resume_external_binding_mismatch')
                if self._state['pending'] is not None:
                    frame, evidence = _actual(body)
                    self._record('INTERRUPTED', {'frame': frame, 'evidence': evidence,
                                 'pending': self._state['pending']}, halted='pending_interrupted')
                elif not self._state['halted']:
                    client.restore(clone(self._state['model']))
            else:
                frame, evidence = _actual(body)
                model = clone(client.snapshot())
                self._check_model(model)
                self._state = {'binding': self.binding, 'model': model, 'initial': evidence,
                    'frame': frame, 'evidence': evidence, 'observation_seq': 1,
                    'world_revision': 1, 'observations': 1, 'steps': 0, 'decisions': 0,
                    'active': None, 'goals': [], 'history': [], 'failed_attempts': [], 'pending': None,
                    'halted': None, 'seq': 0, 'head': ''}
                if sensor_budget:
                    self._state.update(sensing=0, last_sense=None)
                self._record('BEGIN', {'binding': self.binding, 'frame': frame,
                    'evidence': evidence, 'observed_at_ns': time.time_ns(),
                    'model_digest': digest(model), 'model_revision': model['revision']})
        except Exception:
            self.db.close()
            raise

    @staticmethod
    def _check_model(model):
        if type(model) is not dict or type(model.get('revision')) is not int or model['revision'] < 0:
            raise ValueError('invalid model revision')

    @property
    def state(self):
        return clone(self._state)

    def _record(self, kind, payload, **updates):
        payload = clone(payload)
        with self.db:
            seq = self._state['seq'] + 1
            text = canonical(payload)
            sha = hashlib.sha256((self._state['head'] + kind + text).encode()).hexdigest()
            state = clone(self._state)
            state.update(clone(updates))
            state.update(seq=seq, head=sha)
            self.db.execute('INSERT INTO events VALUES(?,?,?,?)', (seq, kind, text, sha))
            self.db.execute('INSERT OR REPLACE INTO state VALUES(1,?)', (canonical(state),))
        self._state = state
        return seq

    def poll(self, *, reason='poll'):
        if self._state['pending'] is not None or self._state['halted']:
            raise ValueError('cannot observe into an unresolved world')
        frame, evidence = _actual(self.body)
        changed = frame != self._state['frame'] or evidence != self._state['evidence']
        payload = {'frame': frame, 'evidence': evidence, 'changed': changed,
                   'reason': reason, 'observed_at_ns': time.time_ns()}
        seq = self._state['seq'] + 1
        self._record('OBSERVE', payload, frame=frame, evidence=evidence,
                     observation_seq=seq, observations=self._state['observations'] + 1,
                     world_revision=self._state['world_revision'] + 1)
        return clone(payload)

    def issue_goal(self, goal, budget):
        if type(goal) is not Goal or type(budget) is not int or budget < 0:
            raise ValueError('invalid goal request')
        goal.validate_handles(self.body.handles)
        if self._state['active'] is not None or self._state['halted']:
            raise ValueError('world not ready for another goal')
        if any(g['goal']['id'] == goal.id for g in self._state['goals']):
            raise ValueError('goal identity already used')
        row = {'goal': goal.to_dict(), 'budget': budget, 'start_steps': self._state['steps'],
               'result': None}
        self._record('GOAL', row, active=len(self._state['goals']),
                     goals=self._state['goals'] + [row])

    def sense(self, handles):
        """Journal native expanded observation, never expand mutation authority.

Opt-in supervisor budget; costs one request plus newly exposed nodes. Results
are supplemental observations, not replacement frames or learned transitions.
"""
        from packages.action_core.observation_scope import observe_ancestors
        remaining = self.binding.get('sensor_budget', 0) - self._state.get('sensing', 0)
        if remaining < 1 or self._state['pending'] is not None or self._state['halted']:
            raise ValueError('sensor disabled, exhausted, or world unresolved')
        before, evidence = _actual(self.body)
        if before != self._state['frame'] or evidence != self._state['evidence']:
            raise ValueError('poll changed world before sensing')
        expanded, added = observe_ancestors(self.body, handles,
            max_new=min(remaining-1, self.binding['sensor_node_cap']))
        if _actual(self.body) != (before, evidence):
            raise ValueError('world changed during sensing')
        payload = dict(source=self._state['observation_seq'], handles=list(handles),
            frame=expanded.to_dict(), added=list(added), cost=1+len(added), observed_at_ns=time.time_ns())
        self._record('SENSE', payload, sensing=self._state['sensing']+payload['cost'], last_sense=payload)
        return clone(payload)

    def _finish(self, reason):
        active = self._state['active']
        row = self._state['goals'][active]
        goal = Goal.from_dict(row['goal'])
        # A new native read closes the goal; prediction is never used here.
        self.poll(reason='goal_end')
        done = _complete(goal, self._state['evidence'], self._state['initial'],
                         self.binding['config']['protected'], self._state['frame'])
        if done:
            reason = 'goal_reached'
        payload = {'goal_id': goal.id, 'reason': reason, 'completed': done,
                   'steps': self._state['steps'] - row['start_steps'],
                   'observation': self._state['observation_seq'],
                   'model_digest': digest(self._state['model'])}
        goals = clone(self._state['goals'])
        goals[active]['result'] = payload
        self._record('GOAL_END', payload, goals=goals, active=None)
        return clone(payload)

    def step(self):
        if self._state['halted']:
            return {'halted': self._state['halted']}
        if self._state['active'] is None:
            return {'idle': True}
        self.poll(reason='pre_decision')
        row = self._state['goals'][self._state['active']]
        goal = Goal.from_dict(row['goal'])
        if _complete(goal, self._state['evidence'], self._state['initial'],
                     self.binding['config']['protected'], self._state['frame']):
            return self._finish('goal_reached')
        if (self._state['steps'] >= self.binding['total_budget']
                or self._state['steps'] - row['start_steps'] >= row['budget']):
            return self._finish('step_budget_exceeded')
        if self._state['decisions'] >= self.binding['decision_cap']:
            return self._finish('decision_budget_exceeded')
        self._record('DECIDE', {'goal_id': goal.id, 'observation': self._state['observation_seq']},
                     decisions=self._state['decisions'] + 1)
        before = Frame.from_dict(clone(self._state['frame']))
        before_evidence = clone(self._state['evidence'])
        history = [(Frame.from_dict(f), Action.from_dict(a)) for f, a in self._state['history']]
        failed_attempts = [(Frame.from_dict(f), Action.from_dict(a))
                           for f, a in self._state['failed_attempts']]
        actions = self.body.actions()
        if not actions:
            return self._finish('no_valid_actions')
        try:
            # Do not expose our retained observation object even to a local
            # testing client. Production research client serializes this again.
            reply = self.client.choose(Frame.from_dict(clone(before.to_dict())), goal,
                                       list(actions), [(Frame.from_dict(clone(f.to_dict())), a)
                                                       for f, a in history],
                                       failed_attempts=failed_attempts)
            if reply is None:
                return self._finish('policy_abstained')
            if type(reply) is not tuple or len(reply) != 3:
                raise ValueError('invalid proposal shape')
            action, forecast, nodes = reply
            forecast = parse_prediction(clone(forecast.to_dict()))
            if (type(action) is not Action or action not in actions or type(nodes) is not int
                    or nodes < 1 or forecast.handles != before.handles or forecast.parent != before.parent
                    or forecast.relations.keys() != before.relations.keys()):
                raise ValueError('proposal scope mismatch')
            self.body._validate(action)
        except Exception:
            return self._finish('invalid_proposal')
        # Changes during computation invalidate this proposal, not the world.
        fresh_frame, fresh_evidence = _actual(self.body)
        if fresh_frame != self._state['frame'] or fresh_evidence != self._state['evidence']:
            self.poll(reason='changed_during_decision')
            return {'replan': True, 'reason': 'changed_during_decision'}
        payload = {'goal_id': goal.id, 'source': self._state['observation_seq'],
                   'world_revision': self._state['world_revision'],
                   'model_digest': digest(self._state['model']),
                   'model_revision': self._state['model']['revision'],
                   'action': action.to_dict(), 'prediction': forecast.to_dict(), 'nodes': nodes}
        forecast_seq = self._record('PREDICT', payload, pending={'phase': 'predicted'})
        self._record('DISPATCH', {'prediction': forecast_seq, 'step': self._state['steps'] + 1},
                     steps=self._state['steps'] + 1,
                     pending={'phase': 'dispatched', 'prediction': forecast_seq})
        succeeded = self.body.step(action)
        after, evidence = _actual(self.body)
        observation_seq = self._state['seq'] + 1
        self._record('RESULT', {'prediction': forecast_seq, 'succeeded': succeeded,
                     'frame': after, 'evidence': evidence, 'observed_at_ns': time.time_ns()},
                     frame=after, evidence=evidence, observation_seq=observation_seq,
                     observations=self._state['observations'] + 1,
                     world_revision=self._state['world_revision'] + 1,
                     pending={'phase': 'observed', 'prediction': forecast_seq})
        event_id = f"{self.binding['world_id']}:event:{observation_seq}"
        try:
            accepted = self.client.learn(event_id, Frame.from_dict(clone(before.to_dict())), action,
                Frame.from_dict(clone(after)), [(Frame.from_dict(clone(f.to_dict())), a) for f, a in history])
            model = clone(self.client.snapshot())
            self._check_model(model)
            if accepted is not True or model['revision'] != self._state['model']['revision'] + 1:
                raise ValueError('learner update acknowledgement mismatch')
        except Exception:
            self._record('HALT', {'reason': 'learner_update_failed'}, halted='learner_update_failed')
            return {'halted': 'learner_update_failed'}
        self._record('LEARN', {'prediction': forecast_seq, 'observation': observation_seq,
                     'event_id': event_id, 'model_digest': digest(model), 'model_revision': model['revision']},
                     model=model, history=(self._state['history'] + [[before.to_dict(), action.to_dict()]])[-256:],
                     failed_attempts=(self._state['failed_attempts'] + [[before.to_dict(), action.to_dict()]])[-256:]
                         if before.to_dict() == after and before_evidence == evidence else self._state['failed_attempts'],
                     pending=None)
        return {'observation': observation_seq, 'succeeded': succeeded}

    def run_goal(self):
        while self._state['active'] is not None and not self._state['halted']:
            result = self.step()
        return result if 'result' in locals() else {'idle': True}

    def close(self):
        self.db.close()


def verify_world(path, *, expected_config, expected_total_budget, expected_world_id,
                 expected_self_id, expected_goals, expected_external_actions=None,
                 expected_decision_cap=None, expected_sensor_budget=0, expected_sensor_node_cap=8):
    """Native reexecution from external inputs, never from claimed final truth.

    Unexpected external changes require an independently supplied intervention
    schedule (observation-seq -> native Actions). Without that authority this
    verifier fails, rather than reconstructing a fabricated world from the log.
    D1 verifies completed, non-interrupted sessions. Pending recovery is safe
    stopping, not an automatically sealed successful execution.
    """
    errors, steps, results = [], 0, []
    external = expected_external_actions or {}
    decision_cap = (max(16, expected_total_budget * 4) if expected_decision_cap is None
                    else expected_decision_cap)
    try:
        db = sqlite3.connect('file:' + Path(path).resolve().as_posix() + '?mode=ro', uri=True)
        try:
            rows, state = _read(db)
            if rows:
                _check_resume_state(rows, state)
        finally:
            db.close()
        if not rows:
            raise ValueError('empty_world')
        config = encode_config(expected_config)
        with tempfile.TemporaryDirectory(prefix='atanor_world_verify_') as temp:
            body = Sandbox(Path(temp) / 'body', **expected_config)
            if 'operations' not in config:
                config['operations'] = body.schema.to_data()
            frame, evidence = _actual(body)
            initial, observation, revision = evidence, 1, 1
            observed_count, decisions, active, goal_index, model_revision = 1, 0, None, 0, None
            phase, pending, model_digest, history = 'begin', None, None, []
            failed_attempts = []
            recorded_goals = []
            seen_external = set()
            sensing, last_sense = 0, None
            for seq, kind, text, _ in rows:
                p = json.loads(text)
                if kind == 'BEGIN':
                    b = p['binding']
                    if (seq != 1 or b.get('contract') != 'shared-world-2'
                            or b['config'] != config or b['world_id'] != expected_world_id
                            or b['self_id'] != expected_self_id or b['total_budget'] != expected_total_budget
                            or b['decision_cap'] != decision_cap
                            or b.get('sensor_budget', 0) != expected_sensor_budget
                            or (expected_sensor_budget and b.get('sensor_node_cap') != expected_sensor_node_cap)
                            or p['frame'] != frame or p['evidence'] != evidence):
                        raise ValueError('external_begin_binding')
                    binding, phase = b, 'ready'
                    model_digest, model_revision = p['model_digest'], p['model_revision']
                elif kind == 'OBSERVE':
                    if phase not in {'ready', 'deciding'}:
                        raise ValueError('observation_order')
                    old_frame, old_evidence = frame, evidence
                    if seq in external:
                        for action in external[seq]:
                            body.step(action)
                        seen_external.add(seq)
                    frame, evidence = _actual(body)
                    if (p['frame'] != frame or p['evidence'] != evidence
                            or p['changed'] != (frame != old_frame or evidence != old_evidence)):
                        raise ValueError('observation_native_mismatch')
                    if type(p['observed_at_ns']) is not int or p['observed_at_ns'] <= 0:
                        raise ValueError('invalid_observation_time')
                    observation, revision, observed_count = seq, revision + 1, observed_count + 1
                    if p['reason'] == 'changed_during_decision':
                        phase = 'ready'
                elif kind == 'SENSE':
                    from packages.action_core.observation_scope import observe_ancestors
                    if (phase not in {'ready', 'deciding'} or not expected_sensor_budget
                            or sensing >= expected_sensor_budget
                            or set(p) != {'source','handles','frame','added','cost','observed_at_ns'}
                            or p['source'] != observation or type(p['cost']) is not int
                            or type(p['observed_at_ns']) is not int or p['observed_at_ns'] <= 0):
                        raise ValueError('sensor_binding_or_order')
                    expanded, added = observe_ancestors(body, p['handles'],
                        max_new=min(expected_sensor_node_cap, expected_sensor_budget-sensing-1))
                    if (p['frame'] != expanded.to_dict() or p['added'] != list(added)
                            or p['cost'] != 1+len(added) or _actual(body) != (frame,evidence)):
                        raise ValueError('sensor_native_mismatch')
                    sensing += p['cost']; last_sense = p
                elif kind == 'GOAL':
                    if phase != 'ready' or active is not None or goal_index >= len(expected_goals):
                        raise ValueError('goal_order')
                    goal, budget = expected_goals[goal_index]
                    if p != {'goal': goal.to_dict(), 'budget': budget, 'start_steps': steps, 'result': None}:
                        raise ValueError('external_goal_binding')
                    active = (goal, budget, steps)
                    recorded_goals.append(clone(p))
                    goal_index += 1
                elif kind == 'DECIDE':
                    if (phase != 'ready' or active is None or decisions >= binding['decision_cap']
                            or p != {'goal_id': active[0].id, 'observation': observation}):
                        raise ValueError('decision_order')
                    decisions += 1
                    phase = 'deciding'
                elif kind == 'PREDICT':
                    if phase != 'deciding' or active is None:
                        raise ValueError('prediction_order')
                    goal, budget, start = active
                    if steps >= expected_total_budget or steps - start >= budget:
                        raise ValueError('pre_mutation_budget')
                    if _complete(goal, evidence, initial, config['protected'], frame):
                        raise ValueError('prediction_after_completion')
                    if set(p) != {'goal_id', 'source', 'world_revision', 'model_digest', 'model_revision', 'action', 'prediction', 'nodes'}:
                        raise ValueError('caller_authority_in_prediction')
                    forecast, action = parse_prediction(p['prediction']), Action.from_dict(p['action'])
                    current = Frame.from_dict(frame)
                    if (forecast.handles != current.handles or forecast.parent != current.parent
                            or forecast.relations.keys() != current.relations.keys()
                            or action not in body.actions() or p['goal_id'] != goal.id
                            or p['source'] != observation or p['world_revision'] != revision
                            or p['model_digest'] != model_digest or p['model_revision'] != model_revision
                            or type(p['nodes']) is not int or p['nodes'] < 1):
                        raise ValueError('prediction_binding')
                    pending, phase = (seq, action, clone(frame), clone(evidence)), 'predicted'
                elif kind == 'DISPATCH':
                    if (phase != 'predicted' or p != {'prediction': pending[0], 'step': steps + 1}
                            or steps >= expected_total_budget or steps - active[2] >= active[1]):
                        raise ValueError('dispatch_budget_or_order')
                    success = body.step(pending[1])
                    steps += 1
                    frame, evidence, phase = *_actual(body), 'dispatched'
                elif kind == 'RESULT':
                    if (phase != 'dispatched' or p['prediction'] != pending[0]
                            or p['succeeded'] is not success or p['frame'] != frame or p['evidence'] != evidence):
                        raise ValueError('result_native_mismatch')
                    observation, revision, observed_count, phase = seq, revision + 1, observed_count + 1, 'observed'
                elif kind == 'LEARN':
                    if (phase != 'observed' or p['prediction'] != pending[0] or p['observation'] != observation
                            or p['event_id'] != f'{expected_world_id}:event:{observation}'
                            or p['model_revision'] != model_revision + 1):
                        raise ValueError('model_lineage_mismatch')
                    model_digest, model_revision = p['model_digest'], p['model_revision']
                    history = (history + [[pending[2], pending[1].to_dict()]])[-256:]
                    if pending[2] == frame and pending[3] == evidence:
                        failed_attempts = (failed_attempts + [[pending[2], pending[1].to_dict()]])[-256:]
                    pending, phase = None, 'ready'
                elif kind == 'GOAL_END':
                    if phase not in {'ready', 'deciding'} or active is None:
                        raise ValueError('goal_end_order')
                    goal, budget, start = active
                    done = _complete(goal, evidence, initial, config['protected'], frame)
                    if (p['goal_id'] != goal.id or p['completed'] is not done or p['steps'] != steps - start
                            or p['observation'] != observation or p['model_digest'] != model_digest):
                        raise ValueError('goal_end_native_mismatch')
                    reason = p['reason']
                    if done != (reason == 'goal_reached'):
                        raise ValueError('false_completion')
                    if reason == 'step_budget_exceeded' and not (steps == expected_total_budget or steps - start == budget):
                        raise ValueError('false_budget_stop')
                    if reason == 'decision_budget_exceeded' and decisions != binding['decision_cap']:
                        raise ValueError('false_decision_stop')
                    if reason == 'no_valid_actions' and body.actions():
                        raise ValueError('false_no_actions_stop')
                    if reason not in {'goal_reached', 'step_budget_exceeded', 'decision_budget_exceeded',
                                      'policy_abstained', 'invalid_proposal', 'no_valid_actions'}:
                        raise ValueError('unknown_goal_stop')
                    recorded_goals[-1]['result'] = p
                    results.append(p)
                    active, phase = None, 'ready'
                else:
                    raise ValueError('interrupted_or_unknown_world_event:' + kind)
            if (phase != 'ready' or active is not None or goal_index != len(expected_goals)
                    or seen_external != set(external) or state['binding'] != binding
                    or state['active'] is not None or state['pending'] is not None or state['halted'] is not None
                    or state['goals'] != recorded_goals or state['steps'] != steps or state['decisions'] != decisions
                    or state['frame'] != frame or state['evidence'] != evidence or state['initial'] != initial
                    or state['observation_seq'] != observation or state['world_revision'] != revision
                    or state['observations'] != observed_count or state['history'] != history
                    or state['failed_attempts'] != failed_attempts
                    or digest(state['model']) != model_digest or state['model']['revision'] != model_revision):
                raise ValueError('durable_world_mismatch')
            if expected_sensor_budget and (state['sensing'] != sensing or state['last_sense'] != last_sense):
                raise ValueError('durable_sensor_mismatch')
    except Exception as exc:
        errors.append(str(exc) or type(exc).__name__)
    return {'green': not errors, 'errors': errors, 'steps': steps, 'goals': results,
            'capability_claim': False}
