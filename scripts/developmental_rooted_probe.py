"""Exposed architecture comparison: induced rooted-cell effect hypotheses.

All structural priors here are developer supplied, not discovered concepts.
No action semantics, task solutions, native IDs or output truth enter contexts.
This is a diagnostic alternative, not deployed cognition or fresh capability.
"""
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packages.action_core.world import Frame, Action
from packages.shared_world.relational import _value, _matrices


def rooted(frame, action, field, address):
    args = [frame.handles.index(h) for h in action.args]
    nodes = list(dict.fromkeys(args + list(address)))
    key = (action.op, field, tuple(nodes.index(i) for i in args),
           tuple(nodes.index(i) for i in address), tuple(frame.kinds[i] for i in nodes),
           tuple((name, tuple(matrix[i][j] for i in nodes for j in nodes))
                 for name, matrix in sorted({'parent': frame.parent, **_matrices(frame)}.items())))
    return key, nodes


def value(expr, frame, field, address, nodes):
    if expr[0] == 'keep':
        return _value(frame, field, address)
    if expr[0] == 'constant':
        return expr[1]
    return _value(frame, field, tuple(nodes[i] for i in expr[1:]))


def cells(frame):
    n = len(frame.handles)
    for field in ('kind', 'size'):
        for i in range(n):
            yield field, (i,)
    for field in _matrices(frame):
        yield from ((field, p) for p in itertools.product(range(n), repeat=2))


def run(source, native, output):
    raw = source.read_bytes()
    truth_raw = native.read_bytes()
    history = json.loads(raw)
    table = {}
    for record in history['records']:
        before, after = (Frame.from_dict(record[k]) for k in ('before', 'after'))
        action = Action.from_dict(record['action'])
        for field, address in cells(before):
            key, nodes = rooted(before, action, field, address)
            actual = _value(after, field, address)
            expressions = [('keep',), ('constant', actual)]
            expressions += [('copy',)+p for p in itertools.product(range(len(nodes)), repeat=len(address))]
            surviving = {e for e in expressions if value(e, before, field, address, nodes) == actual}
            table[key] = table[key] & surviving if key in table else surviving
    # Outcome file is exposed prior diagnostic evidence, never fresh evaluation.
    before = Frame.from_dict(history['records'][-1]['after'])
    queries = json.loads(truth_raw)
    results = []
    for row in queries['rows']:
        action = Action.from_dict(row['action'])
        forecast = {}
        for field, address in cells(before):
            key, nodes = rooted(before, action, field, address)
            forecast[(field, address)] = sorted({value(e, before, field, address, nodes)
                                               for e in table.get(key, ())})
        for cell in row['cells']:
            # Prior slot contains a repr tuple; only its field is needed.
            import ast
            field = ast.literal_eval(cell['slot'])[0]
            address = tuple(cell['address'])
            values = forecast[(field, address)]
            actual = cell['actual']
            category = ('UNKNOWN' if not values else
                        'SINGLETON_CORRECT' if len(values)==1 and actual in values else
                        'SINGLETON_WRONG' if len(values)==1 else
                        'SET_CONTAINS_TRUTH' if actual in values else 'SET_EXCLUDES_TRUTH')
            results.append({'action': row['action'], 'field': field, 'address': address,
                            'values': values, 'actual': actual, 'category': category,
                            'prior_category': cell['category']})
    report = {'scope': 'exposed representation diagnostic, not capability',
              'source_sha256': hashlib.sha256(raw).hexdigest(),
              'native_sha256': hashlib.sha256(truth_raw).hexdigest(),
              'counts': dict(Counter(r['category'] for r in results)),
              'contexts': len(table), 'contradictory_contexts': sum(not v for v in table.values()),
              'rows': results}
    assert source.read_bytes() == raw and native.read_bytes() == truth_raw
    with output.open('x') as stream:
        json.dump(report, stream, sort_keys=True, separators=(',', ':'))
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}))


if __name__ == '__main__':
    run(*(Path(p) for p in sys.argv[1:]))
