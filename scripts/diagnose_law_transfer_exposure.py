"""Post-hoc raw exposure accounting only; never additional learner execution."""
import json
from pathlib import Path
import sys


def run(out):
    lives=[json.loads(s) for s in (out/'life.jsonl').read_text().splitlines()]
    rows=[]
    for life in lives:
        if life['arm']!='experienced':continue
        def changed(e):
            return e['action']==[3,0] and e['before']['kinds'][0]==1 and 2 in e['before']['kinds'] and e['accepted']
        rows.append(dict(law=life['law'],life=life['life'],
                         first_changed_event=next((i+1 for i,e in enumerate(life['events']) if changed(e)),None),
                         counts={a:sum(changed(e) for e in life['events'][:a]) for a in (8,32,128,512)}))
    tasks=[json.loads(s) for s in (out/'tasks.jsonl').read_text().splitlines()]
    examples=[dict(law=r['law'],goal=r['goal'],events=[dict(action=e['action'],before=e['before']['kinds'],after=e['after']['kinds']) for e in r['events']])
              for r in tasks if r['arm']=='experienced' and r['age']==0 and r['life']==0 and r['task']==0]
    result=dict(status='POST_HOC_DIAGNOSTIC_NOT_NEW_GATE',exposures=rows,examples=examples,
                interpretation='Random B experience supplies only0..2 direct law contradictions by128; both arms see identical events. Does not isolate stale replay, optimizer inertia or architecture.')
    with (out/'exposure_diagnosis.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))


if __name__=='__main__':run(Path(sys.argv[1]))
