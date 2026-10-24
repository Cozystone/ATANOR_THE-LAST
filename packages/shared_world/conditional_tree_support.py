"""Bounded generic partial tree search over observed numeric predicates.

Maximize explained rows, then minimize splits; retain all tied trees. Unresolved
branches veto a query. Features/effects are supplied by experience, not task IDs.
Depth two is an explicit research compute bound, not universal concept learning.
"""
from dataclasses import dataclass
from functools import lru_cache
from .conditional_support import _features


@dataclass(frozen=True)
class TreeSupport:
    width: int
    symbols: frozenset
    alternatives: tuple
    covered: int
    splits: int

    def query(self, features):
        features = _features(features)
        if len(features) != self.width:
            raise ValueError('feature width mismatch')
        if self.symbols or not self.alternatives:
            return self.symbols
        result = set()
        for index, operator, threshold, yes, no in self.alternatives:
            condition = features[index] == threshold if operator == 'eq' else features[index] <= threshold
            values = (yes if condition else no).query(features)
            if not values:
                return frozenset()
            result.update(values)
        return frozenset(result)


def fit_tree(examples, depth=2):
    rows = tuple((_features(f), frozenset(s)) for f,s in examples)
    if not rows or any(len(f)!=len(rows[0][0]) for f,_ in rows):
        raise ValueError('nonempty fixed-width examples required')
    width = len(rows[0][0])

    @lru_cache(None)
    def solve(indices, remaining):
        common = frozenset.intersection(*(rows[i][1] for i in indices))
        if common:
            return TreeSupport(width, common, (), len(indices), 0)
        if remaining == 0:
            return TreeSupport(width, frozenset(), (), 0, 0)
        best = (0, 0); alternatives = []
        for column in range(width):
            for threshold in sorted({rows[i][0][column] for i in indices}):
                for operator in ('eq', 'le'):
                    yes = tuple(i for i in indices if (rows[i][0][column]==threshold if operator=='eq' else rows[i][0][column]<=threshold))
                    if not yes or len(yes)==len(indices):
                        continue
                    chosen = set(yes); no = tuple(i for i in indices if i not in chosen)
                    left, right = solve(yes,remaining-1), solve(no,remaining-1)
                    rank = (left.covered+right.covered, -(1+left.splits+right.splits))
                    candidate = (column,operator,threshold,left,right)
                    if rank > best:
                        best, alternatives = rank, [candidate]
                    elif rank == best and rank[0]:
                        alternatives.append(candidate)
        return TreeSupport(width,frozenset(),tuple(alternatives),best[0],-best[1])
    return solve(tuple(range(len(rows))),depth)
