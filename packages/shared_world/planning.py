"""Bounded, open-loop mixture search; forecasts never become observed history.

This is a hypothesis-ranking mechanism, not a calibrated success guarantee.
Opaque action schemas grant syntax only; the external supervisor still owns
permissions, observation provenance, dispatch, and native completion checks.
"""
from __future__ import annotations

from collections import Counter
import copy
from dataclasses import dataclass
import math

from packages.action_core.model import Forecast
from packages.action_core.planner import Goal
from packages.action_core.schema import OperationSchema
from packages.action_core.world import Action, Frame
from .contracts import JointForecast


MAX_BRANCHES = 32
_VIEW_FIELDS = {'kinds', 'sizes', 'equal', 'parent', 'handles', 'relations'}


def _view(value, observed=False):
    expected = (Frame,) if observed else (Frame, Forecast)
    if type(value) not in expected or set(vars(value)) != _VIEW_FIELDS:
        raise ValueError('unsupported view type or extra view fields')
    return type(value).from_dict(copy.deepcopy(value.to_dict()))


def _action(value, schema, handles):
    if type(value) is not Action or set(vars(value)) != {'op', 'args'}:
        raise ValueError('unsupported action fields')
    schema.index(value)
    if any(handle not in handles for handle in value.args):
        raise ValueError('action outside observation scope')
    return value


def _prediction(value, frame):
    if type(value) is Forecast:
        clean = _view(value)
    elif type(value) is JointForecast and set(vars(value)) == {'outcomes'}:
        if type(value.outcomes) is not list:
            raise ValueError('invalid joint outcomes')
        for row in value.outcomes:
            if type(row) not in (list, tuple) or len(row) != 2:
                raise ValueError('invalid joint outcome row')
            if type(row[1]) is not Forecast:
                raise ValueError('joint outcome must remain a hypothesis')
            _view(row[1])
        clean = JointForecast.from_dict(copy.deepcopy(value.to_dict()))
    else:
        raise ValueError('unsupported prediction or extra prediction fields')
    if (clean.handles != frame.handles or clean.parent != frame.parent or
            clean.relations.keys() != frame.relations.keys()):
        raise ValueError('prediction changed bound observation scope')
    return clean


def _state_key(state):
    return (tuple(tuple(row) for row in state.kinds), tuple(state.sizes),
            tuple(tuple(row) for row in state.equal),
            tuple(tuple(row) for row in state.parent), state.handles,
            tuple((name, tuple(tuple(row) for row in matrix)) for name, matrix in sorted(state.relations.items())))


def _bounded(rows):
    """Merge exact identical hypotheses, retain highest mass, never renormalize."""
    merged = {}
    for weight, state in rows:
        if weight <= 0:
            continue
        key = _state_key(state)
        if key in merged:
            merged[key][0] += weight
        else:
            merged[key] = [weight, state]
    # Stable ties follow model branch order, not an interpretation of op names.
    return sorted(merged.values(), key=lambda row: -row[0])[:MAX_BRANCHES]


@dataclass
class _Sequence:
    states: list
    first: Action | None = None
    first_prediction: Forecast | JointForecast | None = None
    uncertainty: float = 0.0
    score: float = -math.inf


