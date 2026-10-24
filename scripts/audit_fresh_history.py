"""Independent raw aggregation of frozen fresh-history validation."""
import hashlib
import json
from pathlib import Path
import sys


def run(out):
    report=json.loads((out/'report.json').read_text());selected=report['selected']
    rows=[json.loads(s) for s in (out/'probes.jsonl').read_text().splitlines()]
    life=[json.loads(s) for s in (out/'A_life.jsonl').read_text().splitlines()]
    events=[json.loads(s) for s in (out/'events.jsonl').read_text().splitlines()]
    assert len(rows)==960 and len(life)==8 and len(events)==128
    assert [x['seed'] for x in life]==list(range(810100,810108))
    assert all(len(x['events'])==1024 for x in life)
    assert report['native_A_verified']==8192
    seen=set()
    for r in rows:
        key=tuple(r[k] for k in ('law','life','arm','count','probe'));assert key not in seen;seen.add(key)
        w=r['witness'];a=w['old_after']['kinds'];b=w['after']['kinds']
        changed=[i for i in range(len(a)) if a[i]!=b[i]];assert changed==w['changed']
        pred=[max(range(3),key=lambda k:p[k]) for p in r['probabilities']]
        assert pred==r['prediction'] and (pred==b)==r['whole_exact']
        assert all(pred[i]==b[i] for i in changed)==r['changed_exact']
    for s in report['summaries']:
        q=[r for r in rows if (r['law'],r['arm'],r['count'])==(s['law'],s['arm'],s['count'])]
        assert len(q)==32
        assert sum(r['changed_exact'] for r in q)==s['changed_correct']
        assert sum(r['whole_exact'] for r in q)==s['whole_correct']
    def acquisition(law,arm,life=None):
        result=None
        for count in (8,4,2,1,0):
            q=[r for r in rows if (r['law'],r['arm'],r['count'])==(law,arm,count) and (life is None or r['life']==life)]
            if sum(r['changed_exact'] for r in q)<.75*len(q):break
            if any(sum(r['changed_exact'] for r in q if r['life']==i)<.5*sum(r['life']==i for r in q) for i in {r['life'] for r in q}):break
            result=count
        return result
    for law,arms in report['outcomes'].items():
        for arm,v in arms.items():
            assert acquisition(law,arm)==v['acquisition']
            assert [acquisition(law,arm,i) for i in range(8)]==v['per_life']
    sel=acquisition('null',selected);fresh=acquisition('null','fresh')
    pairs=[(acquisition('null',selected,i),acquisition('null','fresh',i)) for i in range(8)]
    cascade=[acquisition('cascade',a) for a in (selected,'fresh','full')]
    whole=lambda law,arm:sum(r['whole_exact'] for r in rows if (r['law'],r['arm'],r['count'])==(law,arm,8))
    gates=dict(null_fast=sel is not None and sel<=4,fresh_not_before8=fresh is None or fresh>=8,
               six_of_eight=sum(a is not None and (b is None or a<b) for a,b in pairs)>=6,
               no_life_slower=all(b is None or (a is not None and a<=b) for a,b in pairs),
               cascade_noninferior=all(x is not None for x in cascade) and cascade[0]<=min(cascade[1:]),
               whole_noninferior=all(whole(law,selected)>=whole(law,'fresh') for law in ('null','cascade')))
    assert gates==report['gates']
    assert (report['verdict']=='FRESH_HISTORY_VALIDATION_PASS')==all(gates.values())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in report['hashes'].items())
    artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    with (out/'audit.json').open('x',encoding='utf-8') as f:json.dump(dict(status='RAW_AUDIT_PASS',gates=gates,outcomes=report['outcomes'],artifact_sha256=artifacts),f,indent=2)
    print(json.dumps(dict(status='RAW_AUDIT_PASS',gates=gates,outcomes=report['outcomes'])))


if __name__=='__main__':run(Path(sys.argv[1]))
