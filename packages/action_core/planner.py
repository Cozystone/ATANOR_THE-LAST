"""Goal-conditioned bounded receding-horizon planning, no filesystem semantics."""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
import math
import re

import numpy as np

from .model import HISTORY
from .world import Action, Frame


@dataclass(frozen=True)
class Goal:
    id: str
    kinds: tuple = ()   # ((opaque handle, desired kind), ...)
    equal: tuple = ()   # ((opaque handle, opaque handle), ...)
    sizes: tuple = ()   # exact normalized observed file-size scalar constraints
    relations: tuple = ()  # (opaque channel, left handle, right handle, binary value)

    def __post_init__(self):
        if (type(self.id) is not str or not self.id.strip() or not (self.kinds or self.equal or self.sizes or self.relations) or
                type(self.kinds) not in (tuple, list) or type(self.equal) not in (tuple, list) or
                type(self.sizes) not in (tuple, list) or type(self.relations) not in (tuple, list)):
            raise ValueError('nonempty goal required')
        for row in self.kinds:
            if (type(row) not in (tuple, list) or len(row) != 2 or
                    type(row[0]) is not str or not row[0] or
                    type(row[1]) is not int or row[1] not in (0, 1, 2)):
                raise ValueError('invalid kind goal')
        for row in self.equal:
            if (type(row) not in (tuple, list) or len(row) != 2 or
                    any(type(h) is not str or not h for h in row)):
                raise ValueError('invalid equality goal')
        # A conjunction is a set of literals, not a weighting scheme. Equality
        # is symmetric; repeated/reversed pairs must not change its score.
        object.__setattr__(self, 'kinds', tuple(sorted({tuple(row) for row in self.kinds})))
        object.__setattr__(self, 'equal', tuple(sorted({tuple(sorted(row)) for row in self.equal})))
        for row in self.sizes:
            if (type(row) not in (tuple, list) or len(row) != 2 or type(row[0]) is not str or not row[0] or
                    type(row[1]) not in (int, float) or not math.isfinite(row[1]) or not 0 <= row[1] <= 1):
                raise ValueError('invalid size constraint')
        object.__setattr__(self, 'sizes', tuple(sorted({tuple(row) for row in self.sizes})))
        if len(dict(self.sizes)) != len(self.sizes):
            raise ValueError('conflicting size constraints')
        for row in self.relations:
            if (type(row) not in (tuple, list) or len(row) != 4 or
                    type(row[0]) is not str or not re.fullmatch(r'r_[a-z0-9_]{1,48}', row[0]) or
                    any(type(h) is not str or not h for h in row[1:3]) or
                    type(row[3]) is not int or row[3] not in (0, 1)):
                raise ValueError('invalid relation goal')
        object.__setattr__(self, 'relations', tuple(sorted({tuple(row) for row in self.relations})))
        if len({row[:3] for row in self.relations}) != len(self.relations):
            raise ValueError('conflicting relation constraints')
        self._required_kinds()

    def _required_kinds(self):
        required = {}
        for handle, value in self.kinds:
            if handle in required and required[handle] != value:
                raise ValueError('contradictory kind requirements')
            required[handle] = value
        # This is the public relation schema: content equality is defined only
        # for files. It states no action effect or filesystem solution plan.
        for pair in self.equal:
            for handle in pair:
                if handle in required and required[handle] != 1:
                    raise ValueError('content equality requires file endpoints')
                required[handle] = 1
        for handle, _ in self.sizes:
            if handle in required and required[handle] != 1:
                raise ValueError('size constraints require a file')
            required[handle] = 1
        return required

    def validate_handles(self, handles):
        if (any(h not in handles for h, _ in self.kinds + self.sizes) or
                any(h not in handles for row in self.equal for h in row) or
                any(h not in handles for row in self.relations for h in row[1:3])):
            raise ValueError('unknown goal handle')

    def to_dict(self):
        result = {"id": self.id, "kinds": [list(row) for row in self.kinds],
                "equal": [list(row) for row in self.equal]}
        if self.sizes:
            result.update(goal_version=2, sizes=[list(row) for row in self.sizes])
        if self.relations:
            result.update(goal_version=3, sizes=[list(row) for row in self.sizes],
                          relations=[list(row) for row in self.relations])
        return result

    @classmethod
    def from_dict(cls, obj):
        legacy = {'id', 'kinds', 'equal'}
        if type(obj) is dict and set(obj) == legacy | {'goal_version', 'sizes', 'relations'}:
            if type(obj['goal_version']) is not int or obj['goal_version'] != 3 or not obj['relations']:
                raise ValueError('invalid relation goal version')
            return cls(obj['id'], obj['kinds'], obj['equal'], obj['sizes'], obj['relations'])
        if (type(obj) is not dict or set(obj) not in (legacy, legacy | {'goal_version', 'sizes'}) or
                ('goal_version' in obj and (obj['goal_version'] != 2 or not obj['sizes']))):
            raise ValueError("invalid goal fields")
        return cls(obj["id"], obj["kinds"], obj["equal"], obj.get('sizes', ()))

    def probability(self, frame):
        """Typed unique-conjunction score, NOT a calibrated joint probability.

        For soft forecasts this is a mean-field product heuristic: every required
        kind appears once, every non-reflexive equality pair once. It lies in
        [0, 1] and never exceeds any included factor. Correlations can make it
        over- or underestimate the true joint probability; it is not a bound on
        that unknown joint. A valid one-hot observation matches native holds().
        """
        self.validate_handles(frame.handles)
        handles = list(frame.handles)
        k = np.asarray(frame.kinds)
        if k.ndim == 1:
            k = np.eye(3)[k.astype(int)]
        factors = [float(k[handles.index(handle), value])
                   for handle, value in self._required_kinds().items()]
        for a, b in self.equal:
            if a != b:  # A file is content-equal to itself; no duplicate random event.
                factors.append(float(frame.equal[handles.index(a)][handles.index(b)]))
        factors.extend(float(abs(frame.sizes[handles.index(h)] - wanted) <= 1e-12)
                       for h, wanted in self.sizes)
        for channel, left, right, wanted in self.relations:
            if channel not in frame.relations:
                raise ValueError('unobserved goal relation channel')
            value = float(frame.relations[channel][handles.index(left)][handles.index(right)])
            factors.append(value if wanted else 1 - value)
        if any(not math.isfinite(p) or not 0 <= p <= 1 for p in factors):
            raise ValueError('invalid goal forecast factor')
        return math.prod(factors)

    def holds(self, evidence):
        """Check native receipts; caller must obtain them independently from the body.

        This function cannot authenticate a caller-created evidence dictionary.
        The supervisor/replay verifier owns that observation boundary.
        """
        if type(evidence) is not dict:
            return False
        # Legacy native receipts do not carry relational evidence. Never silently
        # certify a relational goal from kinds/content alone. The supervisor must
        # independently verify such goals against the real body.
        if self.relations:
            return False
        for handle, value in self._required_kinds().items():
            item = evidence.get(handle)
            if type(item) is not dict or type(item.get('kind')) is not int or item['kind'] != value:
                return False
        for a, b in self.equal:
            x, y = evidence[a], evidence[b]
            left, right = x.get('sha256'), y.get('sha256')
            if (type(left) is not str or len(left) != 64 or
                    any(c not in '0123456789abcdef' for c in left) or left != right):
                return False
        for handle, wanted in self.sizes:
            size = evidence[handle].get('size_bytes')
            if (type(size) is not int or size < 0 or
                    abs(min(1., math.log1p(size) / 16) - wanted) > 1e-12):
                return False
        return True


