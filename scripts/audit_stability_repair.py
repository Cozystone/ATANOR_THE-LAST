"""Post-run raw-count audit, not another experiment or changed criterion."""
import json
import statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'evidence/stability-repair-v1'
source=ROOT/'evidence/developmental-plasticity-panel-v1'
rows=[json.loads(s) for s in (out/'probes.jsonl').read_text().splitlines()]
cases={r['id']:r['data'] for r in map(json.loads,(source/'cases.jsonl').read_text().splitlines())}
report=json.loads((out/'report.json').read_text())
assert len(rows)==1152
paired=dict(kept=0,lost=0,gained=0,never=0)
index={(r['law'],r['life'],r['probe'],r['count']):r for r in rows}
assert len(index)==len(rows)
costs=[];ret={}
for law in sorted({r['law'] for r in rows}):
    for life in range(8):
        cost=17
        for count in (16,8,4,2,1,0):
            if sum(index[law,life,q,count]['whole_exact'] for q in range(4))<3:break
            cost=count
        costs.append(cost)
    ret[law]={}
    for count in (0,16):
        selected=[r for r in rows if r['law']==law and r['count']==count]
        ret[law][count]=statistics.mean(r['common_correct']/r['common_count'] for r in selected)
for row in rows:
    c=cases[row['case_id']];p=row['predictions'];truth=c['new']
    assert row['whole_exact']==(p[c['primary']]==truth[c['primary']]['after']['kinds'])
    assert row['common_correct']==sum(p[i]==truth[i]['after']['kinds'] for i in c['common'])
    assert row['common_count']==len(c['common'])
    if row['count']==16:
        old=index[row['law'],row['life'],row['probe'],0]['predictions']
        for i in c['common']:
            a=old[i]==truth[i]['after']['kinds'];b=p[i]==truth[i]['after']['kinds']
            paired['kept' if a and b else 'lost' if a else 'gained' if b else 'never']+=1
mean=statistics.mean(costs)
assert mean==report['original_panel_gates']['means']['weights_adam']
before=statistics.mean(v[0] for v in ret.values());after=statistics.mean(v[16] for v in ret.values())
assert abs(before-report['retention_before'])<1e-12
assert abs(after-report['retention_after'])<1e-12
assert report['repair_gates']['cost_at_most_six']==(mean<=6)
assert report['repair_gates']['macro_preserved']==(after>=before-.02)
assert report['repair_gates']['each_preserved']==all(v[16]>=v[0]-.05 for v in ret.values())
result=dict(status='RAW_COUNT_AUDIT_PASS',rows=len(rows),cost_mean=mean,
            paired_retention=paired,before=before,after=after)
with (out/'audit.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(result))
