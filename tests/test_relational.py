"""Synthetic mechanism tests only; no native task/capability measurement."""
import copy
import json

import pytest

from packages.action_core.model import Forecast
from packages.action_core.schema import OperationSchema
from packages.action_core.world import Action, Frame
from packages.shared_world.contracts import JointForecast
from packages.shared_world.relational import RelationalLearner


SCHEMA = OperationSchema((('v17', 2), ('z9', 1)))


def scene(parent_present=True, size=.2):
    kinds = [1, 0, 2 if parent_present else 0, 1, 0]
    sizes = [size, 0., 0., size, 0.]
    equal = [[int(i in (0, 3) and j in (0, 3)) for j in range(5)] for i in range(5)]
    parent = [[int(i == 2 and j == 1) for j in range(5)] for i in range(5)]
    return Frame(kinds, sizes, equal, parent, tuple(f'n{i}' for i in range(5)))


def jointly_changed(before):
    after = copy.deepcopy(before)
    after.kinds[0], after.kinds[1] = 0, 1
    after.sizes[0], after.sizes[1] = 0., before.sizes[0]
    after.equal = [[int(i in (1, 3) and j in (1, 3)) for j in range(5)] for i in range(5)]
    return after


def permute(frame, action, order):
    inverse = {old: new for new, old in enumerate(order)}
    view = Frame([frame.kinds[i] for i in order], [frame.sizes[i] for i in order],
                 [[frame.equal[i][j] for j in order] for i in order],
                 [[frame.parent[i][j] for j in order] for i in order], frame.handles)
    moved = Action(action.op, tuple(f'n{inverse[frame.handles.index(h)]}' for h in action.args))
    return view, moved


def observed_forecast(frame):
    return Forecast([[int(k == i) for i in range(3)] for k in frame.kinds],
                    copy.deepcopy(frame.sizes), copy.deepcopy(frame.equal),
                    copy.deepcopy(frame.parent), frame.handles)


def train_parent_pair():
    model = RelationalLearner(SCHEMA)
    action = Action('v17', ('n0', 'n1'))
    for ordinal, size in enumerate((.15, .3, .45)):
        yes, no = scene(True, size), scene(False, size)
        assert model.learn(f'ok{ordinal}', yes, action, jointly_changed(yes), [])
        assert model.learn(f'no{ordinal}', no, action, no, [])
    return model, action


def test_parent_context_separates_joint_effect_after_learning():
    model, action = RelationalLearner(SCHEMA), Action('v17', ('n0', 'n1'))
    initial = model.predict(scene(), [action])[0]
    assert initial[0].outcomes[0][1].to_dict() == observed_forecast(scene()).to_dict()
    assert initial[1] == 1.
    model, action = train_parent_pair()
    yes, no = scene(True, .63), scene(False, .63)
    yes_prediction, _ = model.predict(yes, [action])[0]
    no_prediction, _ = model.predict(no, [action])[0]
    assert yes_prediction.outcomes[0][1].to_dict() == observed_forecast(jointly_changed(yes)).to_dict()
    assert no_prediction.outcomes[0][1].to_dict() == observed_forecast(no).to_dict()
    assert yes_prediction.outcomes[0][1].kinds[0] != no_prediction.outcomes[0][1].kinds[0]
    assert yes.parent == no.parent  # Only the unchanged third-entity KIND differs.


def test_unresolved_same_context_is_joint_mixture_not_independent_marginals():
    model = RelationalLearner(SCHEMA)
    before, action = scene(), Action('v17', ('n0', 'n1'))
    model.learn('one', before, action, jointly_changed(before), [])
    model.learn('two', before, action, before, [])
    joint, uncertainty = model.predict(before, [action])[0]
    assert type(joint) is JointForecast
    assert len(joint.outcomes) == 2
    assert sorted(weight for weight, _ in joint.outcomes) == [.5, .5]
    # The supported branches are (source absent,destination file) OR the
    # original pair, never their independent-product hybrid states.
    assert {tuple(tuple(r) for r in f.kinds[:2]) for _, f in joint.outcomes} == {
        ((1, 0, 0), (0, 1, 0)), ((0, 1, 0), (1, 0, 0))}
    assert uncertainty > .5


