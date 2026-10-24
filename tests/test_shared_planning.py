"""Synthetic mechanism tests; no native body, fresh task, or learning run."""
import copy
import math

import pytest

from packages.action_core.model import Forecast
from packages.action_core.planner import Goal
from packages.action_core.schema import OperationSchema
from packages.action_core.world import Action, Frame
from packages.shared_world.contracts import JointForecast
from packages.shared_world.planning import _bounded, choose


def observed(kinds=(0, 0)):
    n = len(kinds)
    return Frame(list(kinds), [0.0] * n, [[0] * n for _ in kinds],
                 [[0] * n for _ in kinds], tuple(f'n{i}' for i in range(n)))


def forecast(kinds=(0, 0), sizes=None):
    view = observed(kinds)
    return Forecast([[float(k == j) for j in range(3)] for k in kinds],
                    sizes or view.sizes, view.equal, view.parent, view.handles)


def soft(probability):
    result = forecast()
    result.kinds[1] = [1.0 - probability, probability, 0.0]
    return result


def identity(state):
    if type(state) is Forecast:
        return copy.deepcopy(state)
    return Forecast([[float(k == j) for j in range(3)] for k in state.kinds],
                    copy.deepcopy(state.sizes), copy.deepcopy(state.equal),
                    copy.deepcopy(state.parent), state.handles)


class Model:
    def __init__(self, names, handler):
        self.schema = OperationSchema(tuple((name, 1) for name in names))
        self.handler = handler
        self.calls = []

    def predict(self, state, actions, history=()):
        self.calls.append((copy.deepcopy(state), list(actions), copy.deepcopy(history)))
        return [self.handler(state, action) for action in actions]


def surface(names):
    return [Action(name, ('n0',)) for name in names]


GOAL = Goal('g', kinds=(('n1', 1),))


def test_whole_joint_outcomes_cannot_assert_an_impossible_conjunction():
    names = ('q11', 'q29')
    impossible = JointForecast([(0.5, forecast((1, 0))), (0.5, forecast((0, 1)))])
    fallback = forecast((1, 0))
    fallback.kinds[1] = [0.9, 0.1, 0.0]
    model = Model(names, lambda s, a: (impossible if a.op == names[0] else fallback, 0.0))
    goal = Goal('both', kinds=(('n0', 1), ('n1', 1)))
    action, prediction, nodes = choose(model, observed(), goal, surface(names), horizon=1)
    assert action.op == names[1]
    assert type(prediction) is Forecast and nodes == 2


def test_positive_correlation_is_not_destroyed_into_marginals():
    names = ('z2', 'z8')
    correlated = JointForecast([(0.5, forecast((1, 1))), (0.5, forecast())])
    fallback = JointForecast([(0.4, forecast((1, 1))), (0.6, forecast())])
    model = Model(names, lambda s, a: (correlated if a.op == names[0] else fallback, 0.0))
    goal = Goal('both', kinds=(('n0', 1), ('n1', 1)))
    action, prediction, _ = choose(model, observed(), goal, surface(names), horizon=1)
    assert action.op == names[0]
    assert prediction.probability(goal) == 0.5


def test_same_action_sequence_cannot_choose_each_branchs_best_continuation():
    names = ('t31', 't53', 't71', 't89')

    def handler(state, action):
        if action.op == names[0]:
            return JointForecast([(0.5, forecast((1, 0))), (0.5, forecast((2, 0)))]), 0.0
        if action.op == names[3]:
            return soft(0.65), 0.0
        kind = identity(state).kinds[0]
        succeeds = ((action.op == names[1] and kind[1] == 1)
                    or (action.op == names[2] and kind[2] == 1))
        return (forecast((0, 1)) if succeeds else identity(state)), 0.0

    model = Model(names, handler)
    action, prediction, nodes = choose(model, observed(), GOAL, surface(names))
    assert action.op == names[3]  # .65 immediate beats .5 expected two-step.
    assert GOAL.probability(prediction) == pytest.approx(0.65)
    assert nodes == sum(len(actions) for _, actions, _ in model.calls)


