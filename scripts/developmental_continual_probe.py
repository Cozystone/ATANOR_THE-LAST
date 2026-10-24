"""Fixed DEV falsification: persistent local hypotheses across native histories."""
import itertools
import json
from pathlib import Path
import random
import sys
import tempfile
from collections import Counter
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_rooted_probe import rooted, value, cells
from scripts.representation_r3_dev import configuration
from packages.action_core.world import Sandbox, Frame, Action
from packages.shared_world.relational import _value


def predict(table, before, action):
    output = []
    for field, address in cells(before):
        key, nodes = rooted(before, action, field, address)
        values = sorted({value(e, before, field, address, nodes) for e in table.get(key, ())})
        output.append((field, address, values))
    return output


def learn(table, before, action, after):
    for field, address in cells(before):
        key, nodes = rooted(before, action, field, address)
        truth = _value(after, field, address)
        candidates = [('keep',), ('constant', truth)]
        candidates += [('copy',)+p for p in itertools.product(range(len(nodes)), repeat=len(address))]
        survivors = {e for e in candidates if value(e, before, field, address, nodes)==truth}
        table[key] = table[key] & survivors if key in table else survivors


def score(prediction, after):
    return dict(Counter('unknown' if not values else
                        'wrong' if _value(after, field, address) not in values else
                        'correct_singleton' if len(values)==1 else 'correct_set'
                        for field, address, values in prediction))


def run(output):
    table, records, curves, anchors = {}, [], [], []
    with tempfile.TemporaryDirectory(prefix='atanor_continual_') as root:
        for episode, count in enumerate((3, 4, 3, 4)):
            seed = 43001 + episode
            rng = random.Random(seed)
            cfg, _, reference, payload = configuration(count, seed)
            body = Sandbox(Path(root)/str(episode), **cfg)
            for step in range(24):
                before = body.observe()
                action = rng.choice(body.actions())
                prediction = predict(table, before, action)
                success = body.step(action)
                after = body.observe()
                measured = score(prediction, after)
                record = {'episode': episode, 'step': step, 'before': before.to_dict(),
                          'action': action.to_dict(), 'after': after.to_dict(),
                          'success': success, 'prequential': measured, 'prediction': prediction}
                records.append(record)
                learn(table, before, action, after)
                if episode == 0:
                    anchors.append((before, action, after, score(predict(table, before, action), after)))
                assert body._paths[reference].read_bytes()==payload
            retention = Counter()
            for before, action, after, _ in anchors:
                retention.update(score(predict(table, before, action), after))
            curves.append({'episode': episode, 'contexts': len(table),
                           'contradictory': sum(not v for v in table.values()),
                           'anchor_retention': dict(retention)})
    total = Counter()
    for record in records:
        total.update(record['prequential'])
    result = {'scope': 'DEV random exposure, not autonomous experiment selection or transfer',
              'counts': dict(total), 'curves': curves, 'records': records,
              'verdict': 'REJECT_SUFFICIENCY' if total['wrong'] or any(c['contradictory'] for c in curves)
                         else 'SURVIVES_DEV_ONLY'}
    with output.open('x') as stream:
        json.dump(result, stream, sort_keys=True, separators=(',', ':'))
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))


if __name__ == '__main__':
    run(Path(sys.argv[1]))
