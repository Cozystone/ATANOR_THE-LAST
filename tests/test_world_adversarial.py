"""D1 native-authority adversarial tests; no capability or hostile-host claim.

All bodies are new test-owned temporary directories. Fake clients deliberately
predict success where native actions fail. Database tampering tests do not claim
cryptographic host isolation: they exercise semantic consistency checks.
"""
import copy
import hashlib
import json
import sqlite3
from contextlib import closing
from unittest.mock import patch

import pytest

from packages.action_core.episode import canonical
from packages.action_core.model import Forecast
from packages.action_core.planner import Goal
from packages.action_core.world import Action, Sandbox
from packages.shared_world.contracts import JointForecast, parse_prediction
from packages.shared_world.runtime import WorldSession, verify_world


CONFIG = {'paths': ['ref', 'folder', 'folder/output'],
          'initial': {'ref': b'genuine'}, 'protected': {'n0'}}
OUTPUT = Goal('output', kinds=(('n2', 1),), equal=(('n0', 'n2'),))
PARENT = Goal('parent', kinds=(('n1', 2),))
MKDIR = Action('mkdir', ('n1',))
COPY = Action('copy', ('n0', 'n2'))


class Envelope:
    def __init__(self, data):
        self.data = data

    def to_dict(self):
        return copy.deepcopy(self.data)


class ScriptedClient:
    def __init__(self, actions=(), *, mutate=None, joint=False):
        self.actions = list(actions)
        self.mutate, self.joint = mutate, joint
        self.revision, self.calls, self.events = 0, 0, []

    def choose(self, frame, goal, actions, history, *, failed_attempts=()):
        self.calls += 1
        n = len(frame.handles)
        # Deliberately optimistic; does not know native outcomes.
        forecast = Forecast([[0., 1., 0.] for _ in range(n)], [0.] * n,
                            [[1.] * n for _ in range(n)], frame.parent, frame.handles)
        prediction = JointForecast([(1., forecast)]) if self.joint else forecast
        if self.mutate:
            # Match a worker's independent JSON reply, not in-process alias writes.
            data = copy.deepcopy(prediction.to_dict())
            self.mutate(data)
            prediction = Envelope(data)
        action = self.actions[self.revision] if self.revision < len(self.actions) else COPY
        return action, prediction, 1

    def learn(self, event_id, before, action, after, history):
        self.events.append(event_id)
        self.revision += 1
        return True

    def snapshot(self):
        return {'revision': self.revision, 'events': list(self.events)}

    def restore(self, value):
        self.revision, self.events = value['revision'], list(value['events'])


@pytest.fixture
def scene(tmp_path):
    return tmp_path / 'world.sqlite', Sandbox(tmp_path / 'body', **CONFIG)


def session(scene, client, *, total=4, cap=16, **kwargs):
    path, body = scene
    options = dict(config=CONFIG, total_budget=total, decision_cap=cap,
                   world_id='authorized-world', self_id='authorized-self')
    options.update(kwargs)
    return WorldSession(path, body, client, **options)


def verify(scene, goals, *, total=4, cap=16, **kwargs):
    options = dict(expected_config=CONFIG, expected_total_budget=total,
                   expected_world_id='authorized-world', expected_self_id='authorized-self',
                   expected_goals=goals, expected_decision_cap=cap)
    options.update(kwargs)
    return verify_world(scene[0], **options)


def edit_state(path, mutate):
    with sqlite3.connect(path) as db:
        state = json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
        mutate(state)
        db.execute('UPDATE state SET payload=? WHERE id=1', (canonical(state),))


def reseal_events(path, mutate_event, mutate_state=lambda _: None):
    """Recompute the public hash chain: hashes alone must not establish truth."""
    with sqlite3.connect(path) as db:
        rows = list(db.execute('SELECT seq,kind,payload FROM events ORDER BY seq'))
        previous = ''
        for seq, kind, text in rows:
            value = json.loads(text)
            mutate_event(kind, value)
            text = canonical(value)
            previous = hashlib.sha256((previous + kind + text).encode()).hexdigest()
            db.execute('UPDATE events SET payload=?,digest=? WHERE seq=?', (text, previous, seq))
        state = json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
        mutate_state(state)
        state['head'] = previous
        db.execute('UPDATE state SET payload=? WHERE id=1', (canonical(state),))


