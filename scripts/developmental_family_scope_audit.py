"""Exposed historical scope audit, not a fresh capability trial or tuning run.

Same training as mixed-life v1. No learning from scope test rows; the two
declared-parent rows already used in training are explicitly labeled exposed.
Record wrong singletons separately from wrong sets and unresolved proposals.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_effect_families import EffectFamilies
from packages.action_core.world import Frame, Action
from packages.shared_world.relational import _value


def run(output):
    names = ['developmental-continual.json', 'developmental-online-eval.json',
             'developmental-composition-probe.json', 'developmental-rewrite-scope.json']
    sources = {n: (ROOT/'evidence'/n).read_bytes() for n in names}
    data = {n: json.loads(b) for n, b in sources.items()}
    scope = data[names[3]]['rows']
    training = data[names[0]]['records'] + data[names[1]]['records']
    training += [data[names[2]]['rows'][0]['native_record']]
    training += [r['record'] for r in scope if r['case'] in ('declared_absent', 'declared_present')]
    combined = EffectFamilies(training)
    rows = []
    for row in scope:
        record = row['record']
        before, after = (Frame.from_dict(record[k]) for k in ('before', 'after'))
        action = Action.from_dict(record['action'])
        result = {}
        for name, model in [('local', combined.local), ('structural', combined.structural), ('combined', combined)]:
            counts = Counter(); errors = []
            for field, address, values in model.predict(before, action, True):
                truth = _value(after, field, address)
                category = ('unknown' if not values else
                            ('wrong_singleton' if len(values) == 1 else 'wrong_set') if truth not in values else
                            'correct_singleton' if len(values) == 1 else 'correct_set')
                counts[category] += 1
                if category.startswith('wrong'):
                    errors.append(dict(field=field, address=address, proposed=values, actual=truth))
            result[name] = dict(counts=counts, errors=errors)
        rows.append(dict(case=row['case'], training_exposed=row['case'] in ('declared_absent', 'declared_present'), results=result))
    report = dict(scope='historical exposed diagnostic; no capability claim', training_count=len(training),
                  sources={n: hashlib.sha256(b).hexdigest() for n,b in sources.items()}, rows=rows)
    with output.open('x') as f:
        json.dump(report, f, sort_keys=True)
    for r in rows:
        print(r['case'], {k:v['counts'] for k,v in r['results'].items()})


if __name__ == '__main__': run(Path(sys.argv[1]))
