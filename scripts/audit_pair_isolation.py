"""Independent raw scoring, no learner execution."""
import hashlib
import json
from pathlib import Path
import sys


def run(out):
    r=json.loads((out/'report.json').read_text())
    rows=[json.loads(s) for s in (out/'probes.jsonl').read_text().splitlines()]
    old=[json.loads(s) for s in (out.parent/'developmental-counterexample-v1/probes.jsonl').read_text().splitlines()]
    lookup={tuple(x[k] for k in ('law','life','arm','count','probe')):x for x in old}
    assert len(rows)==640 and r['shared_counterexamples']==64
    seen=set();controls=0
    for x in rows:
        key=tuple(x[k] for k in ('law','life','arm','count','probe'));assert key not in seen;seen.add(key)
        w=x['witness'];y=w['after']['kinds'];a=w['old_after']['kinds']
        mask=[i for i in range(len(y)) if y[i]!=a[i]];assert mask==w['changed']
        p=[max(range(3),key=lambda j:values[j]) for values in x['probabilities']]
        assert p==x['prediction'] and (p==y)==x['whole_exact']
        assert all(p[i]==y[i] for i in mask)==x['changed_exact']
        if x['arm'] in ('fresh','full'):
            prior=lookup[(x['law'],x['life'],'experienced' if x['arm']=='full' else 'fresh',x['count'],x['probe'])]
            assert x['probabilities']==prior['probabilities'] and w==prior['witness'];controls+=1
    for s in r['summaries']:
        q=[x for x in rows if (x['law'],x['arm'],x['count'])==(s['law'],s['arm'],s['count'])]
        assert len(q)==16
        assert sum(x['changed_exact'] for x in q)==s['changed_correct']
        assert sum(x['whole_exact'] for x in q)==s['whole_correct']
    def threshold(law,arm,life=None):
        found=None
        for c in (8,4,2,1,0):
            q=[x for x in rows if x['law']==law and x['arm']==arm and x['count']==c and (life is None or x['life']==life)]
            if sum(x['changed_exact'] for x in q)<.75*len(q):break
            if any(sum(x['changed_exact'] for x in q if x['life']==i)<.5*sum(x['life']==i for x in q) for i in {x['life'] for x in q}):break
            found=c
        return found
    for law,arms in r['outcomes'].items():
        for arm,v in arms.items():
            assert threshold(law,arm)==v['acquisition']
            assert [threshold(law,arm,i) for i in range(4)]==v['per_life']
    assert controls==320==r['control_probability_matches']
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in r['hashes'].items())
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    with (out/'audit.json').open('x',encoding='utf-8') as f:
        json.dump(dict(status='RAW_AUDIT_PASS',probability_controls=controls,outcomes=r['outcomes'],artifact_sha256=hashes),f,indent=2)
    print(json.dumps(dict(status='RAW_AUDIT_PASS',outcomes=r['outcomes'])))


if __name__=='__main__':run(Path(sys.argv[1]))