def test_handle_permutation_does_not_change_prediction():
    model, action = train_parent_pair()
    before = scene(True, .71)
    expected = jointly_changed(before)
    for order in ((4, 3, 2, 1, 0), (2, 0, 4, 1, 3), (1, 4, 3, 0, 2)):
        moved, moved_action = permute(before, action, order)
        moved_expected, _ = permute(expected, action, order)
        result, _ = model.predict(moved, [moved_action])[0]
        assert result.outcomes[0][1].to_dict() == observed_forecast(moved_expected).to_dict()


def test_snapshot_equivalence_and_no_mutating_predict():
    model, action = train_parent_pair()
    before = scene(True, .61)
    snapshot = json.loads(json.dumps(model.snapshot()))
    result = model.predict(before, [action])
    restored = RelationalLearner.restore(snapshot)
    other = restored.predict(before, [action])
    assert [(j.to_dict(), u) for j, u in result] == [(j.to_dict(), u) for j, u in other]
    assert model.snapshot() == snapshot
    assert restored.snapshot() == snapshot


def test_learning_targets_do_not_become_prediction_inputs():
    model, action = train_parent_pair()
    query = scene(False, .66)
    before = model.snapshot()
    prediction = model.predict(query, [action])[0][0].to_dict()
    # An unsubmitted future result cannot enter the predictor or its model.
    future = jointly_changed(query)
    future.kinds[4] = 2
    assert model.predict(query, [action])[0][0].to_dict() == prediction
    assert model.snapshot() == before
    # Future forecasts cannot masquerade as actual historical input.
    with pytest.raises(ValueError, match='actual Frame'):
        model.predict(query, [action], [(observed_forecast(future), action)])
    with pytest.raises(TypeError):
        model.predict(query, [action], after=future)


@pytest.mark.parametrize('forgery', ['forecast', 'envelope', 'mutated', 'subclass'])
def test_nonactual_or_malformed_caller_values_rejected_without_state_change(forgery):
    model, action = RelationalLearner(SCHEMA), Action('v17', ('n0', 'n1'))
    before = scene()
    if forgery == 'forecast':
        bad = observed_forecast(before)
    elif forgery == 'envelope':
        bad = {'verified': True, 'source': 'native', 'frame': before.to_dict()}
    elif forgery == 'mutated':
        bad = copy.deepcopy(before)
        bad.kinds[0] = 500
    else:
        class ClaimedFrame(Frame):
            pass
        bad = ClaimedFrame(**before.__dict__)
    initial = model.snapshot()
    with pytest.raises(ValueError):
        model.learn('forged', bad, action, before, [])
    assert model.snapshot() == initial


def test_data_is_copied_and_duplicate_observation_is_not_learned_twice():
    model, action = RelationalLearner(SCHEMA), Action('v17', ('n0', 'n1'))
    before = scene()
    after = jointly_changed(before)
    assert model.learn('event', before, action, after, [])
    snapshot = model.snapshot()
    assert not model.learn('event', before, action, after, [])
    after.kinds[0] = 2
    before.sizes[0] = .99
    assert model.snapshot() == snapshot


def test_opaque_operation_relabeling_is_equivalent():
    original, action = train_parent_pair()
    replacement = RelationalLearner(OperationSchema((('q82', 2), ('q83', 1))))
    for i, (before, _, after, history) in enumerate(original.rows):
        replacement.learn(i, before, Action('q82', action.args), after, history)
    query = scene(True, .77)
    left = original.predict(query, [action])[0][0].to_dict()
    right = replacement.predict(query, [Action('q82', action.args)])[0][0].to_dict()
    assert left == right


def test_unknown_operation_has_no_supplied_effect():
    model, action = train_parent_pair()
    before = scene()
    joint, uncertainty = model.predict(before, [Action('z9', ('n4',))])[0]
    assert joint.outcomes[0][1].to_dict() == observed_forecast(before).to_dict()
    assert uncertainty == 1.


