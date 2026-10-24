"""Research partial partitions: unresolved leaves abstain, never mean KEEP.

Only when the original complete learner has no explanation, keep tied
single-predicate partitions maximizing explained training rows. Any unresolved
leaf in a tied model vetoes prediction. This is an inductive bias, not confidence
calibration, sensor discovery, or evidence of newly invented language.
"""
from dataclasses import dataclass
from .conditional_support import fit, _features


@dataclass(frozen=True)
class PartialSupport:
    width: int
    alternatives: tuple

    def query(self, features):
        features = _features(features)
        if len(features) != self.width:
            raise ValueError('feature width mismatch')
        result = set()
        for index, operator, threshold, yes, no in self.alternatives:
            condition = features[index] == threshold if operator == 'eq' else features[index] <= threshold
            branch = yes if condition else no
            if not branch:
                return frozenset()
            result.update(branch)
        return frozenset(result)


def fit_partial(examples):
    rows = [(_features(f), frozenset(s)) for f,s in examples]
    complete = fit(rows)
    if complete.common or complete.alternatives:
        return complete
    best = 0; alternatives = []
    for index in range(complete.width):
        for threshold in sorted({f[index] for f,_ in rows}):
            for operator in ('eq', 'le'):
                yes, no = [], []
                for features, symbols in rows:
                    condition = features[index] == threshold if operator == 'eq' else features[index] <= threshold
                    (yes if condition else no).append(symbols)
                if not yes or not no:
                    continue
                left, right = frozenset.intersection(*yes), frozenset.intersection(*no)
                covered = (len(yes) if left else 0) + (len(no) if right else 0)
                candidate = (index, operator, threshold, left, right)
                if covered > best:
                    best, alternatives = covered, [candidate]
                elif covered and covered == best:
                    alternatives.append(candidate)
    return PartialSupport(complete.width, tuple(alternatives))