def test_all_roots_reach_depth_two_even_width_one_and_return_root_prediction():
    names = ('v4', 'v6', 'v9')

    def handler(state, action):
        if action.op == names[0]:
            return soft(0.4), 0.0
        if action.op == names[1]:
            return forecast((2, 0)), 0.0
        if identity(state).kinds[0][2] == 1:
            return forecast((2, 1)), 0.0
        return identity(state), 0.0

    model = Model(names, handler)
    action, prediction, nodes = choose(model, observed(), GOAL, surface(names), width=1, limit=12)
    assert action.op == names[1]
    assert GOAL.probability(prediction) == 0  # NOT the terminal success forecast.
    assert nodes == 12 and len(model.calls) == 4
    assert all(len(actions) == 3 for _, actions, _ in model.calls)


def test_branch_cap_does_not_renormalize_lost_probability_mass():
    names = ('c2', 'c4', 'c8')

    def handler(state, action):
        if action.op == names[0]:
            return JointForecast([(1 / 32, forecast((2, 0), [i / 32, 0.0]))
                                  for i in range(32)]), 0.0
        if action.op == names[2]:
            return soft(0.8), 0.0
        if identity(state).kinds[0][2] == 1:
            x = state.sizes[0]
            return JointForecast([(0.5, forecast((2, 1), [x, 0.0])),
                                  (0.5, forecast((2, 1), [x + 1 / 128, 0.0]))]), 0.0
        return identity(state), 0.0

    model = Model(names, handler)
    action, _, nodes = choose(model, observed(), GOAL, surface(names), limit=105)
    assert action.op == names[2]  # 64 equally weighted successes retain only .5.
    assert nodes == 105
    rows = _bounded([(1 / 64, forecast((2, 1), [i / 64, 0.0])) for i in range(64)])
    assert len(rows) == 32 and sum(weight for weight, _ in rows) == 0.5
    merged = _bounded([(1 / 64, forecast((2, 1))) for _ in range(64)])
    assert len(merged) == 1 and merged[0][0] == 1.0


def test_actual_history_is_unchanged_and_never_contains_imagined_forecasts():
    names = ('e7', 'e8')
    history = [(observed((2, 0)), Action(names[0], ('n0',)))]
    before = copy.deepcopy(history)
    model = Model(names, lambda s, a: (identity(s), 0.0))
    choose(model, observed(), GOAL, surface(names), history, horizon=3, width=1, limit=8)
    assert history == before
    assert any(type(state) is Forecast for state, _, _ in model.calls)
    assert all(past == before for _, _, past in model.calls)
    assert all(type(state) is Frame for _, _, past in model.calls for state, _ in past)


def test_predictor_mutation_does_not_change_callers_frame_or_history():
    class Mutator(Model):
        def predict(self, state, actions, history=()):
            result = super().predict(state, actions, history)
            state.kinds[0] = 2
            if history:
                history[0][0].sizes[0] = 0.75
            return result

    names = ('p3',)
    frame, history = observed(), [(observed((2, 0)), Action(names[0], ('n0',)))]
    before = copy.deepcopy((frame, history))
    model = Mutator(names, lambda s, a: (forecast((0, 1)), 0.0))
    choose(model, frame, GOAL, surface(names), history, horizon=1)
    assert (frame, history) == before


@pytest.mark.parametrize('horizon,limit', [(1, 1), (2, 5)])
def test_undersized_root_budget_is_rejected_before_predict(horizon, limit):
    model = Model(('k1', 'k2'), lambda s, a: (identity(s), 0.0))
    with pytest.raises(ValueError, match='budget insufficient'):
        choose(model, observed(), GOAL, surface(('k1', 'k2')), horizon=horizon, limit=limit)
    assert model.calls == []


