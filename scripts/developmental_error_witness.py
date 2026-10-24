"""Trace every sealed conditional error to its actual training support."""
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_rooted_probe import rooted, cells
from packages.shared_world.relational import _value
from packages.action_core.world import Frame, Action


def run(training_path, result_path, output):
    raws = [p.read_bytes() for p in (training_path, result_path)]
    training, result = (json.loads(r)['records'] for r in raws)
    index = {}
    for ordinal, record in enumerate(training):
        before, after = (Frame.from_dict(record[k]) for k in ('before', 'after'))
        action = Action.from_dict(record['action'])
        for field, address in cells(before):
            key, nodes = rooted(before, action, field, address)
            index.setdefault(key, []).append({'record': ordinal, 'address': address,
                'sizes': [before.sizes[i] for i in nodes], 'actual': _value(after,field,address)})
    errors = []
    for ordinal, record in enumerate(result):
        before, after = (Frame.from_dict(record[k]) for k in ('before', 'after'))
        action = Action.from_dict(record['action'])
        for field, address, values in record['predictions']['conditional']:
            truth = _value(after, field, address)
            if not values or truth in values:
                continue
            key, nodes = rooted(before, action, field, address)
            errors.append({'record': ordinal, 'field':field, 'address':address,
                           'sizes':[before.sizes[i] for i in nodes], 'predicted':values,
                           'actual':truth, 'training':index.get(key,[])})
    report = {'source_sha256':[hashlib.sha256(r).hexdigest() for r in raws], 'errors':errors,
              'scope':'retrospective support audit, no evaluation retry'}
    with output.open('x') as stream:
        json.dump(report,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({'errors':len(errors), 'all_training_sizes_opposite':all(
        e['sizes'][0]>0 and e['sizes'][1]==0 and all(t['sizes'][0]==0 and t['sizes'][1]>0
        for t in e['training']) for e in errors)}))


if __name__=='__main__':
    run(*(Path(p) for p in sys.argv[1:]))
