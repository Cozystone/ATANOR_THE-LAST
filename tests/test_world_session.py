"""D1 native integration: continuity and actual results, not intelligence proof."""
import copy
import sqlite3

import pytest

from packages.action_core.model import Forecast
from packages.action_core.planner import Goal
from packages.action_core.world import Action, Sandbox
from packages.shared_world.runtime import WorldSession, verify_world


class Scripted:
    def __init__(self, actions=()):
        self.actions = list(actions)
        self.model = {'revision': 0, 'seen': []}
        self.before = []

    def choose(self, frame, goal, actions, history, *, failed_attempts=()):
        self.before.append(copy.deepcopy(frame))
        if not self.actions:
            return None
        action = self.actions.pop(0)
        prediction = Forecast([[int(k == j) for j in range(3)] for k in frame.kinds],
                              frame.sizes, frame.equal, frame.parent, frame.handles)
        return action, prediction, 1

    def learn(self, event_id, before, action, after, history):
        assert event_id not in self.model['seen']
        self.model['seen'].append(event_id)
        self.model['revision'] += 1
        return True

    def snapshot(self):
        return copy.deepcopy(self.model)

    def restore(self, value):
        self.model = copy.deepcopy(value)


def config():
    return {'paths': ['reference', 'folder', 'folder/target'],
            'initial': {'reference': b'actual evidence'}, 'protected': {'n0'}}


def check(path, cfg, goals, budget=5, **kw):
    return verify_world(path, expected_config=cfg, expected_total_budget=budget,
                        expected_world_id='world', expected_self_id='self', expected_goals=goals, **kw)


def test_idle_observation_two_goals_and_restart_share_one_world(tmp_path):
    cfg, db = config(), tmp_path / 'life.sqlite'
    body = Sandbox(tmp_path / 'body', **cfg)
    first = Goal('first', (('n2', 1),), (('n0', 'n2'),))
    second = Goal('second', (('n2', 0),))
    client = Scripted([Action('mkdir', ('n1',)), Action('copy', ('n0', 'n2'))])
    world = WorldSession(db, body, client, config=cfg, total_budget=5, world_id='world', self_id='self')
    world.poll(reason='no_question')
    world.issue_goal(first, 3)
    world.step()
    assert world.state['goals'][0]['result'] is None
    assert body.observe().kinds[1] == 2
    world.close()

    restored = Scripted([Action('copy', ('n0', 'n2')), Action('unlink', ('n2',))])
    world = WorldSession(db, body, restored, config=cfg, total_budget=5, world_id='world', self_id='self')
    assert restored.model['revision'] == 1
    assert world.run_goal()['completed']
    world.issue_goal(second, 2)
    assert world.run_goal()['completed']
    assert world.state['steps'] == 3
    assert world.state['model']['revision'] == 3
    assert len(world.state['history']) == 3
    world.close()
    result = check(db, cfg, [(first, 3), (second, 2)])
    assert result['green'], result


def test_returned_world_state_is_not_a_mutation_channel(tmp_path):
    cfg = config()
    world = WorldSession(tmp_path / 'state.sqlite', Sandbox(tmp_path / 'body', **cfg),
                         Scripted(), config=cfg, total_budget=1, world_id='world', self_id='self')
    copy_state = world.state
    copy_state['steps'] = -100
    copy_state['evidence']['n2']['kind'] = 1
    assert world.state['steps'] == 0
    assert world.state['evidence']['n2']['kind'] == 0
    world.close()


def test_world_observes_authorized_external_event_between_goals(tmp_path):
    cfg, db = config(), tmp_path / 'external.sqlite'
    body = Sandbox(tmp_path / 'body', **cfg)
    world = WorldSession(db, body, Scripted(), config=cfg, total_budget=5, world_id='world', self_id='self')
    action = Action('mkdir', ('n1',))
    assert body.step(action)
    world.poll(reason='external_actor')
    observation = world.state['observation_seq']
    goal = Goal('already', (('n1', 2),))
    world.issue_goal(goal, 1)
    assert world.run_goal()['completed']
    assert world.state['steps'] == 0
    world.close()
    assert not check(db, cfg, [(goal, 1)])['green']
    assert check(db, cfg, [(goal, 1)], expected_external_actions={observation: [action]})['green']


def test_change_while_thinking_invalidates_proposal_without_dispatch(tmp_path):
    cfg, db = config(), tmp_path / 'race.sqlite'
    body = Sandbox(tmp_path / 'body', **cfg)

    class Changing(Scripted):
        def choose(self, *args, **kwargs):
            reply = super().choose(*args, **kwargs)
            body.step(Action('mkdir', ('n1',)))
            return reply

    world = WorldSession(db, body, Changing([Action('empty', ('n2',))]), config=cfg,
                         total_budget=5, world_id='world', self_id='self')
    goal = Goal('g', (('n1', 2),))
    world.issue_goal(goal, 1)
    assert world.step()['replan']
    seq = world.state['observation_seq']
    assert world.state['steps'] == 0
    assert world.run_goal()['completed']
    world.close()
    result = check(db, cfg, [(goal, 1)], expected_external_actions={seq: [Action('mkdir', ('n1',))]})
    assert result['green'], result


def test_journal_tampering_does_not_resume(tmp_path):
    cfg, db = config(), tmp_path / 'corrupt.sqlite'
    body, client = Sandbox(tmp_path / 'body', **cfg), Scripted()
    world = WorldSession(db, body, client, config=cfg, total_budget=5, world_id='world', self_id='self')
    world.close()
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE events SET digest='forged' WHERE seq=1")
    with pytest.raises(ValueError, match='chain'):
        WorldSession(db, body, client, config=cfg, total_budget=5, world_id='world', self_id='self')


def test_only_native_unchanged_outcome_enters_repeat_context(tmp_path):
    cfg, db = config(), tmp_path / 'no-change.sqlite'
    body = Sandbox(tmp_path / 'body', **cfg)
    action = Action('copy', ('n0', 'n2'))
    client = Scripted([action, Action('mkdir', ('n1',)), action])
    world = WorldSession(db, body, client, config=cfg, total_budget=5, world_id='world', self_id='self')
    goal = Goal('g', (('n2', 1),), (('n0', 'n2'),))
    world.issue_goal(goal, 4)
    assert world.run_goal()['completed']
    # Failed copy before parent existed enters context; subsequent successful
    # mkdir and copy stay in memory without becoming repeat penalties.
    assert len(world.state['history']) == 3
    assert len(world.state['failed_attempts']) == 1
    assert world.state['failed_attempts'][0][1] == action.to_dict()
    world.close()
    assert check(db, cfg, [(goal, 4)])['green']


def test_native_content_change_cannot_be_inferred_unchanged_from_frame(tmp_path):
    cfg = {'paths': ['a', 'b'], 'initial': {'a': b'xx', 'b': b'yy'}, 'protected': set()}
    body = Sandbox(tmp_path / 'body', **cfg)
    action = Action('empty', ('n1',))
    client = Scripted([action])
    # Simulate an external change in the native interval. Its content is not in
    # Frame; only independent evidence distinguishes it. No replay GREEN claim.
    def changed(_):
        body._paths['n1'].write_bytes(b'zz')
        return True
    body.step = changed
    world = WorldSession(tmp_path / 'external-content.sqlite', body, client, config=cfg,
                         total_budget=1, world_id='world', self_id='self')
    world.issue_goal(Goal('g', (('n1', 0),)), 1)
    world.step()
    assert world.state['failed_attempts'] == []
    world.close()
