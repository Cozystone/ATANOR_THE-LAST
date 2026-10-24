"""Explain sealed errors, not retry or tune a capability experiment."""
import hashlib
import itertools
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_rooted_probe import rooted, value, cells
from packages.action_core.world import Frame, Action
from packages.shared_world.relational import _value


def run(source, output):
    raw = source.read_bytes()
    records = json.loads(raw)['records']
    groups = {}
    for ordinal, record in enumerate(records):
        before, after = (Frame.from_dict(record[k]) for k in ('before', 'after'))
        action = Action.from_dict(record['action'])
        for field, address in cells(before):
            key, nodes = rooted(before, action, field, address)
            truth = _value(after, field, address)
            expressions = [('keep',), ('constant', truth)]
            expressions += [('copy',)+p for p in itertools.product(range(len(nodes)), repeat=len(address))]
            allowed = {e for e in expressions if value(e, before, field, address, nodes)==truth}
            groups.setdefault(key, []).append({'record': ordinal, 'field': field,
                'address': address, 'sizes': tuple(before.sizes[i] for i in nodes),
                'truth': truth, 'allowed': allowed})
    failures = []
    for key, examples in groups.items():
        common = set.intersection(*(e['allowed'] for e in examples))
        if common:
            continue
        numeric = {}
        for example in examples:
            numeric.setdefault(example['sizes'], []).append(example)
        subconflicts = sum(not set.intersection(*(e['allowed'] for e in group))
                           for group in numeric.values())
        witness = None
        for left, right in itertools.combinations(examples, 2):
            if not left['allowed'] & right['allowed']:
                witness = [{k: sorted(v) if k=='allowed' else v for k,v in e.items()}
                           for e in (left, right)]
                break
        failures.append({'context': repr(key), 'examples': len(examples),
                         'numeric_subgroups': len(numeric), 'numeric_conflicts': subconflicts,
                         'pair_witness': witness})
    report = {'source_sha256': hashlib.sha256(raw).hexdigest(),
              'conflicting_contexts': len(failures),
              'numeric_conflicts': sum(f['numeric_conflicts'] for f in failures),
              'scope': 'retrospective explanation only; exact numeric split can memorize',
              'failures': failures}
    assert source.read_bytes()==raw
    with output.open('x') as stream:
        json.dump(report, stream, sort_keys=True, separators=(',', ':'))
    print(json.dumps(report))


if __name__=='__main__':
    run(Path(sys.argv[1]), Path(sys.argv[2]))