def choose(model, frame, goal, actions, history=(), *, horizon=2, width=8,
           limit=4096, revisit_penalty=0.2, failed_attempts=(), allow_partial=False,
           complete_only=False):
    """Return first action, its one-step prediction, and state-action evaluations.

    Each candidate is ONE action sequence applied across its entire weighted
    distribution. It cannot choose a different continuation per hypothetical
    outcome. Replan only after the supervisor obtains a real observation.

    Depths one and two cover every allowed first action; width starts with the
    frontier entering depth three. Budget insufficiency for any requested beam
    depth is explicit ValueError, never an unreported partial evaluation.

    Score = sum(retained mass * goal score) - .035 * depth
            - .1 * sqrt(uncertainty) - revisit_penalty * matching no-change count.
    Learning history never incurs a repetition cost. The separate, bounded
    failed_attempts input contains supervisor-observed no-change Frame/Action
    pairs, not inferred results from the next history row. Only the supervisor
    can bind each pair to its immediate native RESULT and compare evidence.
    Uncertainty conservatively retains earlier uncertainty and charges omitted
    probability mass as uncertainty one; this is a heuristic, not a bound.
    Soft Forecast outcomes retain Goal's documented mean-field limitation.
    """
    if type(allow_partial) is not bool:
        raise ValueError('allow_partial must be bool')
    if type(complete_only) is not bool:
        raise ValueError('complete_only must be bool')
    if any(type(v) is not int or v < 1 for v in (horizon, width, limit)):
        raise ValueError('positive integer planning budgets required')
    if (type(revisit_penalty) not in (int, float)
            or not math.isfinite(revisit_penalty) or revisit_penalty < 0):
        raise ValueError('invalid revisit penalty')
    current = _view(frame, observed=True)
    if type(goal) is not Goal or set(vars(goal)) != {'id', 'kinds', 'equal', 'sizes', 'relations'}:
        raise ValueError('unsupported goal fields')
    goal = Goal.from_dict(copy.deepcopy(goal.to_dict()))
    goal.validate_handles(current.handles)
    schema = getattr(model, 'schema', None)
    if type(schema) is not OperationSchema or set(vars(schema)) != {'entries'}:
        raise ValueError('model must expose its bound operation schema')
    schema = OperationSchema.from_data(schema.to_data())
    if type(actions) not in (list, tuple) or not actions:
        raise ValueError('nonempty action surface required')
    actions = tuple(_action(a, schema, current.handles) for a in actions)
    if len(set(actions)) != len(actions):
        raise ValueError('duplicate action surface')
    if type(history) not in (list, tuple):
        raise ValueError('actual history sequence required')
    actual = []
    for row in history:
        if type(row) not in (list, tuple) or len(row) != 2:
            raise ValueError('invalid actual history row')
        observed = _view(row[0], observed=True)
        if observed.handles != current.handles or observed.parent != current.parent:
            raise ValueError('actual history outside observation scope')
        actual.append((observed, _action(row[1], schema, current.handles)))
    if type(failed_attempts) not in (list, tuple) or len(failed_attempts) > 256:
        raise ValueError('bounded failed attempt sequence required')
    no_change = []
    for row in failed_attempts:
        if type(row) not in (list, tuple) or len(row) != 2:
            raise ValueError('invalid failed attempt row')
        observed = _view(row[0], observed=True)
        if observed.handles != current.handles or observed.parent != current.parent:
            raise ValueError('failed attempt outside observation scope')
        no_change.append((observed, _action(row[1], schema, current.handles)))
    revisits = Counter(a for observed, a in no_change
                       if observed.to_dict() == current.to_dict())
    action_count = len(actions)
    minimum = action_count * (1 + action_count if horizon >= 2 else 1)
    if limit < minimum:
        raise ValueError('budget insufficient for complete root coverage')
    frontier = [_Sequence([(1.0, current)])]
    best = None
    used = 0
    for depth in range(1, horizon + 1):
        required = sum(len(node.states) for node in frontier) * action_count
        if used + required > limit:
            raise ValueError(f'budget insufficient for full depth {depth}: '
                             f'need {used + required}, limit {limit}')
        expanded = []
        for node in frontier:
            rows_by_action = [[] for _ in actions]
            uncertainty_by_action = [0.0 for _ in actions]
            root_predictions = None
            for mass, state in node.states:
                # Isolate caller-owned observations and prior rows from an
                # accidental mutating predictor. No imagined row is appended.
                supplied = _view(state)
                supplied_history = [(_view(f, observed=True), a) for f, a in actual]
                used += action_count
                predicted = model.predict(supplied, list(actions), supplied_history)
                if type(predicted) is not list or len(predicted) != action_count:
                    raise ValueError('prediction count does not match action surface')
                clean_predictions = []
                for index, row in enumerate(predicted):
                    # Explicit opt-in absence is not an unchanged-state forecast.
                    # No fabricated outcome enters the search or learning history.
                    if row is None and allow_partial:
                        clean_predictions.append(None)
                        uncertainty_by_action[index] += mass
                        continue
                    if type(row) not in (list, tuple) or len(row) != 2:
                        raise ValueError('invalid prediction row')
                    prediction = _prediction(row[0], current)
                    uncertainty = row[1]
                    if (type(uncertainty) not in (int, float)
                            or not math.isfinite(uncertainty)
                            or not 0 <= uncertainty <= 1):
                        raise ValueError('invalid prediction uncertainty')
                    clean_predictions.append(prediction)
                    outcomes = (prediction.outcomes if type(prediction) is JointForecast
                                else [(1.0, prediction)])
                    rows_by_action[index].extend(
                        (mass * weight, branch) for weight, branch in outcomes)
                    uncertainty_by_action[index] += mass * uncertainty
                if node.first is None:
                    root_predictions = clean_predictions
            for index, action in enumerate(actions):
                states = _bounded(rows_by_action[index])
                if allow_partial and not states:
                    continue
                retained_mass = sum(weight for weight, _ in states)
                missing_mass = max(0.0, 1.0 - retained_mass)
                uncertainty = max(node.uncertainty,
                                  min(1.0, uncertainty_by_action[index] + missing_mass))
                first = node.first if node.first is not None else action
                prediction = (node.first_prediction if node.first is not None
                              else root_predictions[index])
                expected = sum(weight * goal.probability(state) for weight, state in states)
                score = (expected - 0.035 * depth - 0.1 * math.sqrt(uncertainty)
                         - revisit_penalty * revisits[first])
                child = _Sequence(states, first, prediction, uncertainty, score)
                expanded.append(child)
                complete=(abs(retained_mass-1.)<=1e-12 and uncertainty==0 and
                          all(goal.probability(state)==1 for _,state in states))
                if (not complete_only or complete) and (best is None or score > best.score):
                    best = child
        # All roots enter depth two, even if width=1. Later beam ranking is
        # stable in traversal/action-surface order for exactly equal scores.
        frontier = (expanded if depth == 1 else
                    sorted(expanded, key=lambda node: -node.score)[:width])
    if best is None:
        return None, None, used
    return best.first, best.first_prediction, used