def choose(model, frame, goal, actions, history=(), *, horizon=3, width=3, limit=384, uncertainty_weight=0.5, cover_root=False, revisit_weight=0.0):
    """Bounded forecast search with optional soft observed-revisit cost.

    Revisit counts use only exact matching observed Frames supplied by the
    supervisor, never imagined states. Frame type alone is not authentication.
    The cost is a heuristic, not a claim that a repeated action cannot succeed:
    stochastic retries may be useful. No action is banned or prediction changed.
    """
    if horizon < 1 or width < 1 or limit < 1 or not actions:
        raise ValueError("empty action surface or planning budget")
    if not math.isfinite(uncertainty_weight) or uncertainty_weight < 0:
        raise ValueError('invalid uncertainty weight')
    if type(revisit_weight) not in (int, float) or not math.isfinite(revisit_weight) or revisit_weight < 0:
        raise ValueError('invalid revisit weight')
    if cover_root and horizon >= 2 and limit < len(actions) * (1 + len(actions)):
        raise ValueError('budget insufficient for requested two-step root coverage')
    goal.validate_handles(frame.handles)
    actual_history = list(history)
    revisits = Counter()
    if revisit_weight and type(frame) is Frame:
        observed_now = frame.to_dict()
        for observed, action in actual_history:
            if type(observed) is Frame and type(action) is Action and observed.to_dict() == observed_now:
                revisits[action] += 1
    frontier = [(0.0, frame, actual_history, None, None)]
    best, used = None, 0
    for depth in range(horizon):
        expanded = []
        for _, state, past, first, first_prediction in frontier:
            candidates = actions[:max(0, limit - used)]
            if not candidates:
                break
            predicted = model.predict(state, candidates, past)
            used += len(candidates)
            for action, (future, uncertainty) in zip(candidates, predicted):
                p = goal.probability(future)
                # Forecast utility is NOT a completion certificate.
                score = p - 0.035 * (depth + 1) - uncertainty_weight * math.sqrt(max(0, uncertainty))
                start = first or action
                if revisit_weight:
                    # Keep this first-action cost at every depth: an optimistic
                    # imagined continuation must not erase observed repetition.
                    score -= revisit_weight * revisits[start]
                first_p = first_prediction if first_prediction is not None else future
                row = (score, future, (past + [(state, action)])[-HISTORY:], start, first_p)
                expanded.append(row)
                if best is None or score > best[0]:
                    best = row
        if not expanded:
            break
        # An enabling action may have low immediate terminal-goal value. Do not
        # discard it before examining its consequences when coverage is requested.
        keep = len(actions) if cover_root and depth == 0 else width
        frontier = sorted(expanded, key=lambda r: r[0], reverse=True)[:keep]
    if best is None:
        raise RuntimeError("no candidate evaluated")
    return best[3], best[4], used
