"""Exposed-data feasibility, NOT fresh capability or a deployed self-model.

Source:12 paired procedure-v1 native tasks. Leave one BODY SIZE out (4/5/6),
never split paired arms. Generic predecision numeric state/goal summaries only;
no seed/ordinal/action names/outcome features. Range-normalized nearest neighbor,
average exact distance ties; predict native actions then model calls lexically.
No hyperparameter search. Compare both fixed strategies and cyclically shuffled
training outcome pairs. GO only no extra actions vs primitive AND >=20% fewer
queries than primitive AND better(actions,queries) than fixed learned/shuffle.
Source cohort already exposed to engineer; results diagnostic only. Historical
paired acquisition CPU/actions reported, not free self-knowledge. No rerun/tuning.
"""
import json,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def features(row):
    f=row['trace'][0]['before'];handles=f['handles'];sizes=f['sizes']
    required=row['goal']['sizes'];n=len(handles)
    changed=[h for h,v in required if abs(sizes[handles.index(h)]-v)>1e-12]
    values=[n,len(required)/n,len(changed)/n,row['budget'],min(sizes),max(sizes),sum(sizes)/n]
    for matrix in [f['equal'],f['parent']]+[v for _,v in sorted(f['relations'].items())]:
        values.append(sum(sum(r) for r in matrix)/(n*n))
    return values


def choose(training,query,shuffle=False):
    low=[min(x[j] for x,y in training) for j in range(len(query))]
    spans=[max(x[j] for x,y in training)-low[j] or 1 for j in range(len(query))]
    labels=[y for x,y in training]
    if shuffle:labels=labels[1:]+labels[:1]
    distances=[sum(((v-q)/s)**2 for v,q,s in zip(x,query,spans)) for x,y in training]
    nearest=[i for i,d in enumerate(distances) if abs(d-min(distances))<1e-12]
    costs={arm:tuple(sum(labels[i][arm][k] for i in nearest)/len(nearest) for k in range(2)) for arm in ('primitive','learned')}
    return min(costs,key=lambda arm:costs[arm]),costs


def run(output):
    if output.exists():raise FileExistsError(output)
    path=ROOT/'evidence/developmental-procedure-v1/report.json';raw=path.read_bytes();source=json.loads(raw)
    pairs=[]
    for ordinal in range(12):
        arms={r['arm']:r for r in source['rows'] if r['ordinal']==ordinal and r['arm']!='reversed'}
        assert features(arms['primitive'])==features(arms['learned'])
        pairs.append((features(arms['primitive']),{a:(len(r['trace']),r['queries']) for a,r in arms.items()}))
    started=time.process_time();rows=[]
    for ordinal,(x,y) in enumerate(pairs):
        training=[(a,b) for a,b in pairs if a[0]!=x[0]]
        real,predicted=choose(training,x);sham,_=choose(training,x,True)
        rows.append(dict(ordinal=ordinal,group=x[0],features=x,choice=real,predicted=predicted,shuffled_choice=sham,
            actual=y,chosen=y[real],shuffled=y[sham]))
    summary={}
    for arm in ('primitive','learned','chosen','shuffled'):
        costs=[r['actual'][arm] if arm in ('primitive','learned') else r[arm] for r in rows]
        summary[arm]=dict(actions=sum(c[0] for c in costs),queries=sum(c[1] for c in costs))
    a,b=summary['chosen'],summary['primitive'];cost=lambda s:(s['actions'],s['queries'])
    passed=a['actions']<=b['actions'] and a['queries']<=.8*b['queries'] and all(cost(a)<cost(summary[c]) for c in ('learned','shuffled'))
    result=dict(verdict='EXPOSED_SELF_COST_SIGNAL' if passed else 'NO_EXPOSED_SELF_COST_SIGNAL',summary=summary,rows=rows,
        analysis_cpu=time.process_time()-started,source_sha256=hashlib.sha256(raw).hexdigest(),
        historical_acquisition={a:source['summary'][a] for a in ('primitive','learned','reversed')},
        scope='group-held-out existing exposed data; not native policy deployment, autonomy or capability')
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,separators=(',',':'))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':run(Path(sys.argv[1]))
