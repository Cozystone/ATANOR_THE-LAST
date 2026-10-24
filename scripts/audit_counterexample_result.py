"""Raw-only independent scoring of counterexample diagnostic; no model rerun."""
import hashlib
import json
from pathlib import Path
import sys


def run(out):
    rows=[json.loads(s) for s in (out/'probes.jsonl').read_text().splitlines()]
    events=[json.loads(s) for s in (out/'events.jsonl').read_text().splitlines()]
    report=json.loads((out/'report.json').read_text())
    assert len(rows)==320 and len(events)==64
    seen=set()
    for r in rows:
        key=tuple(r[k] for k in ('law','life','arm','count','probe'))
        assert key not in seen;seen.add(key)
        w=r['witness'];old=w['old_after']['kinds'];new=w['after']['kinds']
        changed=[i for i in range(len(old)) if old[i]!=new[i]]
        assert changed==w['changed'] and changed
        pred=[max(range(3),key=lambda k:p[k]) for p in r['probabilities']]
        assert pred==r['prediction']
        assert r['changed_exact']==all(pred[i]==new[i] for i in changed)
        assert r['whole_exact']==(pred==new) and r['old_exact']==(pred==old)
    for s in report['summaries']:
        q=[r for r in rows if (r['law'],r['arm'],r['count'])==(s['law'],s['arm'],s['count'])]
        assert len(q)==16
        for source,target in [('changed_exact','changed_correct'),('whole_exact','whole_correct'),('old_exact','old_correct')]:
            assert sum(r[source] for r in q)==s[target]
    ages=[0,1,2,4,8]
    def threshold(law,arm,life=None):
        passed=[]
        for age in ages:
            q=[r for r in rows if r['law']==law and r['arm']==arm and r['count']==age and (life is None or r['life']==life)]
            enough=sum(r['changed_exact'] for r in q)>=3*len(q)/4
            each=all(sum(r['changed_exact'] for r in q if r['life']==i)>=sum(r['life']==i for r in q)/2 for i in {r['life'] for r in q})
            passed.append(enough and each)
        # Earliest suffix of all passes, independently computed in reverse.
        last=None
        for index in reversed(range(len(ages))):
            if not passed[index]:break
            last=ages[index]
        return last
    for law,o in report['outcomes'].items():
        for arm in ('fresh','experienced'):
            assert threshold(law,arm)==o['acquisition'][arm]
            for i in range(4):assert threshold(law,arm,i)==o['per_life'][i][arm]
    for law in ('null','cascade'):
        for life in range(4):
            q=[e for e in events if e['law']==law and e['life']==life]
            assert [e['ordinal'] for e in q]==list(range(1,9))
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in report['hashes'].items())
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    with (out/'audit.json').open('x',encoding='utf-8') as f:
        json.dump(dict(status='RAW_AUDIT_PASS',probe_rows=320,shared_actual_counterexamples=64,
                       outcomes=report['outcomes'],artifact_sha256=hashes),f,indent=2)
    print(json.dumps(dict(status='RAW_AUDIT_PASS',outcomes=report['outcomes'])))


if __name__=='__main__':run(Path(sys.argv[1]))
