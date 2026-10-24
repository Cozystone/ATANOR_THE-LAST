import copy
import json

import pytest

from packages.action_core.model import Forecast
from packages.action_core.planner import Goal
from packages.action_core.world import Action, Frame, Sandbox
from packages.shared_world.contracts import JointForecast
from packages.shared_world.planning import _bounded, _prediction, choose
from packages.shared_world.relational import RelationalLearner
from packages.shared_world.runtime import WorldSession, verify_world
from packages.shared_world.worker import Client
from scripts.representation_r1_dev import config, sensor, CHANNEL, SCHEMA


def test_versioned_roundtrip_and_legacy_unchanged(tmp_path):
    cfg, _ = config(91, linked=True)
    body = Sandbox(tmp_path / 'body', **cfg)
    frame = body.observe()
    assert frame.relations[CHANNEL][0][1] == 1
    assert Frame.from_dict(frame.to_dict()).to_dict() == frame.to_dict()
    v = frame.to_dict()
    del v['view_version']
    with pytest.raises(ValueError):
        Frame.from_dict(v)
    legacy = copy.deepcopy(frame)
    legacy.relations = {}
    assert set(legacy.to_dict()) == {'kinds', 'sizes', 'equal', 'parent', 'handles'}


def test_relation_not_copied_as_static_oracle(tmp_path):
    cfg, _ = config(92, linked=True)
    body = Sandbox(tmp_path / 'body', **cfg)
    model = RelationalLearner(schema=SCHEMA)
    before = body.observe()
    action = Action('unlink', ('n0',))
    body.step(action)
    after = body.observe()
    assert after.relations[CHANNEL][0] == [0, 0, 0]
    assert model.learn('native-unlink', before, action, after)
    forecast, _ = model.predict(before, [action])[0]
    assert all(state.relations == after.relations for _, state in forecast.outcomes)
    restored = RelationalLearner.restore(model.snapshot())
    assert restored.predict(before, [action])[0][0].to_dict() == forecast.to_dict()
    with pytest.raises(ValueError):
        model.learn('invented', forecast.outcomes[0][1], action, after)


def test_branch_merge_keeps_distinct_relations(tmp_path):
    cfg, _ = config(93, linked=True)
    frame = Sandbox(tmp_path / 'body', **cfg).observe()
    from packages.shared_world.relational import _view
    a, b = _view(frame), _view(frame)
    b.relations[CHANNEL][0][1] = 0
    assert len(_bounded([(0.5, a), (0.5, b)])) == 2
    b.relations = {}
    with pytest.raises(ValueError):
        JointForecast([(0.5, a), (0.5, b)])
    with pytest.raises(ValueError):
        _prediction(b, frame)


def test_extra_authority_and_vocabulary_changes_rejected(tmp_path):
    cfg, _ = config(94)
    forged = copy.deepcopy(cfg)
    forged['relation_spec']['verified'] = True
    with pytest.raises(ValueError):
        Sandbox(tmp_path / 'forged', **forged)
    body = Sandbox(tmp_path / 'body', **cfg)
    before = body.observe()
    model = RelationalLearner(schema=SCHEMA)
    model.learn('one', before, Action('empty', ('n0',)), before)
    changed = copy.deepcopy(before)
    changed.relations = {'r_foreign': changed.relations[CHANNEL]}
    with pytest.raises(ValueError):
        model.predict(changed, [Action('empty', ('n0',))])


def test_protected_alias_setup_denied_before_mutation(tmp_path):
    cfg, _ = config(95, linked=True)
    cfg['protected'].add('n0')
    with pytest.raises(ValueError):
        Sandbox(tmp_path / 'forbidden', **cfg)
    assert not (tmp_path / 'forbidden').exists()


def test_size_goal_native_check_and_conflicts(tmp_path):
    cfg, _ = config(96)
    body = Sandbox(tmp_path / 'body', **cfg)
    goal = Goal('empty', sizes=(('n0', 0.),))
    assert not goal.holds(body.evidence())
    body.step(Action('empty', ('n0',)))
    assert goal.holds(body.evidence())
    assert goal.probability(body.observe()) == 1
    assert Goal.from_dict(goal.to_dict()) == goal
    with pytest.raises(ValueError):
        Goal('bad', kinds=(('n0', 0),), sizes=(('n0', 0.),))
    with pytest.raises(ValueError):
        Goal('bad', sizes=(('n0', 0.), ('n0', .3)))


def test_worker_session_replay_binds_projection_and_rejects_false_configuration(tmp_path):
    cfg, _ = config(97, linked=True)
    body = Sandbox(tmp_path / 'body', **cfg)
    before = body.observe()
    action = Action('unlink', ('n0',))
    training = Sandbox(tmp_path / 'training', **cfg)
    training.step(action)
    model = RelationalLearner(schema=SCHEMA)
    model.learn('native', before, action, training.observe())
    db = tmp_path / 'life.sqlite'
    client = Client(algorithm='relational', schema=SCHEMA, frozen=True, horizon=1)
    try:
        client.restore(model.snapshot())
        with pytest.raises(ValueError):
            wrong = copy.deepcopy(cfg)
            wrong.pop('relation_spec')
            WorldSession(tmp_path / 'wrong.sqlite', body, client, config=wrong,
                         total_budget=1, world_id='r', self_id='s')
        world = WorldSession(db, body, client, config=cfg, total_budget=1, world_id='r', self_id='s')
        goal = Goal('remove', kinds=(('n0', 0),))
        world.issue_goal(goal, 1)
        assert world.run_goal()['completed']
        world.close()
    finally:
        client.close()
    result = verify_world(db, expected_config=cfg, expected_total_budget=1,
                          expected_world_id='r', expected_self_id='s', expected_goals=[(goal, 1)])
    assert result['green'], result
    wrong = copy.deepcopy(cfg)
    wrong['relation_spec']['channels'][CHANNEL]['predictions'] = [True, False]
    result = verify_world(db, expected_config=wrong, expected_total_budget=1,
                          expected_world_id='r', expected_self_id='s', expected_goals=[(goal, 1)])
    assert not result['green']
