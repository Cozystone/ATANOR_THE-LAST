"""One-shot new native histories: frozen versus cumulative conditional learner."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import random
import sys
import tempfile
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.developmental_conditional_eval import Model
from scripts.developmental_continual_probe import score
from scripts.representation_r3_dev import configuration
from packages.action_core.world import Sandbox, Frame, Action


def run(source, output):
    raw = source.read_bytes()
    training = json.loads(raw)['records']
    frozen = Model(training)
    online = Model(training)
    records, curves = [], []
    totals = {k:Counter() for k in ('frozen','online')}
    costs = Counter()
    with tempfile.TemporaryDirectory(prefix='atanor_online_') as root:
        for episode, count in enumerate((5,6,5,6)):
            seed = 61001+episode
            rng = random.Random(seed)
            cfg,_,reference,payload = configuration(count,seed,payload=b'q'*(331+episode*307))
            body = Sandbox(Path(root)/str(episode),**cfg)
            episode_counts = {k:Counter() for k in totals}
            for step in range(24):
                before = body.observe()
                action = rng.choice(body.actions())
                predictions = {}
                for arm, model in (('frozen',frozen),('online',online)):
                    start = time.process_time()
                    predictions[arm] = model.predict(before,action,True)
                    costs[arm] += time.process_time()-start
                success = body.step(action)
                after = body.observe()
                for arm in totals:
                    measured = score(predictions[arm],after)
                    totals[arm].update(measured)
                    episode_counts[arm].update(measured)
                assert body._paths[reference].read_bytes()==payload
                records.append({'before':before.to_dict(),'action':action.to_dict(),
                    'after':after.to_dict(),'success':success,'episode':episode,'step':step,
                    'predictions':predictions})
                start = time.process_time()
                online = Model(training+records)
                costs['online_learning'] += time.process_time()-start
            curves.append(episode_counts)
    retention = {k:Counter() for k in totals}
    for record in training:
        before,after = (Frame.from_dict(record[k]) for k in ('before','after'))
        action = Action.from_dict(record['action'])
        for arm,model in (('frozen',frozen),('online',online)):
            retention[arm].update(score(model.predict(before,action,True),after))
    b,c = totals['frozen'],totals['online']
    adequate = b['wrong']>=4
    passed = (adequate and c['wrong']<=b['wrong']*.5 and c['unknown']<=b['unknown']
              and c['correct_singleton']>b['correct_singleton'] and retention['online']['wrong']==0
              and retention['online']['correct_singleton']>=retention['frozen']['correct_singleton'])
    result = {'verdict':'PREDICTIVE_LEARNING_PASS' if passed else
              'INSUFFICIENT_ERROR_OPPORTUNITIES' if not adequate else 'PREDICTIVE_LEARNING_FAIL',
              'scope':'same mechanics; random policy; no task/agency/economy claim',
              'source_sha256':hashlib.sha256(raw).hexdigest(),'totals':totals,'curves':curves,
              'cpu_seconds':costs,'retention':retention,'records':records}
    assert source.read_bytes()==raw
    with output.open('x') as stream:
        json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))


if __name__=='__main__':
    run(Path(sys.argv[1]),Path(sys.argv[2]))
