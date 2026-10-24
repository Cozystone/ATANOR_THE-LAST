"""Experimental empirical controlled-predictive partition, NOT a general PSR.

Opaque JSON observations/actions; no relation vocabulary, goal or body semantics.
Tests are contiguous, actually executed action-observation futures (length<=3).
New dimensions require incompatible empirical futures in a currently merged
state, with >=2 observations on each side. Unknown is not zero probability.
This first estimator uses current observations as empirical history anchors:
it does NOT solve hidden-state inference or invent predictions for unseen anchors.
No unsupported merge, automatic promotion, authentication, or stochastic safety
theorem. The owning native runner supplies actual observations. Same test vector
feeds prediction and planning; a tabular baseline exposes lookup-only gains.
"""
from collections import Counter, defaultdict, deque
from fractions import Fraction
import json


def token(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


class PredictiveState:
    def __init__(self, *, max_length=3, max_tests=32, max_records=4096, min_support=2):
        if any(type(x) is not int or x < 1 for x in (max_length, max_tests, max_records, min_support)):
            raise ValueError('positive integer limits required')
        self.limits = dict(max_length=max_length, max_tests=max_tests,
                           max_records=max_records, min_support=min_support)
        self.records = []
        self.tests = []
        self.births = []
        self.stats = defaultdict(Counter)
        self.edges = defaultdict(Counter)
        self.witnesses = {}
        self._cache = {}

    def probability(self, anchor, test):
        actions, outcomes = test
        counts = self.stats.get((anchor, actions))
        if not counts or sum(counts.values()) < self.limits['min_support']:
            return None
        return Fraction(counts.get(outcomes, 0), sum(counts.values()))

    def state(self, observation, *, ablated=False):
        anchor = token(observation)
        return self._state(anchor, ablated)

    def _state(self, anchor, ablated=False):
        if ablated:
            return ()
        return tuple(self.probability(anchor, t) for t in self.tests)

    def _reindex(self):
        groups = defaultdict(Counter)
        for (anchor, action), outcomes in self.edges.items():
            groups[(self._state(anchor), action)].update(outcomes)
        self._cache = groups

    def distribution(self, observation, action, *, ablated=False, tabular=False):
        anchor, act = token(observation), token(action)
        if tabular:
            counts = self.edges.get((anchor, act), Counter())
        elif ablated:
            counts = Counter()
            for (_, a), outcomes in self.edges.items():
                if a == act:
                    counts.update(outcomes)
        else:
            # Unknown observation anchors do not inherit a known state merely
            # because all test estimates happen to be missing on both sides.
            if not any(s == anchor for s, _ in self.edges):
                return {}
            counts = self._cache.get((self._state(anchor), act), Counter())
        total = sum(counts.values())
        if total < self.limits['min_support']:
            return {}
        return {o: n / total for o, n in sorted(counts.items())}

    def predict(self, observation, action, **mode):
        distribution = self.distribution(observation, action, **mode)
        if len(distribution) != 1:
            return None
        return json.loads(next(iter(distribution)))

    def learn(self, before, action, after, *, boundary=False):
        if type(boundary) is not bool:
            raise ValueError('explicit episode boundary boolean required')
        if len(self.records) >= self.limits['max_records']:
            raise RuntimeError('record cap; no implicit forgetting')
        b, a, o = map(token, (before, action, after))
        if self.records and not boundary and self.records[-1]['after'] != b:
            raise ValueError('discontinuous observation; declare native reset boundary')
        old_prediction = self.predict(before, action)
        previous_state = self._state(b)
        row = dict(before=b, action=a, after=o, boundary=boundary)
        self.records.append(row)
        self.edges[(b, a)][o] += 1
        # Only windows which actually occurred: never splice hypothetical graph
        # paths into observed test counts, and never cross episode boundaries.
        for length in range(1, min(self.limits['max_length'], len(self.records)) + 1):
            window = self.records[-length:]
            if any(r['boundary'] for r in window[1:]):
                break
            actions = tuple(r['action'] for r in window)
            outcomes = tuple(r['after'] for r in window)
            anchor = window[0]['before']
            self.stats[(anchor, actions)][outcomes] += 1
            self.witnesses[(anchor, actions, outcomes)] = len(self.records)-length
        self._reindex()
        self._discover(dict(record=len(self.records)-1, old_prediction=old_prediction,
                            old_state=[None if p is None else str(p) for p in previous_state]))

    def _discover(self, trigger):
        # A new observed witness can expose ambiguity even when the predictor
        # already abstained. No dimensions born merely from low sample counts.
        while len(self.tests) < self.limits['max_tests']:
            grouped = defaultdict(list)
            for (anchor, actions), outcomes in self.stats.items():
                if sum(outcomes.values()) >= self.limits['min_support']:
                    grouped[(self._state(anchor), actions)].append((anchor, outcomes))
            candidates = []
            for (_, actions), rows in grouped.items():
                for left_index, (left, lc) in enumerate(rows):
                    for right, rc in rows[left_index+1:]:
                        # Mixed outcomes within an anchor may be stochastic or
                        # history aliasing: do not manufacture deterministic states.
                        if len(lc) != 1 or len(rc) != 1 or next(iter(lc)) == next(iter(rc)):
                            continue
                        outcome = next(iter(lc))
                        test = (actions, outcome)
                        if test in self.tests:
                            continue
                        candidates.append((len(actions), actions, outcome, left, right,
                                           self.witnesses[(left, actions, outcome)],
                                           self.witnesses[(right, actions, next(iter(rc)))]))
            if not candidates:
                break
            _, actions, outcomes, left, right, lrow, rrow = min(candidates)
            assert self._state(left) == self._state(right)
            test = (actions, outcomes)
            assert self.probability(left, test) == 1 and self.probability(right, test) == 0
            self.tests.append(test)
            self.births.append(dict(**trigger, test=[list(actions), list(outcomes)],
                                   left=left, right=right, witness_rows=[lrow, rrow]))
            self._reindex()

    def snapshot(self):
        return dict(format='empirical-predictive-state-v1', limits=self.limits,
                    records=self.records, tests=self.tests, births=self.births)

    @classmethod
    def restore(cls, data):
        if set(data) != {'format', 'limits', 'records', 'tests', 'births'} or data['format'] != 'empirical-predictive-state-v1':
            raise ValueError('invalid snapshot')
        model = cls(**data['limits'])
        for r in data['records']:
            if set(r) != {'before', 'action', 'after', 'boundary'}:
                raise ValueError('invalid observation record')
            model.learn(json.loads(r['before']), json.loads(r['action']),
                        json.loads(r['after']), boundary=r['boundary'])
        # Supplied state dimensions have no authority; reconstruct from history.
        if token(model.snapshot()) != token(data):
            raise ValueError('snapshot not bound to reconstructed history')
        return model

    def plan(self, observation, actions, goal, *, horizon=4, limit=4096, **mode):
        """Generic shortest supported plan; goal is explicit observation equality.

        No state mutation/learning. Unknown/mixed edges cannot be called safe.
        Prediction support is empirical, not an execution permission or proof.
        """
        if horizon < 1 or limit < 1:
            raise ValueError('positive planning budgets required')
        queue = deque([(observation, [])])
        seen = {token(observation)}
        queries = 0
        while queue:
            current, path = queue.popleft()
            if current == goal:
                return path, queries
            if len(path) >= horizon:
                continue
            for action in actions:
                if queries >= limit:
                    return None, queries
                queries += 1
                future = self.predict(current, action, **mode)
                if future is None or token(future) in seen:
                    continue
                seen.add(token(future))
                queue.append((future, path + [action]))
        return None, queries
