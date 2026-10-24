"""Typed joint hypotheses, never observations or authority receipts.

Native Frame is a scoped observation view, not a persistent entity identity.
These types carry predictions only; provenance/budget/completion are owned by
the supervisor and independently checked outside the learner process.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import copy

from packages.action_core.model import Forecast
from packages.action_core.relations import validate_relations


@dataclass
class ScopedPartialForecast:
    """Marginal possibility sets, NOT a joint distribution or observed state.

    Empty/missing cells mean unknown. Parent is immutable locator topology used
    solely to bind the scope. No score or success/authority field is accepted.
    This envelope is for execution journaling, not multi-step model rollout.
    """
    handles: tuple
    parent: list
    channels: list
    cells: list

    def __post_init__(self):
        n = len(self.handles)
        if not n or self.handles != tuple(f'n{i}' for i in range(n)):
            raise ValueError('invalid partial vocabulary')
        if (type(self.parent) is not list or len(self.parent) != n
                or any(type(r) is not list or len(r) != n for r in self.parent)
                or any(type(v) not in (int, float) or v not in (0, 1)
                       for r in self.parent for v in r)):
            raise ValueError('invalid partial topology')
        if (type(self.channels) is not list
                or any(type(c) is not str for c in self.channels)
                or len(set(self.channels)) != len(self.channels)):
            raise ValueError('invalid partial channels')
        validate_relations({c: [[0]] for c in self.channels}, 1)
        if type(self.cells) is not list:
            raise ValueError('invalid partial cells')
        seen = set()
        for cell in self.cells:
            if type(cell) not in (tuple, list) or len(cell) != 3:
                raise ValueError('invalid partial cell')
            field, address, values = cell
            if type(field) is not str or field not in ['kind', 'size', 'equal'] + self.channels:
                raise ValueError('unknown partial field')
            arity = 1 if field in ('kind', 'size') else 2
            if (type(address) not in (tuple, list) or len(address) != arity
                    or any(type(i) is not int or not 0 <= i < n for i in address)):
                raise ValueError('invalid partial address')
            key = (field, tuple(address))
            if key in seen:
                raise ValueError('duplicate partial cell')
            seen.add(key)
            if (type(values) is not list or any(type(v) not in (int, float)
                    or not math.isfinite(v) or not 0 <= v <= (2 if field == 'kind' else 1)
                    or (field == 'kind' and v not in (0, 1, 2)) for v in values)):
                raise ValueError('invalid possibility set')

    @property
    def relations(self):
        return dict.fromkeys(self.channels)  # vocabulary only, no inferred values

    def to_dict(self):
        return copy.deepcopy(dict(type='scoped_partial_forecast', truth_claim=False,
            handles=list(self.handles), parent=self.parent, channels=self.channels, cells=self.cells))

    @classmethod
    def from_dict(cls, value):
        if (type(value) is not dict or set(value) != {
                'type', 'truth_claim', 'handles', 'parent', 'channels', 'cells'}
                or value['type'] != 'scoped_partial_forecast' or value['truth_claim'] is not False):
            raise ValueError('invalid partial envelope')
        return cls(tuple(value['handles']), value['parent'], value['channels'], value['cells'])


def parse_execution_prediction(value):
    if type(value) is dict and value.get('type') == 'scoped_partial_forecast':
        return ScopedPartialForecast.from_dict(value)
    return parse_prediction(value)


@dataclass
class JointForecast:
    """Finite mixture of jointly updated world views; not calibrated by typing.

    An outcome can still contain marginal approximations. Exact conjunction
    evaluation is claimed only for discrete one-hot/binary outcome views.
    """
    outcomes: list  # [(weight: float, state: Forecast), ...]

    def __post_init__(self):
        if type(self.outcomes) is not list or not 1 <= len(self.outcomes) <= 32:
            raise ValueError('invalid outcome count')
        if any(type(row) not in (tuple, list) or len(row) != 2
               or type(row[1]) is not Forecast for row in self.outcomes):
            raise ValueError('invalid joint outcome shape')
        first = self.outcomes[0][1]
        for weight, state in self.outcomes:
            if (type(weight) not in (int, float) or not math.isfinite(weight)
                    or weight < 0 or type(state) is not Forecast):
                raise ValueError('invalid joint outcome')
            # Revalidate mutable legacy dataclass values, not just its tag.
            Forecast.from_dict(state.to_dict())
            if (state.handles != first.handles or state.parent != first.parent or
                    state.relations.keys() != first.relations.keys()):
                raise ValueError('inconsistent outcome scope')
        if abs(sum(w for w, _ in self.outcomes) - 1) > 1e-8:
            raise ValueError('outcome weights must sum to one')

    @property
    def handles(self):
        return self.outcomes[0][1].handles

    @property
    def parent(self):
        return self.outcomes[0][1].parent

    @property
    def relations(self):
        # For vocabulary checks only. Values can differ across joint outcomes.
        return self.outcomes[0][1].relations

    def probability(self, goal):
        return sum(weight * goal.probability(state) for weight, state in self.outcomes)

    def to_dict(self):
        return {'type': 'joint_forecast', 'outcomes': [
            {'weight': weight, 'state': state.to_dict()} for weight, state in self.outcomes]}

    @classmethod
    def from_dict(cls, value):
        if (type(value) is not dict or set(value) != {'type', 'outcomes'}
                or value['type'] != 'joint_forecast' or type(value['outcomes']) is not list):
            raise ValueError('invalid joint prediction envelope')
        rows = value['outcomes']
        if any(type(row) is not dict or set(row) != {'weight', 'state'} for row in rows):
            raise ValueError('unexpected joint prediction field')
        return cls([(row['weight'], Forecast.from_dict(row['state'])) for row in rows])


def parse_prediction(value):
    if type(value) is not dict:
        raise ValueError('prediction must be a mapping')
    if value.get('type') == 'joint_forecast':
        return JointForecast.from_dict(value)
    return Forecast.from_dict(value)


def prediction_probability(prediction, goal):
    return (prediction.probability(goal) if type(prediction) is JointForecast
            else goal.probability(prediction))
