"""Independent raw score reconstruction; no learner evaluation or tuning."""
import hashlib
import json
from pathlib import Path
import statistics
import sys


def run(out):
    report=json.loads((out/'report.json').read_text())
    rows=[json.loads(s) for s in (out/'probes.jsonl').read_text().splitlines()]
    cases={r['id']:r['data'] for r in [json.loads(s) for s in (out/'cases.jsonl').read_text().splitlines()]}
    histories=[json.loads(s) for s in (out/'A_life.jsonl').read_text().splitlines()]
    events=[json.loads(s) for s in (out/'events.jsonl').read_text().splitlines()]
    assert len(rows)==3072 and len(cases)==1280 and len(events)==1024
    assert len(histories)==8 and all(len(h['events'])==1024 for h in histories)
    assert [h['seed'] for h in histories]==list(range(830200,830208))
    seen=set()
    for r in rows:
        key=tuple(r[k] for k in ('law','life','arm','count','probe'));assert key not in seen;seen.add(key)
        c=cases[r['case_id']];idx=c['primary'];p=r['predictions'];truth=c['new'][idx]['after']['kinds']
        pred=[max(range(3),key=lambda k:v[k]) for v in r['primary_probabilities']]
        assert pred==p[idx]
        changed=[i for i,(a,b) in enumerate(zip(c['old'][idx]['after']['kinds'],truth)) if a!=b]
        assert changed==c['changed'] and changed
        common=[i for i,(a,b) in enumerate(zip(c['old'],c['new'])) if a==b and a['after']['kinds']!=c['before']['kinds']]
        assert common==c['common'] and common
        assert r['changed_exact']==all(pred[i]==truth[i] for i in changed)
        assert r['whole_exact']==(pred==truth)
        assert r['common_count']==len(common)
        assert r['common_correct']==sum(p[i]==c['new'][i]['after']['kinds'] for i in common)
    for s in report['summaries']:
        q=[r for r in rows if (r['law'],r['arm'],r['count'])==(s['law'],s['arm'],s['count'])]
        assert len(q)==s['n']==32
        for key,field in [('whole','whole_exact'),('changed','changed_exact'),('common','common_correct'),('common_n','common_count')]:
            assert s[key]==sum(r[field] for r in q)
    def acquisition(law,arm,life=None):
        passing=[]
        for c in (0,1,2,4,8,16):
            q=[r for r in rows if (r['law'],r['arm'],r['count'])==(law,arm,c) and (life is None or r['life']==life)]
            passed=sum(r['whole_exact'] for r in q)>=.75*len(q) and all(sum(r['whole_exact'] for r in q if r['life']==i)>=.5*sum(r['life']==i for r in q) for i in {r['life'] for r in q})
            passing.append((c,passed))
        return next((c for i,(c,p) in enumerate(passing) if all(t[1] for t in passing[i:])),None)
    for law,arms in report['outcomes'].items():
        for arm,value in arms.items():assert acquisition(law,arm)==value
    metrics=report['metrics'];costs=metrics['costs'];laws=list(costs['fresh'])
    assert len(laws)==6 and 'null' not in laws and 'cascade' not in laws
    for arm in costs:
        for law,values in costs[arm].items():assert values==[acquisition(law,arm,i) for i in range(8)]
    capped=lambda v:17 if v is None else v
    flat={a:[capped(x) for law in laws for x in costs[a][law]] for a in costs}
    means={a:statistics.mean(v) for a,v in flat.items()};medians={a:statistics.median(v) for a,v in flat.items()}
    assert means==metrics['means'] and medians==metrics['medians']
    lawmeans={law:{a:statistics.mean(capped(x) for x in costs[a][law]) for a in costs} for law in laws}
    assert lawmeans==metrics['lawmeans']
    severe=lambda f,e:e>2*f and e-f>=4
    negatives=sum(severe(f,e) for f,e in zip(flat['fresh'],flat['weights_adam']))
    improved=sum(statistics.mean(capped(costs['weights_adam'][law][i]) for law in laws)<statistics.mean(capped(costs['fresh'][law][i]) for law in laws) for i in range(8))
    retention={law:{c:statistics.mean(r['common_correct']/r['common_count'] for r in rows if (r['law'],r['arm'],r['count'])==(law,'weights_adam',c)) for c in (0,16)} for law in laws}
    for law in laws:
        for c in (0,16):assert retention[law][c]==metrics['retention'][law][str(c)]
    before=statistics.mean(v[0] for v in retention.values());after=statistics.mean(v[16] for v in retention.values())
    gates=dict(mean_gain=means['weights_adam']<=.8*means['fresh'],median_gain=medians['weights_adam']<=.75*medians['fresh'],
        four_laws=sum(m['weights_adam']<m['fresh'] for m in lawmeans.values())>=4,six_histories=improved>=6,
        severe_pairs=negatives<=4,no_severe_law=not any(severe(m['fresh'],m['weights_adam']) for m in lawmeans.values()),
        retention_nonvacuous=before>=.8,retention_macro=after>=before-.05,retention_each=all(v[16]>=v[0]-.1 for v in retention.values()))
    assert gates==metrics['gates'] and negatives==metrics['severe_negative_pairs'] and improved==metrics['improved_histories']
    assert (report['verdict']=='BOUNDED_PANEL_PASS')==all(gates.values())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in report['hashes'].items())
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    with (out/'audit.json').open('x',encoding='utf-8') as f:json.dump(dict(status='RAW_AUDIT_PASS',gates=gates,means=means,medians=medians,retention_macro=dict(before=before,after=after),artifact_sha256=hashes),f,indent=2)
    print(json.dumps(dict(status='RAW_AUDIT_PASS',gates=gates,means=means,medians=medians,retention_macro=dict(before=before,after=after))))


if __name__=='__main__':run(Path(sys.argv[1]))
