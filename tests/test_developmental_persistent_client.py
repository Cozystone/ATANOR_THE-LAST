"""Integration only; training contexts supplied, not autonomous discovery."""
import sqlite3
from contextlib import closing

import pytest

from packages.action_core.world import Sandbox, Action, Frame
from packages.action_core.planner import Goal
from packages.shared_world.runtime import WorldSession, verify_world
from scripts.developmental_persistent_client import PersistentClient
from scripts.representation_r1_dev import SCHEMA


@pytest.mark.parametrize('planner', ['beam', 'cost_ordered'])
def test_native_learning_restart_and_journal_order(tmp_path, planner):
    cfg = dict(paths=['a', 'b'], initial={'a': b'abc', 'b': b'abc'},
               protected=set(), operations=SCHEMA)
    training = Sandbox(tmp_path / 'training', **cfg)
    records = []
    for handle in ('n0', 'n1'):
        before = training.observe(); action = Action('empty', (handle,))
        training.step(action)
        records.append(dict(before=before.to_dict(), action=action.to_dict(),
                            after=training.observe().to_dict()))
    client = PersistentClient(records, schema=SCHEMA, planner=planner)
    body = Sandbox(tmp_path / 'body', **cfg); path = tmp_path / 'world.sqlite'
    kwargs = dict(config=cfg, total_budget=2, world_id='world', self_id='self')
    goals = [Goal('first', sizes=(('n0', 0.),)), Goal('second', sizes=(('n1', 0.),))]
    with closing(WorldSession(path, body, client, **kwargs)) as world:
        world.issue_goal(goals[0], 1)
        assert world.run_goal()['completed']
        checkpoint = client.snapshot()
        assert checkpoint['revision'] == 1
    resumed = PersistentClient([], schema=SCHEMA, planner=planner)
    with closing(WorldSession(path, body, resumed, **kwargs)) as world:
        assert resumed.snapshot() == checkpoint
        world.issue_goal(goals[1], 1)
        assert world.run_goal()['completed']
        assert resumed.snapshot()['revision'] == 2
    result = verify_world(path, expected_config=cfg, expected_total_budget=2,
        expected_world_id='world', expected_self_id='self',
        expected_goals=[(goal, 1) for goal in goals])
    assert result['green'], result
    with sqlite3.connect(path) as db:
        kinds = [r[0] for r in db.execute('SELECT kind FROM events ORDER BY seq')]
    assert [k for k in kinds if k in ('PREDICT', 'DISPATCH', 'RESULT', 'LEARN')] == [
        'PREDICT', 'DISPATCH', 'RESULT', 'LEARN'] * 2
    row = resumed.snapshot()['records'][-1]
    args = (Frame.from_dict(row['before']), Action.from_dict(row['action']),
            Frame.from_dict(row['after']), [])
    event_id = list(resumed.state['events'])[-1]
    assert resumed.learn(event_id, *args) is False
    changed = Frame.from_dict(row['after']); changed.sizes[0] = .9
    with pytest.raises(ValueError):
        resumed.learn(event_id, args[0], args[1], changed, [])
