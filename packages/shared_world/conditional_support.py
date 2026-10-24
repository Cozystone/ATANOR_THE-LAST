"""Experimental finite conditional hypothesis support, never authority.

Examples supply generic numeric features and sets of surviving effect symbols.
On conflict, retain ALL consistent one-predicate partitions over observed values,
not a hand-picked threshold or task-specific rule. No recursive search, latent
truth guarantee, prediction-as-observation, or automatic production promotion.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ConditionalSupport:
    width: int
    common: frozenset
    alternatives: tuple

    def query(self, features):
        features = _features(features)
        if len(features) != self.width:
            raise ValueError('feature width mismatch')
        if self.common:
            return self.common
        result = set()
        for index, operator, threshold, yes, no in self.alternatives:
            condition = (features[index] == threshold if operator == 'eq'
                         else features[index] <= threshold)
            result.update(yes if condition else no)
        return frozenset(result)


def _features(values):
    values = tuple(values)
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError('finite numeric features required')
    return values


def fit(examples):
    """Fit from actual-example hypotheses; caller owns native provenance.

Empty returned support means unresolved, not permission to default to KEEP.
The primitive cannot authenticate that a caller's examples actually happened.
"""
    rows = [(_features(features), frozenset(symbols)) for features, symbols in examples]
    if not rows:
        raise ValueError('at least one observed example required')
    width = len(rows[0][0])
    if any(len(features) != width for features, _ in rows):
        raise ValueError('inconsistent feature width')
    common = frozenset.intersection(*(symbols for _, symbols in rows))
    if common:
        return ConditionalSupport(width, common, ())
    alternatives = []
    for index in range(width):
        for threshold in sorted({features[index] for features, _ in rows}):
            for operator in ('eq', 'le'):
                yes, no = [], []
                for features, symbols in rows:
                    condition = features[index] == threshold if operator == 'eq' else features[index] <= threshold
                    (yes if condition else no).append(symbols)
                if not yes or not no:
                    continue
                left, right = frozenset.intersection(*yes), frozenset.intersection(*no)
                if left and right:
                    alternatives.append((index, operator, threshold, left, right))
    return ConditionalSupport(width, frozenset(), tuple(alternatives))
