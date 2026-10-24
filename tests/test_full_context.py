"""Synthetic mechanism checks only. No native task or fresh capability execution."""
import builtins
import copy
import io
import json
import os

import numpy as np
import pytest
import torch

from packages.action_core.model import Forecast, Learner as LegacyLearner, role_features
from packages.action_core.schema import OperationSchema
from packages.action_core.world import Action, Frame, Sandbox
from packages.shared_world.full_context import (
    CONTEXT_INPUT_DIM, CONTEXT_ROLE_DIM, MODEL_FORMAT,
    FullContextLearner, full_context_role_features,
)


SCHEMA = OperationSchema((('q81', 2), ('z19', 1)))
ACTION = Action('q81', ('n0', 'n1'))


def frame(parent_kind=0):
    return Frame([1, 0, parent_kind], [0.3, 0.0, 0.0],
                 [[1, 0, 0], [0, 0, 0], [0, 0, int(parent_kind != 0)]],
                 [[0, 0, 0], [0, 0, 1], [0, 0, 0]], ('n0', 'n1', 'n2'))


def outcome():
    return Frame([0, 1, 2], [0.0, 0.3, 0.0],
                 [[0, 0, 0], [0, 1, 0], [0, 0, 1]],
                 [[0, 0, 0], [0, 0, 1], [0, 0, 0]], ('n0', 'n1', 'n2'))


def permute(value, action, order):
    inverse = {old: new for new, old in enumerate(order)}
    moved = Frame([value.kinds[i] for i in order], [value.sizes[i] for i in order],
                  [[value.equal[i][j] for j in order] for i in order],
                  [[value.parent[i][j] for j in order] for i in order], value.handles)
    renamed = Action(action.op, tuple(f'n{inverse[value.handles.index(h)]}' for h in action.args))
    return moved, renamed


def normalized_snapshot(learner):
    return json.loads(json.dumps(learner.snapshot(), sort_keys=True, allow_nan=False))


def test_third_object_context_reaches_other_argument_without_operator_rules():
    absent, present = frame(0), frame(2)
    np.testing.assert_array_equal(role_features(absent, ACTION)[0], role_features(present, ACTION)[0])
    x0 = full_context_role_features(absent, ACTION, SCHEMA)
    x1 = full_context_role_features(present, ACTION, SCHEMA)
    assert x0.shape == x1.shape == (3, CONTEXT_ROLE_DIM)
    assert not np.array_equal(x0[0], x1[0])
    learner = FullContextLearner(seed=17, schema=SCHEMA)
    model = learner.members[0]
    inputs = model.inputs(present, [ACTION]).detach().requires_grad_()
    assert inputs.shape == (1, 3, CONTEXT_INPUT_DIM)
    kinds, _, _ = model(inputs, model.history([], 3), torch.tensor(present.equal)[None])
    kinds[0, 0, 0].backward()
    # Slot two starts at 50; its observed parent-kind summary occupies 54:57.
    assert torch.count_nonzero(inputs.grad[0, 0, 54:57]).item() > 0
    p0 = learner.predict(absent, [ACTION])[0][0].kinds[0]
    p1 = learner.predict(present, [ACTION])[0][0].kinds[0]
    assert p0 != p1  # Information access only, not a learned correct effect.


@pytest.mark.parametrize('order', [(2, 0, 1), (1, 2, 0), (0, 2, 1)])
def test_rebinding_nodes_actions_and_history_is_equivariant(order):
    learner = FullContextLearner(seed=29, schema=SCHEMA)
    current, action = frame(2), ACTION
    history = [(frame(0), Action('z19', ('n2',)))]
    moved, moved_action = permute(current, action, order)
    moved_history = [permute(f, a, order) for f, a in history]
    expected, expected_uncertainty = learner.predict(current, [action], history)[0]
    actual, actual_uncertainty = learner.predict(moved, [moved_action], moved_history)[0]
    np.testing.assert_allclose(actual.kinds, np.asarray(expected.kinds)[list(order)], atol=1e-7)
    np.testing.assert_allclose(actual.sizes, np.asarray(expected.sizes)[list(order)], atol=1e-7)
    for name in ('equal', 'parent'):
        wanted = np.asarray(getattr(expected, name))[np.ix_(order, order)]
        np.testing.assert_allclose(getattr(actual, name), wanted, atol=1e-7)
    assert actual_uncertainty == pytest.approx(expected_uncertainty, abs=1e-8)


def test_schema_names_are_opaque_but_argument_positions_are_preserved():
    other = OperationSchema((('a03', 2), ('b74', 1)))
    left = FullContextLearner(seed=37, schema=SCHEMA)
    right = FullContextLearner(seed=37, schema=other)
    a = left.predict(frame(2), [ACTION])[0]
    b = right.predict(frame(2), [Action('a03', ACTION.args)])[0]
    assert a == b
    unary = full_context_role_features(frame(2), Action('z19', ('n2',)), SCHEMA)
    np.testing.assert_array_equal(unary[:, 50:], np.zeros((3, 25), dtype=np.float32))


def test_capacity_change_is_explicit_and_recurrent_width_stays_fixed():
    learner = FullContextLearner(seed=1, schema=SCHEMA)
    legacy = LegacyLearner(seed=1, schema=SCHEMA)
    count = lambda item: sum(p.numel() for p in item.members.parameters())
    assert count(learner) == 28407  # Two opaque public operation identifiers.
    assert count(learner) - count(legacy) == 10800
    assert len(learner.members) == 3
    assert all(m.cell.hidden_size == 24 and m.cell.input_size == 79 for m in learner.members)


