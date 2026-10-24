import pytest
from packages.action_core.world import Sandbox, Action
from packages.shared_world.relational import RelationalLearner, _view
from packages.shared_world.intervention_synthesis import synthesize
from scripts.representation_r3_dev import configuration
from scripts.representation_r1_dev import SCHEMA


def test_current_disagreement_proposed_without_learning(tmp_path):
    cfg, aliases, _, _ = configuration(2, 1281, 'independent_mixed', b'x'*23)
    body = Sandbox(tmp_path/'train', **cfg)
    action = Action('empty', (aliases[0],))
    before = body.observe(); body.step(action)
    model = RelationalLearner(schema=SCHEMA, partitioned=True)
    model.learn('actual', before, action, body.observe())
    cfg, _, _, _ = configuration(2, 1281, 'detached_absent', b'x'*23)
    body = Sandbox(tmp_path/'query', **cfg)
    snapshot = model.snapshot()
    report = synthesize(model, body.observe(), body.actions(), remaining=3)
    assert report['status'] == 'PROPOSED'
    assert len(report['sequence']) == 1
    assert report['disagreement']['disagreement_cells']
    assert model.snapshot() == snapshot
    assert report['truth_claim'] is False


def test_cold_model_is_not_invented_disagreement(tmp_path):
    cfg, _, _, _ = configuration(2, 1281)
    body = Sandbox(tmp_path/'cold', **cfg)
    model = RelationalLearner(schema=SCHEMA, partitioned=True)
    assert synthesize(model, body.observe(), body.actions(), remaining=3)['status'] == 'NO_WITNESS_WITHIN_BOUNDS'
    with pytest.raises(ValueError):
        synthesize(model, _view(body.observe()), body.actions(), remaining=3)
    assert synthesize(model, body.observe(), body.actions(), remaining=3, max_queries=1)['status'] == 'QUERY_BUDGET_EXHAUSTED'
