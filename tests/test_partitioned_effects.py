import copy

import pytest

from packages.action_core.world import Action, Sandbox
from packages.shared_world.relational import RelationalLearner, _induce, _apply
from scripts.representation_r3_dev import configuration
from scripts.representation_r1_dev import SCHEMA


def transition(tmp_path, count, seed, name):
    cfg, aliases, reference, _ = configuration(count, seed)
    body = Sandbox(tmp_path / name, **cfg)
    before = body.observe()
    action = Action('empty', (aliases[0],))
    body.step(action)
    return before, action, body.observe(), reference


def test_native_wildcard_failure_and_quantified_repair(tmp_path):
    before, action, after, reference = transition(tmp_path, 3, 931, 'body')
    assert _induce(before, action, after, False) is None
    program = _induce(before, action, after, True)
    assert program is not None
    predicted = _apply(program, before, action, True)
    assert predicted.sizes == after.sizes
    assert predicted.equal == after.equal
    assert predicted.relations == after.relations
    i = before.handles.index(reference)
    assert predicted.sizes[i] == before.sizes[i] > 0


@pytest.mark.parametrize('count,seed', [(4, 81), (5, 982), (7, 219)])
def test_one_program_transfers_to_larger_permuted_groups(tmp_path, count, seed):
    before, action, after, _ = transition(tmp_path, 3, 931, 'training')
    program = _induce(before, action, after, True)
    before, action, after, _ = transition(tmp_path, count, seed, 'fresh')
    predicted = _apply(program, before, action, True)
    assert predicted is not None
    assert predicted.sizes == after.sizes
    assert predicted.equal == after.equal
    assert predicted.relations == after.relations


def test_mode_is_explicit_and_checkpoint_bound(tmp_path):
    before, action, after, _ = transition(tmp_path, 3, 931, 'body')
    model = RelationalLearner(schema=SCHEMA, partitioned=True)
    model.learn('native', before, action, after)
    value = model.snapshot()
    assert value['partitioned'] is True
    restored = RelationalLearner.restore(value)
    assert restored.predict(before, [action])[0][0].to_dict() == model.predict(before, [action])[0][0].to_dict()
    forged = copy.deepcopy(value)
    forged['partitioned'] = 'verified'
    with pytest.raises(ValueError):
        RelationalLearner.restore(forged)
    assert RelationalLearner(schema=SCHEMA).partitioned is False