@pytest.mark.parametrize('joint', [False, True])
def test_forecast_success_never_becomes_native_completion(scene, joint):
    client = ScriptedClient([COPY], joint=joint)
    with closing(session(scene, client, total=1)) as world:
        world.issue_goal(OUTPUT, 1)
        result = world.run_goal()
        assert result == dict(goal_id='output', reason='step_budget_exceeded', completed=False,
                              steps=1, observation=result['observation'],
                              model_digest=result['model_digest'])
        assert scene[1].evidence()['n2']['kind'] == 0
        assert world.state['steps'] == 1
    checked = verify(scene, [(OUTPUT, 1)], total=1)
    assert checked['green'], checked
    assert checked['capability_claim'] is False


def test_shared_body_survives_goals_and_resume_without_budget_reset(scene):
    with closing(session(scene, ScriptedClient([MKDIR, COPY]), total=2)) as world:
        world.poll()  # Observation exists independently of a goal.
        world.issue_goal(PARENT, 1)
        assert world.run_goal()['completed'] is True
        world.poll()
    path, body = scene
    attached = Sandbox.attach(body.root, CONFIG['paths'], CONFIG['protected'])
    client = ScriptedClient([MKDIR, COPY])
    with closing(session((path, attached), client, total=2)) as world:
        assert client.revision == 1
        world.issue_goal(OUTPUT, 1)
        assert world.run_goal()['completed'] is True
        assert world.state['steps'] == 2
        assert len(world.state['history']) == 2
    checked = verify(scene, [(PARENT, 1), (OUTPUT, 1)], total=2)
    assert checked['green'], checked


def test_global_budget_cannot_be_renewed_by_new_goal(scene):
    client = ScriptedClient([MKDIR, COPY])
    with closing(session(scene, client, total=1)) as world:
        world.issue_goal(PARENT, 3)
        assert world.run_goal()['completed']
        world.issue_goal(OUTPUT, 3)
        result = world.run_goal()
        assert result['reason'] == 'step_budget_exceeded'
        assert result['steps'] == 0 and not result['completed']
        assert client.calls == 1
        assert scene[1].evidence()['n2']['kind'] == 0
    checked = verify(scene, [(PARENT, 3), (OUTPUT, 3)], total=1)
    assert checked['green'], checked


@pytest.mark.parametrize('field', ['verified', 'source', 'freshness', 'status', 'completed'])
@pytest.mark.parametrize('joint', [False, True])
def test_prediction_caller_authority_fields_rejected_before_dispatch(scene, field, joint):
    client = ScriptedClient([MKDIR], mutate=lambda p: p.update({field: True}), joint=joint)
    with closing(session(scene, client)) as world:
        world.issue_goal(OUTPUT, 2)
        result = world.run_goal()
        assert result['reason'] == 'invalid_proposal'
        assert world.state['steps'] == 0
        assert scene[1].evidence()['n1']['kind'] == 0
    assert verify(scene, [(OUTPUT, 2)])['green']


@pytest.mark.parametrize('action', [Action('empty', ('n0',)),
                                   Action('empty', ('../outside',)),
                                   Action('copy', ('n0',)),
                                   Action('invented', ('n1',))])
def test_invalid_actions_never_reach_native_body(scene, action):
    with closing(session(scene, ScriptedClient([action]))) as world:
        world.issue_goal(OUTPUT, 2)
        assert world.run_goal()['reason'] == 'invalid_proposal'
        assert world.state['steps'] == 0
        assert scene[1].evidence()['n0']['size_bytes'] == 7
        assert scene[1].evidence()['n1']['kind'] == 0


def test_forecast_with_wrong_parent_scope_is_not_a_valid_proposal(scene):
    # Native contract: parent[i][j] means i is the parent of j, not vice versa.
    assert scene[1].observe().parent[1][2] == 1
    client = ScriptedClient([MKDIR], mutate=lambda p: p['parent'][1].__setitem__(2, 0))
    with closing(session(scene, client)) as world:
        world.issue_goal(OUTPUT, 2)
        assert world.run_goal()['reason'] == 'invalid_proposal'
        assert world.state['steps'] == 0


@pytest.mark.parametrize('changes', [dict(world_id='other-world'), dict(self_id='other-self'),
                                     dict(total_budget=100), dict(decision_cap=100)])
def test_resume_requires_same_external_authority_binding(scene, changes):
    with closing(session(scene, ScriptedClient())):
        pass
    with pytest.raises(ValueError):
        session(scene, ScriptedClient(), **changes)


def test_returned_state_is_a_clone_not_write_authority(scene):
    with closing(session(scene, ScriptedClient())) as world:
        clone = world.state
        clone['binding']['total_budget'] = 999
        clone['model']['revision'] = 999
        assert world.state['binding']['total_budget'] == 4
        assert world.state['model']['revision'] == 0


