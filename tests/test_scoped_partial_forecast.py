import copy
import json
import sqlite3
from contextlib import closing

import pytest

from packages.shared_world.contracts import (ScopedPartialForecast,
    parse_execution_prediction, parse_prediction)
from packages.shared_world.runtime import WorldSession, verify_world
from packages.action_core.world import Sandbox
from packages.action_core.planner import Goal
from scripts.developmental_persistent_client import PersistentClient
from scripts.representation_r1_dev import SCHEMA


def envelope():
    return ScopedPartialForecast(('n0',), [[0]], [],
                                 [('kind', [0], [0, 1]), ('size', [0], [])]).to_dict()


def test_unknown_roundtrip_is_not_a_complete_rollout():
    wire = json.loads(json.dumps(envelope()))
    assert parse_execution_prediction(wire).to_dict() == wire
    with pytest.raises(ValueError):
        parse_prediction(wire)


@pytest.mark.parametrize('change', [
    lambda x: x.update(verified=True),
    lambda x: x.update(truth_claim=True),
    lambda x: x['cells'].append(['kind', [0], [1]]),
    lambda x: x['cells'].append(['size', [-1], [0]]),
    lambda x: x['cells'].append(['r_fake', [0, 0], [1]]),
    lambda x: x['cells'][0].__setitem__(2, [float('nan')]),
])
def test_reject_authority_and_invalid_cells(change):
    value = json.loads(json.dumps(envelope())); change(value)
    with pytest.raises(ValueError):
        parse_execution_prediction(value)


def test_partial_policy_reaches_native_runtime_without_promoting_prediction(tmp_path):
    # Deliberately wrong synthetic predictor: plumbing/adversarial evidence only.
    # It predicts an existing file becomes a directory. Actual empty cannot do so.
    cfg = dict(paths=['a'], initial={'a': b'abc'}, protected=set(), operations=SCHEMA)
    client = PersistentClient([], schema=SCHEMA, horizon=1)
    client.adapter.predict = lambda frame, actions, history=(): [None] * len(actions)
    client.adapter.predict_cells = lambda frame, action: (
        [('kind', [0], [2]), ('size', [0], [])] if action.op == 'empty' else [])
    path = tmp_path / 'world.sqlite'
    goal = Goal('directory', kinds=(('n0', 2),))
    with closing(WorldSession(path, Sandbox(tmp_path / 'body', **cfg), client,
            config=cfg, total_budget=1, world_id='world', self_id='self')) as world:
        world.issue_goal(goal, 1)
        result = world.run_goal()
        assert result['completed'] is False
        assert result['reason'] == 'step_budget_exceeded'
        assert client.state['records'][-1]['after']['kinds'] == [1]
    with sqlite3.connect(path) as db:
        prediction = json.loads(db.execute("SELECT payload FROM events WHERE kind='PREDICT'").fetchone()[0])['prediction']
    assert prediction['cells'][1][2] == []
    assert prediction['truth_claim'] is False
    verified = verify_world(path, expected_config=cfg, expected_total_budget=1,
        expected_world_id='world', expected_self_id='self', expected_goals=[(goal, 1)])
    assert verified['green'], verified
