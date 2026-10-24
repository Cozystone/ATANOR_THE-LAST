"""Bounded relational feature selection, not open-ended concept invention.

Inputs are anonymous integer channels for two entities. No filenames, operation
semantics, filesystem access, future observations, or source labels are accepted.
The human supplies the grammar and outcome target; experience selects the feature.
"""
from dataclasses import dataclass


def validate_pair(pair):
    if (type(pair) is not tuple or len(pair) != 2 or
            any(type(row) is not tuple for row in pair) or
            not pair[0] or len(pair[0]) != len(pair[1]) or
            any(type(x) is not int for row in pair for x in row)):
        raise ValueError('expected exactly two equal-width integer tuples')


@dataclass(frozen=True)
class Rule:
    column: int
    operator: str
    predictions: tuple[bool, bool]
    width: int

    def predict(self, pair):
        validate_pair(pair)
        if len(pair[0]) != self.width:
            raise ValueError('channel schema changed')
        a, b = pair[0][self.column], pair[1][self.column]
        value = {'eq': a == b, 'lt': a < b, 'le': a <= b}[self.operator]
        return self.predictions[int(value)]


def majority(labels):
    if not labels or any(type(y) is not bool for y in labels):
        raise ValueError('nonempty boolean outcomes required')
    return sum(labels) * 2 > len(labels)  # deterministic tie: False


def fit(pairs, labels, excluded_columns=()):
    if not pairs or len(pairs) != len(labels):
        raise ValueError('unaligned experience')
    default = majority(labels)
    for pair in pairs:
        validate_pair(pair)
    width = len(pairs[0][0])
    if any(len(pair[0]) != width for pair in pairs):
        raise ValueError('mixed observation schemas')
    best = None
    for column in range(width):
        if column in excluded_columns:
            continue
        for operator in ('eq', 'lt', 'le'):
            probe = Rule(column, operator, (False, True), width)
            bits = [probe.predict(pair) for pair in pairs]
            outputs = tuple(majority(ys) if ys else default for ys in
                            ([y for bit, y in zip(bits, labels) if bit == v]
                             for v in (False, True)))
            rule = Rule(column, operator, outputs, width)
            errors = sum(rule.predict(pair) != y for pair, y in zip(pairs, labels))
            if best is None or errors < best[0]:
                best = (errors, rule)
    if best is None:
        raise ValueError('no available feature')
    return best[1]
