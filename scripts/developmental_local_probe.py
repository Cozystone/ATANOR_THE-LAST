"""Exposed diagnostic: local expression support versus native consequences.

No policy, learning, default KEEP, or promotion. Every query is evaluated before
its outcome. Each native branch reconstructs the same sealed actual history.
"""
import json
import hashlib
from pathlib import Path
import sys
import tempfile
from collections import Counter
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packages.action_core.world import Sandbox, Action
from packages.shared_world.relational import RelationalLearner, _bindings, _groups, _evaluate, _value
from scripts.representation_r3_dev import configuration


def run(source, output):
    raw = source.read_bytes()
    data = json.loads(raw)
    model = RelationalLearner.restore(data['snapshot'])
    snapshot = model.snapshot()
    model._compile()
    cfg, _, reference, payload = configuration(3, 119031)
    rows = []
    with tempfile.TemporaryDirectory(prefix='atanor_local_probe_') as root:
        def restore(label):
            body = Sandbox(Path(root)/label, **cfg)
            for record in data['records']:
                assert body.observe().to_dict() == record['before']
                assert body.step(Action.from_dict(record['action'])) == record['success']
                assert body.observe().to_dict() == record['after']
            return body
        actions = restore('inventory').actions()
        for ordinal, action in enumerate(actions):
            body = restore(str(ordinal))
            before = body.observe()
            bindings = _bindings(before, action)
            groups = _groups(before, bindings, model.partitioned)
            programs = model.cache.get(action.op, {}).get('programs', [])
            forecasts = []
            for slot, addresses in groups.items():
                expressions = {e for p in programs for e in p.get(slot, [])}
                for address in addresses:
                    values = set()
                    unresolved = 0
                    for expression in expressions:
                        try:
                            values.add(_evaluate(expression, slot[0], address, before, bindings))
                        except KeyError:
                            unresolved += 1
                    forecasts.append((slot, address, sorted(values), unresolved))
            # No native outcome was consulted to form forecasts.
            success = body.step(action)
            after = body.observe()
            cells = []
            for slot, address, values, unresolved in forecasts:
                truth = _value(after, slot[0], address)
                category = ('UNKNOWN' if not values or unresolved else
                            'SINGLETON_CORRECT' if len(values)==1 and truth in values else
                            'SINGLETON_WRONG' if len(values)==1 else
                            'SET_CONTAINS_TRUTH' if truth in values else 'SET_EXCLUDES_TRUTH')
                cells.append({'slot': repr(slot), 'address': address, 'values': values,
                              'unresolved': unresolved, 'actual': truth, 'category': category})
            assert body._paths[reference].read_bytes() == payload
            rows.append({'action': action.to_dict(), 'success': success, 'cells': cells})
    assert model.snapshot() == snapshot and source.read_bytes() == raw
    counts = Counter(c['category'] for r in rows for c in r['cells'])
    result = {'scope': 'exposed diagnostic; conditional branches pooled, NOT validated applicability',
              'source_sha256': hashlib.sha256(raw).hexdigest(), 'counts': dict(counts),
              'native_queries': len(rows), 'capability_claim': False, 'rows': rows}
    with output.open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))

if __name__ == '__main__':
    run(Path(sys.argv[1]), Path(sys.argv[2]))
