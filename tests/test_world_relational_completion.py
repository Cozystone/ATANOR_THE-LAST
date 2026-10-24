"""Native relation authority, not caller forecast authority."""
from contextlib import closing
import pytest
from packages.action_core.world import Sandbox, Action
from packages.action_core.planner import Goal
from packages.shared_world.relational import _view
from packages.shared_world.runtime import WorldSession, verify_world
from scripts.representation_r1_dev import config, CHANNEL


@pytest.mark.parametrize('linked', [False, True])
def test_actual_relation_decides_even_when_forecast_claims_success(tmp_path, linked):
    cfg, _ = config(151001, linked=linked)
    class Forged:
        def __init__(self): self.revision = 0
        def snapshot(self): return {'revision': self.revision}
        def restore(self, value): self.revision = value['revision']
        def learn(self, *args): self.revision += 1; return True
        def choose(self, frame, goal, actions, history, **kwargs):
            predicted = _view(frame)
            predicted.relations[CHANNEL][0][1] = 1
            return Action('empty', ('n0',)), predicted, 1
    goal = Goal('physical-relation', relations=((CHANNEL, 'n0', 'n1', 1),))
    path = tmp_path / 'world.sqlite'
    with closing(WorldSession(path, Sandbox(tmp_path / 'body', **cfg), Forged(),
            config=cfg, total_budget=1, world_id='w', self_id='s')) as world:
        world.issue_goal(goal, 1)
        assert world.run_goal()['completed'] is linked
    result = verify_world(path, expected_config=cfg, expected_total_budget=1,
        expected_world_id='w', expected_self_id='s', expected_goals=[(goal, 1)])
    assert result['green'], result