def test_learning_and_json_snapshot_restore_are_identical_on_continuation():
    learner = FullContextLearner(seed=43, updates=1, change_balanced=True,
                                 latest_update=True, schema=SCHEMA)
    history = [(frame(0), Action('z19', ('n2',)))]
    before = normalized_snapshot(learner)
    assert learner.learn('event_1', frame(2), ACTION, outcome(), history)
    assert learner.revision == 1 and normalized_snapshot(learner)['weights'] != before['weights']
    stored = normalized_snapshot(learner)
    assert stored['format'] == MODEL_FORMAT
    assert not learner.learn('event_1', frame(2), ACTION, outcome(), history)
    assert normalized_snapshot(learner) == stored
    restored = FullContextLearner.restore(stored)
    assert normalized_snapshot(restored) == stored
    assert restored.predict(frame(2), [ACTION], history) == learner.predict(frame(2), [ACTION], history)
    for item in (learner, restored):
        assert item.learn('event_2', frame(0), Action('z19', ('n2',)), frame(2), [])
    assert normalized_snapshot(restored) == normalized_snapshot(learner)


def test_rollout_forecast_is_allowed_only_for_prediction_not_learning_or_history():
    learner = FullContextLearner(seed=7, updates=0, schema=SCHEMA)
    forecast, _ = learner.predict(frame(2), [ACTION])[0]
    assert type(forecast) is Forecast
    assert learner.predict(forecast, [ACTION])
    assert learner.predict(frame(2), []) == []
    with pytest.raises(ValueError):
        learner.learn('not_observed', forecast, ACTION, outcome(), [])
    with pytest.raises(ValueError):
        learner.predict(frame(2), [ACTION], [(forecast, ACTION)])


@pytest.mark.parametrize('bad_action', [
    Action('unknown', ('n0',)), Action('q81', ('n0',)),
    Action('z19', ('n7',)), Action('q81', ['n0', 'n1']),
])
def test_unsupported_actions_are_rejected_without_revision(bad_action):
    learner = FullContextLearner(seed=1, updates=0, schema=SCHEMA)
    with pytest.raises(ValueError):
        learner.predict(frame(2), [bad_action])
    assert learner.revision == 0 and learner.replay == []


def test_extra_future_metadata_and_malformed_history_are_rejected():
    learner = FullContextLearner(seed=1, updates=0, schema=SCHEMA)
    extra = frame(2)
    extra.future_outcome = outcome()
    with pytest.raises(ValueError):
        learner.predict(extra, [ACTION])
    action_extra = Action('q81', ACTION.args)
    object.__setattr__(action_extra, 'future_success', True)
    with pytest.raises(ValueError):
        learner.predict(frame(2), [action_extra])
    with pytest.raises(ValueError):
        learner.predict(frame(2), [ACTION], [(frame(0), ACTION, outcome())])
    with pytest.raises(TypeError):
        learner.predict(frame(2), [ACTION], future_outcome=outcome())
    with pytest.raises(ValueError):
        learner.predict(frame(2).to_dict(), [ACTION])
    invalid = frame(2)
    invalid.kinds[0] = 4
    with pytest.raises(ValueError):
        learner.predict(invalid, [ACTION])
    unsupported = frame(2)
    unsupported.kinds = np.asarray(unsupported.kinds)
    with pytest.raises(ValueError):
        learner.predict(unsupported, [ACTION])


def test_learning_rejects_changed_binding_even_for_duplicate_event():
    learner = FullContextLearner(seed=1, updates=0, schema=SCHEMA)
    learner.learn('event_1', frame(2), ACTION, outcome(), [])
    stored = normalized_snapshot(learner)
    other_binding = Frame([0], [0.0], [[0]], [[0]], ('n0',))
    for identifier in ('event_1', 'new_event'):
        with pytest.raises(ValueError):
            learner.learn(identifier, frame(2), ACTION, other_binding, [])
    assert normalized_snapshot(learner) == stored


def test_old_or_augmented_or_corrupted_checkpoints_are_not_silently_loaded():
    learner = FullContextLearner(seed=1, updates=0, schema=SCHEMA)
    value = normalized_snapshot(learner)
    with pytest.raises(ValueError):
        FullContextLearner.restore(LegacyLearner(seed=1, updates=0, schema=SCHEMA).snapshot())
    for key, replacement in [('future_truth', True), ('revision', 2), ('format', 'other')]:
        bad = copy.deepcopy(value)
        bad[key] = replacement
        with pytest.raises(ValueError):
            FullContextLearner.restore(bad)
    bad = copy.deepcopy(value)
    bad['weights']['0.operation.weight'] = [[float('nan')] * 4] * 2
    with pytest.raises(ValueError):
        FullContextLearner.restore(bad)
    bad = copy.deepcopy(value)
    bad['weights']['0.cell.weight_ih'] = [[0.0]]
    with pytest.raises(ValueError):
        FullContextLearner.restore(bad)


def test_model_operations_do_not_access_native_filesystem(monkeypatch):
    learner = FullContextLearner(seed=2, updates=1, schema=SCHEMA)
    # Let framework imports initialize before forbidding runtime file operations.
    learner.learn('warm_framework', frame(2), ACTION, outcome(), [])

    def forbidden(*args, **kwargs):
        raise AssertionError('baseline attempted filesystem/native access')

    for owner, name in ((builtins, 'open'), (io, 'open'), (os, 'open'),
                        (os, 'scandir'), (Sandbox, 'observe'), (Sandbox, 'evidence')):
        monkeypatch.setattr(owner, name, forbidden)
    learner.predict(frame(2), [ACTION])
    learner.learn('second', frame(2), ACTION, outcome(), [])
    restored = FullContextLearner.restore(normalized_snapshot(learner))
    assert restored.predict(frame(2), [ACTION]) == learner.predict(frame(2), [ACTION])