def test_soft_forecast_stays_uncertain_and_is_not_argmaxed_to_truth():
    model, action = train_parent_pair()
    soft = observed_forecast(scene())
    soft.kinds[0] = [.5, .5, 0.]
    joint, uncertainty = model.predict(soft, [action])[0]
    assert joint.outcomes[0][1].kinds[0] == [.5, .5, 0.]
    assert uncertainty == 1.


def test_frozen_weights_do_not_change_with_new_observations():
    model, action = train_parent_pair()
    model.updates = 0
    before = scene()
    prediction = model.predict(before, [action])[0][0].to_dict()
    rows = copy.deepcopy(model.snapshot()['rows'])
    model.learn('new_failure', before, action, before, [])
    assert model.snapshot()['rows'] == rows
    assert model.predict(before, [action])[0][0].to_dict() == prediction


def test_locator_scope_drift_is_explicitly_rejected():
    model, action = RelationalLearner(SCHEMA), Action('v17', ('n0', 'n1'))
    before, after = scene(), scene()
    after.parent[2][1] = 0
    with pytest.raises(ValueError, match='scope changed'):
        model.learn('drift', before, action, after, [])


def test_checkpoint_cannot_inject_authority_fields_or_prediction_rows():
    model, _ = train_parent_pair()
    forged = model.snapshot()
    forged['verified'] = True
    with pytest.raises(ValueError, match='envelope'):
        RelationalLearner.restore(forged)
    forged = model.snapshot()
    forged['rows'][0]['before'] = observed_forecast(scene()).to_dict()
    with pytest.raises(ValueError):
        RelationalLearner.restore(forged)


def test_past_unchanged_third_entity_context_can_condition_effect():
    model, action = RelationalLearner(SCHEMA), Action('v17', ('n0', 'n1'))
    current = scene(True, .4)
    previous_action = Action('z9', ('n4',))
    old_yes = [(scene(True, .2), previous_action)]
    old_no = [(scene(False, .2), previous_action)]
    model.learn('past_yes', current, action, jointly_changed(current), old_yes)
    model.learn('past_no', current, action, current, old_no)
    yes = model.predict(current, [action], old_yes)[0][0].outcomes[0][1]
    no = model.predict(current, [action], old_no)[0][0].outcomes[0][1]
    assert yes.to_dict() == observed_forecast(jointly_changed(current)).to_dict()
    assert no.to_dict() == observed_forecast(current).to_dict()


def test_replay_budget_is_bounded_and_forecast_cannot_self_train():
    model, action = RelationalLearner(SCHEMA, max_records=2), Action('v17', ('n0', 'n1'))
    for i in range(4):
        before = scene(True, .1 * (i + 1))
        model.learn(i, before, action, jointly_changed(before), [])
    assert len(model.rows) == 2
    assert model.revision == 4
    prediction = model.predict(scene(), [action])[0][0].outcomes[0][1]
    old = model.snapshot()
    with pytest.raises(ValueError, match='actual Frame'):
        model.learn('self_claim', scene(), action, prediction, [])
    assert model.snapshot() == old


def test_rule_budget_overflow_is_visible_as_uncertainty():
    model, action = RelationalLearner(SCHEMA, max_rules=1), Action('v17', ('n0', 'n1'))
    yes, no = scene(), scene(False)
    model.learn('one', yes, action, jointly_changed(yes), [])
    low = model.predict(yes, [action])[0][1]
    model.learn('two', no, action, no, [])
    high = model.predict(yes, [action])[0][1]
    assert model.cache['v17']['unsupported'] == 1
    assert high > low


def test_soft_parent_relation_is_not_rounded_into_binding_fact():
    model, action = train_parent_pair()
    soft = observed_forecast(scene())
    soft.parent[2][1] = .5
    prediction, uncertainty = model.predict(soft, [action])[0]
    assert prediction.outcomes[0][1].parent[2][1] == .5
    assert uncertainty == 1.