def test_branch_expansion_budget_is_checked_before_partial_depth():
    names = ('b5', 'b7')
    joint = JointForecast([(0.5, forecast((1, 0))), (0.5, forecast((2, 0)))])
    model = Model(names, lambda s, a: (joint, 0.0))
    with pytest.raises(ValueError, match='full depth 2: need 10, limit 6'):
        choose(model, observed(), GOAL, surface(names), limit=6)
    assert len(model.calls) == 1 and sum(len(a) for _, a, _ in model.calls) == 2


def test_opaque_renaming_and_exact_ties_follow_surface_order():
    first = Model(('n77', 'h03'), lambda s, a: (forecast((0, 1)), 0.0))
    second = Model(('a91', 'zz2'), lambda s, a: (forecast((0, 1)), 0.0))
    a = choose(first, observed(), GOAL, surface(('n77', 'h03')))
    b = choose(second, observed(), GOAL, surface(('a91', 'zz2')))
    assert a[0].op == 'n77' and b[0].op == 'a91'
    assert a[1:] == b[1:]


def test_revisit_cost_uses_only_matching_failed_attempt_and_is_optional():
    names = ('u1', 'u2')
    model = Model(names, lambda s, a: (soft(0.7 if a.op == names[0] else 0.6), 0.0))
    actions = surface(names)
    history = [(observed(), actions[0])]
    assert choose(model, observed(), GOAL, actions, history, horizon=1)[0] == actions[0]
    assert choose(model, observed(), GOAL, actions, history, horizon=1,
                  failed_attempts=history)[0] == actions[1]
    assert choose(model, observed(), GOAL, actions, history, horizon=1,
                  failed_attempts=history, revisit_penalty=0)[0] == actions[0]
    other_failures = [(observed((2, 0)), actions[0])]
    assert choose(model, observed(), GOAL, actions, history, horizon=1,
                  failed_attempts=other_failures)[0] == actions[0]


@pytest.mark.parametrize('fault', ['action_handle', 'action_op', 'action_arity',
                                  'goal_handle', 'future_history', 'extra_history',
                                  'extra_forecast', 'prediction_scope', 'uncertainty'])
def test_caller_and_predictor_scope_faults_are_rejected(fault):
    names = ('j13',)
    prediction = forecast()
    model = Model(names, lambda s, a: (prediction, float('nan') if fault == 'uncertainty' else 0.0))
    actions, goal, history = surface(names), GOAL, []
    if fault == 'action_handle':
        actions = [Action(names[0], ('foreign',))]
    elif fault == 'action_op':
        actions = [Action('unbound', ('n0',))]
    elif fault == 'action_arity':
        actions = [Action(names[0], ('n0', 'n1'))]
    elif fault == 'goal_handle':
        goal = Goal('bad', kinds=(('foreign', 1),))
    elif fault == 'future_history':
        history = [(forecast(), actions[0])]
    elif fault == 'extra_history':
        past = observed()
        past.native_success = True
        history = [(past, actions[0])]
    elif fault == 'extra_forecast':
        prediction.verified = True
    elif fault == 'prediction_scope':
        prediction.parent[0][1] = 1
    with pytest.raises(ValueError):
        choose(model, observed(), goal, actions, history, horizon=1)


@pytest.mark.parametrize('kwargs', [{'horizon': True}, {'width': 0}, {'limit': 1.2},
                                   {'revisit_penalty': math.inf}, {'revisit_penalty': -1}])
def test_invalid_parameters_rejected(kwargs):
    model = Model(('d0',), lambda s, a: (identity(s), 0.0))
    with pytest.raises(ValueError):
        choose(model, observed(), GOAL, surface(('d0',)), **kwargs)


