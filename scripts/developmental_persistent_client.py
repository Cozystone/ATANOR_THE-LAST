"""Research bridge to the existing supervisor, not a new Self or authority.

Partial forecasts retain unknown cells without manufacturing a complete state.
Checkpoints retain actual training rows;
the supervisor owns their provenance. No production registration or activation.
"""
import copy

from scripts.developmental_task_eval import Adapter
from packages.shared_world.partial_goal import arbitrate, PartialGoalPrediction
from packages.shared_world.partial_goal import select
from packages.shared_world.cost_ordered_search import search
from packages.shared_world.relational import _view
from packages.shared_world.contracts import ScopedPartialForecast


class PersistentClient:
    def __init__(self, records, *, schema, horizon=3, limit=4096, learning=True,
                 planner='beam', representation='local'):
        if representation not in ('local', 'families'):
            raise ValueError('unknown effect representation')
        self.representation = representation
        if planner not in ('beam', 'cost_ordered'):
            raise ValueError('unknown research planner')
        self.planner = planner
        self.schema = copy.deepcopy(schema)
        self.horizon, self.limit = horizon, limit
        if type(learning) is not bool:
            raise ValueError('learning mode must be boolean')
        self.learning = learning
        self.restore(dict(revision=0, records=records, events={}, learning=learning,
                          initial_count=len(records)))

    def snapshot(self):
        return copy.deepcopy(self.state)

    def restore(self, checkpoint):
        state = copy.deepcopy(checkpoint)
        if (set(state) != {'revision', 'records', 'events', 'learning', 'initial_count'}
                or state['learning'] is not self.learning
                or type(state['initial_count']) is not int
                or not 0 <= state['initial_count'] <= len(state['records'])
                or type(state['revision']) is not int
                or state['revision'] != len(state['events'])
                or type(state['records']) is not list
                or type(state['events']) is not dict):
            raise ValueError('invalid research checkpoint')
        model = Adapter(state['records'] if self.learning else
                        state['records'][:state['initial_count']], schema=self.schema)
        if self.representation == 'families':
            from scripts.developmental_effect_families import EffectFamilies
            model.model = EffectFamilies(state['records'] if self.learning else
                                         state['records'][:state['initial_count']])
        self.state, self.adapter = state, model

    def choose(self, frame, goal, actions, history, *, failed_attempts=()):
        result = self._decision(frame, goal, actions)
        return result if result[0] is not None else None

    def _decision(self, frame, goal, actions, *, limit=None):
        limit = self.limit if limit is None else limit
        if limit <= len(actions):
            return None, None, 0
        if self.planner == 'beam':
            action, prediction, used = arbitrate(self.adapter, frame, goal, actions,
                                                horizon=self.horizon, limit=limit)
        else:
            plan, predictions, used = search(self.adapter, frame, goal,
                [(a,) for a in actions], budget=self.horizon, limit=limit-len(actions))
            if plan:
                action, prediction = plan[0], _view(predictions[0])
            else:
                partial = select(self.adapter, frame, goal, actions)
                used += len(actions)
                action, prediction = (None, None) if partial is None else partial[:2]
        if action is None:
            return None, None, used
        if type(prediction) is PartialGoalPrediction:
            prediction = ScopedPartialForecast(frame.handles, copy.deepcopy(frame.parent),
                list(frame.relations), copy.deepcopy(prediction.cells))
        return action, prediction, used

    def learn(self, event_id, before, action, after, history):
        row = dict(before=before.to_dict(), action=action.to_dict(), after=after.to_dict())
        if event_id in self.state['events']:
            if self.state['events'][event_id] != row:
                raise ValueError('event identity reused with different observation')
            return False
        # Validate/rebuild is deliberately not repeated on each native event.
        if self.learning:
            self.adapter.model.learn([row])
        self.state['records'].append(copy.deepcopy(row))
        self.state['events'][event_id] = copy.deepcopy(row)
        self.state['revision'] += 1
        return True
