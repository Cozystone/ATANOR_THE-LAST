"""Independent raw arithmetic and native reexecution after the one trial."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.hidden_regime_trial import body,frame,SEQUENCE,observation
from scripts.plasticity_law_suite import successors
from scripts.plastic_law_world import LawWorld,native
from scripts.adaptation_pair_isolation import digest


def run():
    out=ROOT/'evidence/latent-cause-sequential-v1'
    report=json.loads((out/'report.json').read_text())
    read=lambda name:list(map(json.loads,(out/name).read_text().splitlines()))
    rows=read('tasks.jsonl');ret=read('retention.jsonl');bank=read('bank.jsonl')
    unique={};scores={};usable={}
    for r in rows+ret:
        if 'regime_index' in r:
            visited=list(dict.fromkeys(SEQUENCE[:r['phase']+1]));law=visited[r['regime_index']]
        else:law=SEQUENCE[r['phase']]
        key=(law,r['seed']);unique[key]=r
        assert r['whole']==(r['predictions'][r['target']]==r['goal'])
        assert r['success']==(r['actual']['kinds']==r['goal'])
        assert r['actual']==r['catalog'][r['choice']]['after']
    for (law,seed),r in unique.items():
        b,_=body(law,seed,len(r['before']['kinds']))
        try:
            assert frame(b)==r['before'];assert successors(b,r['actions'])==r['catalog']
        finally:b.dispose()
    for arm in ('weights_adam','anchored','latent'):
        scores[arm]=[];usable[arm]={}
        for phase in range(6):
            best=None
            for count in (64,32,16,8,4,0):
                q=[r for r in rows if (r['arm'],r['phase'],r['count'])==(arm,phase,count)]
                assert len(q)==32
                valid=sum(r['whole'] for r in q)>=24 and sum(r['success'] for r in q)>=24
                valid=valid and all(sum(r['whole'] and r['success'] for r in q if r['life']==i)>=4 for i in range(4))
                if not valid:break
                best=count
            scores[arm].append(best)
            selected=[r for r in ret if (r['arm'],r['phase'])==(arm,phase)]
            usable[arm][str(phase)]=sum(sum(r['whole'] for r in selected if r['regime_index']==i)>=24 and sum(r['success'] for r in selected if r['regime_index']==i)>=24 for i in {r['regime_index'] for r in selected})
    assert scores==report['acquisition'];assert usable==report['usable_regimes']
    cap=lambda v:65 if v is None else v
    gates=dict(novel_acquired=all(scores['latent'][p] is not None for p in (0,1,2,4)),
        acquisition_noninferior=all(cap(scores['latent'][p])<=1.25*cap(scores['weights_adam'][p])+4 for p in (0,1,2,4)),
        return_within_four=all(scores['latent'][p] is not None and scores['latent'][p]<=4 for p in (3,5)),
        cumulative_three=usable['latent']['2']>=3,cumulative_four=usable['latent']['4']>=4 and usable['latent']['5']>=4,
        improvement_over_controls=usable['latent']['5']>max(usable[a]['5'] for a in ('weights_adam','anchored')),
        bounded_growth=not any(r['saturated'] for r in bank))
    assert gates==report['gates']
    warm=read('warm.jsonl');checked=0
    for life in range(4):
        b=LawWorld(941800+life,4,2,'restrict')
        try:
            for e in [r for r in warm if r['life']==life]:
                assert frame(b)==e['before']
                assert bool(b.do(native.FK_ACTIONS[e['action'][0]],e['action'][1]))==e['accepted']
                assert frame(b)==e['after'];checked+=1
        finally:b.dispose()
    events=read('events.jsonl')
    for e in events:
        count=e['ordinal']-1
        native_event=observation(SEQUENCE[e['phase']],9500000+e['life']*100000+e['phase']*1000+count,count)
        assert all(e[k]==v for k,v in native_event.items())
    calibrations={}
    for r in ret:
        key=(r['life'],r['phase'],r['regime_index'])
        calibrations[key]=r['calibration']
    for (life,phase,si),es in calibrations.items():
        law=list(dict.fromkeys(SEQUENCE[:phase+1]))[si]
        for j,e in enumerate(es):assert e==observation(law,9800000+life*100000+phase*1000+si*20+j,j)
    assert all(digest(Path(p))==h for p,h in report['hashes'].items())
    result=dict(status='RAW_NATIVE_AUDIT_PASS',tasks=len(rows),retention=len(ret),native_catalogs=len(unique),
                warm_transitions=checked,sequential_events=len(events),calibration_events=4*len(calibrations),acquisition=scores,usable=usable,gates=gates,
                files={p.name:digest(p) for p in out.iterdir() if p.is_file()})
    with (out/'audit.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='files'}))

if __name__=='__main__':run()
