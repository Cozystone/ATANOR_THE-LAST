"""Counterexample-triggered bounded representation proposal, not promotion authority.

Given actual transitions and anonymous raw channels, find a comparison that
reduces contradictory successors of the old view. No goal labels, native paths,
field names, filesystem access, or special operation semantics. This is finite
feature search over a human-provided grammar, NOT unconstrained concept invention.
"""
from collections import Counter, defaultdict
import json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def validate(records):
    if type(records) is not list or not 2 <= len(records) <= 512:
        raise ValueError('bounded transition batch required')
    width = None
    for record in records:
        if type(record) is not dict or set(record) != {'before', 'action', 'after', 'raw_before'}:
            raise ValueError('only observed transition and raw channels accepted')
        raw = record['raw_before']
        if (type(raw) is not list or not raw or any(type(row) is not list or not row for row in raw) or
                len(raw) != len(record['before']['handles']) or
                any(type(value) is not int for row in raw for value in row)):
            raise ValueError('invalid raw observation shape')
        width = len(raw[0]) if width is None else width
        if any(len(row) != width for row in raw):
            raise ValueError('raw schema changed')
    return width


def relation(raw, column, operator):
    def compare(a, b):
        return {'eq': a == b, 'lt': a < b, 'le': a <= b}[operator]
    return [[int(compare(a[column], b[column])) for b in raw] for a in raw]


def ambiguity(records, feature=None):
    buckets = defaultdict(Counter)
    for record in records:
        key = [record['before'], record['action']]
        if feature:
            key.append(relation(record['raw_before'], feature['column'], feature['operator']))
        buckets[canonical(key)][canonical(record['after'])] += 1
    return sum(sum(counts.values()) - max(counts.values()) for counts in buckets.values())


def propose(records):
    width = validate(records)
    baseline = ambiguity(records)
    if baseline == 0:
        return None  # no experienced contradiction, no speculative new organ
    best, best_error = None, baseline
    for column in range(width):
        for operator in ('eq', 'lt', 'le'):
            expression = {'column': column, 'operator': operator}
            error = ambiguity(records, expression)
            if error < best_error:
                best, best_error = expression, error
    return None if best is None else {'format': 'relation-proposal-v1', 'width': width, **best}


if __name__ == '__main__':
    import sys
    records = json.loads(sys.stdin.read())
    print(json.dumps(propose(records)))