def test_pending_native_side_effect_is_never_reissued_on_resume(scene):
    client = ScriptedClient([MKDIR, COPY])
    with closing(session(scene, client)) as world:
        world.issue_goal(OUTPUT, 2)
        native_step = scene[1].step

        def die_after_mutation(action):
            native_step(action)
            raise KeyboardInterrupt('controlled process-interruption analogue')

        with patch.object(scene[1], 'step', side_effect=die_after_mutation):
            with pytest.raises(KeyboardInterrupt):
                world.step()
        assert scene[1].evidence()['n1']['kind'] == 2
    resumed_client = ScriptedClient([MKDIR, COPY])
    with closing(session(scene, resumed_client)) as world:
        assert world.state['steps'] == 1
        assert world.step() == {'halted': 'pending_interrupted'}
        assert resumed_client.calls == 0
        assert scene[1].evidence()['n2']['kind'] == 0
    assert not verify(scene, [(OUTPUT, 2)])['green']


@pytest.mark.parametrize('field', ['steps', 'decisions', 'history', 'failed_attempts', 'model', 'goal_budget'])
def test_resume_rejects_semantically_modified_state_with_unchanged_hash_head(scene, field):
    with closing(session(scene, ScriptedClient([MKDIR, COPY]))) as world:
        world.issue_goal(OUTPUT, 2)
        world.step()

    def corrupt(state):
        if field in ('steps', 'decisions'):
            state[field] = 0
        elif field == 'history':
            state['history'] = []
        elif field == 'failed_attempts':
            state['failed_attempts'] = copy.deepcopy(state['history'])
        elif field == 'model':
            state['model']['events'] = ['caller-invented-event']
        else:
            state['goals'][0]['budget'] = 99

    edit_state(scene[0], corrupt)
    with pytest.raises(ValueError):
        session(scene, ScriptedClient([MKDIR, COPY]))


def test_resealed_false_completion_is_rejected_by_native_replay(scene):
    with closing(session(scene, ScriptedClient([COPY]), total=1)) as world:
        world.issue_goal(OUTPUT, 1)
        assert not world.run_goal()['completed']

    def forge(kind, payload):
        if kind == 'GOAL_END':
            payload.update(completed=True, reason='goal_reached')

    def forge_state(state):
        state['goals'][0]['result'].update(completed=True, reason='goal_reached')

    reseal_events(scene[0], forge, forge_state)
    checked = verify(scene, [(OUTPUT, 1)], total=1)
    assert not checked['green']
    assert any('native' in error or 'completion' in error for error in checked['errors'])


def test_external_changes_are_observed_but_require_independent_replay_authority(scene):
    with closing(session(scene, ScriptedClient([COPY]))) as world:
        assert scene[1].step(MKDIR)
        observed = world.poll(reason='authorized_external_change')
        observation_seq = world.state['observation_seq']
        assert observed['changed'] and world.state['halted'] is None
        world.issue_goal(OUTPUT, 1)
        assert world.run_goal()['completed']
        assert world.state['steps'] == 1  # External action is not learner-spent budget.
    assert not verify(scene, [(OUTPUT, 1)])['green']
    checked = verify(scene, [(OUTPUT, 1)], expected_external_actions={observation_seq: [MKDIR]})
    assert checked['green'], checked


def test_verifier_binds_goal_config_and_decision_cap_externally(scene):
    with closing(session(scene, ScriptedClient([MKDIR]))) as world:
        world.issue_goal(PARENT, 1)
        assert world.run_goal()['completed']
    assert not verify(scene, [(PARENT, 2)])['green']
    changed_config = copy.deepcopy(CONFIG)
    changed_config['initial']['ref'] = b'counterfeit'
    assert not verify(scene, [(PARENT, 1)], expected_config=changed_config)['green']
    assert not verify(scene, [(PARENT, 1)], cap=99)['green']


@pytest.mark.parametrize('rows', [[], [None], [()], [(1., None)], [(True, None)]])
def test_joint_forecast_malformed_rows_fail_explicitly(rows):
    with pytest.raises(ValueError):
        JointForecast(rows)


@pytest.mark.parametrize('weight', [float('nan'), float('inf'), -0.1, 0.8, True])
def test_joint_forecast_invalid_mass_is_rejected(scene, weight):
    frame = scene[1].observe()
    n = len(frame.handles)
    forecast = Forecast([[1., 0., 0.]] * n, [0.] * n, [[0.] * n for _ in range(n)],
                        frame.parent, frame.handles)
    with pytest.raises(ValueError):
        JointForecast([(weight, forecast)])


def test_observation_tag_cannot_impersonate_prediction(scene):
    with pytest.raises(ValueError):
        parse_prediction(scene[1].observe().to_dict())