@pytest.mark.parametrize('family', ['legacy', 'full_context', 'relational'])
def test_actual_learner_interfaces_accept_common_planner_without_training(family):
    from packages.action_core.model import Learner
    from packages.shared_world.full_context import FullContextLearner
    from packages.shared_world.relational import RelationalLearner

    classes = {'legacy': Learner, 'full_context': FullContextLearner,
               'relational': RelationalLearner}
    names = ('f17', 'f39')
    schema = OperationSchema(tuple((name, 1) for name in names))
    learner = classes[family](schema=schema, seed=23)
    history = [(observed((2, 0)), Action(names[0], ('n0',)))]
    action, prediction, nodes = choose(learner, observed(), GOAL, surface(names), history, limit=6)
    assert action in surface(names) and nodes == 6
    assert type(prediction) is (JointForecast if family == 'relational' else Forecast)


def test_revisit_regression_successful_lifetime_cycle_is_not_a_failed_attempt():
    # S --a--> F completed an earlier goal; F --b--> S completed another.
    # A new goal asks for F again. Exact predictions and unchanged mechanics
    # must favor the known one-step a, not c -> d solely due to past success.
    names = ('a17', 'c39', 'd52', 'b68')
    actions = surface(names)
    a, c, d, b = actions
    start, complete, detour = (0, 0), (0, 1), (2, 0)
    effects = {(start, a.op): complete, (complete, b.op): start,
               (start, c.op): detour, (detour, d.op): complete}

    def handler(state, action):
        kinds = tuple(row.index(1.0) for row in identity(state).kinds)
        return forecast(effects.get((kinds, action.op), kinds)), 0.0

    model = Model(names, handler)
    history = [(observed(start), a), (observed(complete), b)]
    snapshot = copy.deepcopy(history)
    goal = Goal('new_goal_after_completed_cycle', kinds=(('n1', 1),))
    chosen, prediction, nodes = choose(model, observed(start), goal, actions,
                                       history, horizon=2, limit=20)
    assert chosen == a
    assert goal.probability(prediction) == 1.0 and nodes == 20
    assert history == snapshot
    assert all(past == snapshot for _, _, past in model.calls)


def test_revisit_regression_failed_attempts_do_not_replace_learning_history():
    names = ('m31', 'm47')
    actions = surface(names)
    model = Model(names, lambda s, a: (soft(0.7 if a == actions[0] else 0.6), 0.0))
    history = [(observed((2, 0)), actions[1])]
    failures = [(observed(), actions[0])]
    history_snapshot, failure_snapshot = copy.deepcopy((history, failures))
    chosen, _, _ = choose(model, observed(), GOAL, actions, history, horizon=1,
                           failed_attempts=failures)
    assert chosen == actions[1]  # Only the independently supplied no-change pair costs .2.
    assert all(past == history_snapshot for _, _, past in model.calls)
    assert history == history_snapshot and failures == failure_snapshot
    assert choose(model, observed(), GOAL, actions, history, horizon=1,
                  failed_attempts=failures, revisit_penalty=0)[0] == actions[0]
    assert choose(model, observed(), GOAL, actions, history, horizon=1,
                  failed_attempts=[(observed((2, 0)), actions[0])])[0] == actions[0]


@pytest.mark.parametrize('fault', ['hypothetical_view', 'unbound_action', 'extra_metadata',
                                  'changed_parent', 'foreign_handle', 'unbounded_sequence'])
def test_revisit_regression_failed_attempt_scope_is_revalidated(fault):
    names = ('s23',)
    action = surface(names)[0]
    failed_frame = observed()
    if fault == 'hypothetical_view':
        failed_frame = forecast()
    elif fault == 'unbound_action':
        action = Action('unbound', ('n0',))
    elif fault == 'extra_metadata':
        failed_frame.caller_says_native_no_change = True
    elif fault == 'changed_parent':
        failed_frame.parent[0][1] = 1
    elif fault == 'foreign_handle':
        action = Action(names[0], ('foreign',))
    failures = [(failed_frame, action)]
    if fault == 'unbounded_sequence':
        failures *= 257
    model = Model(names, lambda s, a: (identity(s), 0.0))
    with pytest.raises(ValueError):
        choose(model, observed(), GOAL, surface(names), horizon=1,
               failed_attempts=failures)
    assert model.calls == []
