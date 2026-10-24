"""Independent readout from sealed raw events, not an additional candidate run."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys


def run(out):
    read=lambda name:[json.loads(line) for line in (out/name).read_text().splitlines()]
    tasks=read('tasks.jsonl');probes=read('probes.jsonl');lives=read('life.jsonl')
    report=json.loads((out/'report.json').read_text())
    assert len(tasks)==320 and len(probes)==320 and len(lives)==16
    groups=defaultdict(list);seen=set();actions=0
    for row in tasks:
        key=tuple(row[k] for k in ('law','life','age','arm','task'))
        assert key not in seen;seen.add(key)
        events=row['events'];assert len(events)==row['actions']<=32
        # Zero-action goals are possible, verify from matching native-independent probe initial A truth.
        initial=next(p['old_truth'] for p in probes if tuple(p[k] for k in ('law','life','age','arm','task'))==key)
        for e in events:
            assert e['before']['kinds']==initial
            initial=e['after']['kinds']
        success=initial==row['goal'];assert success==row['success']
        assert row['cost']==(len(events) if success else 33)
        groups[(row['law'],row['arm'],row['age'])].append(row)
        actions+=len(events)
    for row in lives:
        other=next(x for x in lives if x['law']==row['law'] and x['life']==row['life'] and x['arm']!=row['arm'])
        assert row['events']==other['events'] and len(row['events'])==512
    assert actions+8192==report['native_verified']
    for s in report['summaries']:
        key=s['law'],s['arm'],s['age'];rows=groups[key];assert len(rows)==16
        assert sum(r['success'] for r in rows)==s['success']
        assert sum(r['cost'] for r in rows)/16==s['mean_cost']
        changed=[r for r in rows if r['task']<2];assert len(changed)==8
        assert sum(r['success'] for r in changed)==s['changed_success']
        assert sum(r['cost'] for r in changed)/8==s['changed_mean_cost']
        p=[p for p in probes if (p['law'],p['arm'],p['age'])==key]
        for x in p:
            assert x['new_correct']==(x['prediction']==x['new_truth'])
            assert x['old_correct']==(x['prediction']==x['old_truth'])
        assert sum(x['new_correct'] for x in p)/16==s['changed_probe_accuracy']
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in report['hashes'].items())
    acquisition={}
    for law in ('null','cascade'):
        acquisition[law]={}
        for arm in ('fresh','experienced'):
            hits=[s['age'] for s in report['summaries'] if s['law']==law and s['arm']==arm and s['changed_probe_accuracy']>=.75]
            acquisition[law][arm]=min(hits) if hits else 513
    assert acquisition==report['acquisition']
    # Verify reported overall conjunction; no post-result threshold changes.
    passed=all(all(x.values()) for x in report['gates'].values()) and report['source_unchanged']
    assert (report['verdict']=='BOUNDED_LAW_ADAPTATION_POSITIVE')==passed
    totals={}
    for law in ('null','cascade'):
        totals[law]={}
        for arm in ('fresh','experienced'):
            rows=[r for r in tasks if r['law']==law and r['arm']==arm]
            changed=[r for r in rows if r['cohort']=='changed']
            totals[law][arm]=dict(mean_cost=sum(r['cost'] for r in rows)/len(rows),
                changed_cost=sum(r['cost'] for r in changed)/len(changed),
                task_cpu_seconds=sum(r['cpu_seconds'] for r in rows),
                paired_changed=[sum(r['cost'] for r in changed if r['life']==i)/10 for i in range(4)])
        baseline=totals[law]['fresh']; experienced=totals[law]['experienced']
        before=[p for p in probes if p['law']==law and p['arm']=='experienced' and p['age']==0]
        expected=dict(
            old_answer_conflict=sum(p['old_correct'] for p in before)>=12 and sum(p['new_correct'] for p in before)<=4,
            changed_cost_gain=experienced['changed_cost']<=.8*baseline['changed_cost'],
            total_cost_gain=experienced['mean_cost']<=.8*baseline['mean_cost'],
            faster_new_law=acquisition[law]['experienced']<acquisition[law]['fresh'] and acquisition[law]['experienced']<=128,
            final_success_noninferior=sum(r['success'] for r in groups[(law,'experienced',512)])>=sum(r['success'] for r in groups[(law,'fresh',512)]),
            paired_lives=sum(a<b for a,b in zip(experienced['paired_changed'],baseline['paired_changed']))>=3
                and all(a<=1.1*b for a,b in zip(experienced['paired_changed'],baseline['paired_changed'])))
        assert expected==report['gates'][law]
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}
    with (out/'audit.json').open('x',encoding='utf-8') as f:
        json.dump(dict(raw_count_audit='PASS',tasks=len(tasks),training_actions=8192,
                       native_verified=report['native_verified'],totals=totals,artifact_sha256=hashes),f,indent=2)
    print(json.dumps(dict(raw_count_audit='PASS',totals=totals)))


if __name__=='__main__':run(Path(sys.argv[1]))
