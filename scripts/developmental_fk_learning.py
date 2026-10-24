"""Native SQL feasibility; no transferred rules or task capability claim."""
import hashlib, importlib.util, json, random, sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from packages.shared_world.conditional_support import fit

def observe(body):
    states=list(body.config()); edges=[[0]*body.n for _ in states]
    for k,ref in body.con.execute('SELECT k, ref FROM row_ ORDER BY k'):
        if ref is not None: edges[k][ref]=1
    return states,edges

def features(states,edges,target,categories):
    values=[]
    for category in categories:
        mask=[int(s==category) for s in states]
        values.extend((sum(mask),sum(edges[target][j]*mask[j] for j in range(len(states))),
                       sum(edges[j][target]*mask[j] for j in range(len(states)))))
    return tuple(values)

def run(source,output):
    raw=source.read_bytes()
    spec=importlib.util.spec_from_file_location('fk_native',source)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    training=[]; models={}; totals={arm:Counter() for arm in ('local','relational')}; records=[]
    for phase,n,seed,prefill in [('train',4,82001,2),('test',7,83001,3)]:
        body=module.FKWorld(seed,n=n,prefill=prefill); rng=random.Random(seed)
        try:
            for step in range(192):
                states,edges=observe(body)
                action=rng.choice(body.actions); target=rng.randrange(body.n)
                predictions={}
                if phase=='test':
                    model=models.get((action,states[target]))
                    predictions={'local':sorted(model.common) if model else [],
                        'relational':sorted(model.query(features(states,edges,target,categories))) if model else []}
                ok=body.do(action,target); after,_=observe(body)
                row={'states':states,'edges':edges,'action':action,'target':target,'after':after,'success':ok}
                if phase=='train': training.append(row)
                else:
                    for arm,values in predictions.items():
                        totals[arm]['unknown' if not values else 'wrong' if after[target] not in values
                                    else 'singleton' if len(values)==1 else 'set']+=1
                    records.append({**row,'predictions':predictions})
        finally: body.dispose()
        if phase=='train':
            categories=sorted({s for row in training for s in row['states']}); examples={}
            for row in training:
                t=row['target']; key=(row['action'],row['states'][t])
                examples.setdefault(key,[]).append((features(row['states'],row['edges'],t,categories),{row['after'][t]}))
            models={key:fit(rows) for key,rows in examples.items()}
    passed=totals['relational']['wrong']==0 and totals['relational']['singleton']>=totals['local']['singleton']+20
    result={'verdict':'LOCAL_PREDICTION_PASS' if passed else 'LOCAL_PREDICTION_FAIL',
        'scope':'SQL target-state prediction, not full-world/task/transfer',
        'source_sha256':hashlib.sha256(raw).hexdigest(),'categories':categories,'totals':totals,
        'training':training,'records':records,'rules':[{'key':k,'common':sorted(m.common),
        'alternatives':[[i,op,t,sorted(y),sorted(n)] for i,op,t,y,n in m.alternatives]} for k,m in models.items()]}
    assert source.read_bytes()==raw
    with output.open('x') as stream: json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({k:v for k,v in result.items() if k not in ('training','records','rules')}))

if __name__=='__main__': run(Path(sys.argv[1]),Path(sys.argv[2]))
