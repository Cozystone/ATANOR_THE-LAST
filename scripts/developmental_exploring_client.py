"""Opt-in research client: plan first, then bounded unknown-support exploration.

Reuse the measured fixed heuristic, not learned curiosity or a new authority.
Every action still passes native WorldSession budgets/provenance/verification.
No operation/goal-name routing; new records enter only through inherited learn.
"""
import copy
import random
from scripts.developmental_persistent_client import PersistentClient
from packages.shared_world.contracts import ScopedPartialForecast


class ExploringClient(PersistentClient):
    def __init__(self, records, *, exploration_seed=0, **kwargs):
        if type(exploration_seed) is not int:
            raise ValueError('integer seed required')
        self.exploration_seed = exploration_seed
        self._initializing = True
        super().__init__(records, **kwargs)
        self._initializing = False

    def snapshot(self):
        return {**super().snapshot(), 'exploration_seed': self.exploration_seed}

    def restore(self, checkpoint):
        state = copy.deepcopy(checkpoint)
        seed = state.pop('exploration_seed', None)
        if not (self._initializing and seed is None) and (type(seed) is not int or seed != self.exploration_seed):
            raise ValueError('exploration policy binding mismatch')
        super().restore(state)

    def choose(self, frame, goal, actions, history, *, failed_attempts=()):
        if not actions or self.limit <= 2 * len(actions):
            return None
        action, prediction, used = self._decision(frame, goal, actions,
                                                  limit=self.limit-len(actions))
        if action is not None:
            return action, prediction, used
        predictions = [self.adapter.predict_cells(frame, a) for a in actions]
        used += len(actions)
        scores = [(sum(not v for _, _, v in cells), sum(len(v)>1 for _, _, v in cells))
                  for cells in predictions]
        best = max(scores)
        if best == (0, 0):
            return None
        # Revision advances only on real, supervisor-delivered events, including
        # failed native actions. Restart reproduces the same decision state.
        rng = random.Random(self.exploration_seed + self.state['revision'])
        index = rng.choice([i for i, score in enumerate(scores) if score == best])
        forecast = ScopedPartialForecast(frame.handles, copy.deepcopy(frame.parent),
                                         list(frame.relations), predictions[index])
        return actions[index], forecast, used
