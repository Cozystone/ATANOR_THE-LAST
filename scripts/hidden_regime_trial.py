"""One untouched-instance sequential native trial, sealed before execution.

Environment identities exist only here. Bodies/evidence are deliberately supplied;
this is not autonomous exploration nor an unseen-law-family evaluation.
"""
import copy
import json
import random
import time
from pathlib import Path
import sys
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.plastic_law_world import LawWorld,native,SOURCE
from scripts.plasticity_law_suite import SQL,successors
from scripts.developmental_plastic_eval import frame
from scripts.developmental_plastic_world import PlasticWorld
from scripts.stable_plastic_world import StablePlasticWorld
from scripts.latent_cause_world import LatentCauseWorld
from scripts.adaptation_pair_isolation import compose,digest

SEQUENCE=('null','cascade','steal_link','null','attached_insert','cascade')
COUNTS=(0,4,8,16,32,64)
ARMS=('weights_adam','anchored','latent')


def body(regime,seed,n):
    b=LawWorld(seed,n,0,regime if regime in ('null','cascade') else 'restrict')
    ids=list(range(1,n));random.Random(seed).shuffle(ids)
    free,linked,missing=ids[:3]
    b.con.execute('INSERT INTO anchor VALUES(0)')
    b.con.executemany('INSERT INTO row_ VALUES (?,NULL)',[(i,) for i in ids if i!=missing])
    for i in [linked]+ids[3::2]:b.con.execute('UPDATE row_ SET ref=0 WHERE k=?',(i,))
    b.con.commit()
    if regime in SQL:b.con.execute(SQL[regime]);b.con.commit()
    return b,[[3,0],[1,free],[0,missing],[2,linked]]


def observation(regime,seed,slot):
    b,actions=body(regime,seed,4)
    try:
        before=frame(b);action=actions[slot%4]
        accepted=bool(b.do(native.FK_ACTIONS[action[0]],action[1]))
        return dict(before=before,action=action,after=frame(b),accepted=accepted)
    finally:b.dispose()


def teach(model,e):
    model.enter_body(len(e['before']['kinds']))
    model.learn(e['before'],e['action'],e['after'])


def tasks(model,regime,seed):
    results=[]
    for q in range(8):
        b,primary=body(regime,seed+q,5+q%2)
        try:
            before=frame(b);actions=[[o,i] for o in range(4) for i in range(b.n)]
            catalog=successors(b,actions);target=actions.index(primary[q%4])
            goal=catalog[target]['after']['kinds']
            # Nontrivial reachable goal only; deterministic environment fallback.
            if goal==before['kinds']:
                target=next(i for i,r in enumerate(catalog) if r['after']['kinds']!=before['kinds'])
                goal=catalog[target]['after']['kinds']
            probe=copy.deepcopy(model);probe.enter_body(b.n)
            probs=probe.forecasts(before,actions)[0]
            goal_tensor=torch.tensor(goal)[None,:,None].expand(len(actions),-1,-1)
            scores=probs.clamp_min(1e-9).log().gather(2,goal_tensor).squeeze(-1).mean(1)
            choice=int(scores.argmax());action=actions[choice]
            accepted=bool(b.do(native.FK_ACTIONS[action[0]],action[1]));actual=frame(b)
            assert actual==catalog[choice]['after'] and accepted==catalog[choice]['accepted']
            pred=probs.argmax(-1).tolist()
            results.append(dict(probe=q,seed=seed+q,before=before,actions=actions,goal=goal,
                                target=target,predictions=pred,choice=choice,actual=actual,
                                whole=pred[target]==goal,success=actual['kinds']==goal,
                                catalog=catalog))
        finally:b.dispose()
    return results


def acquisition(rows,arm,phase):
    result=None
    for c in reversed(COUNTS):
        selected=[r for r in rows if (r['arm'],r['phase'],r['count'])==(arm,phase,c)]
        if any(sum(r[k] for r in selected)<.75*len(selected) for k in ('whole','success')):break
        if any(sum(r['whole'] and r['success'] for r in selected if r['life']==life)<4 for life in range(4)):break
        result=c
    return result


def run(out):
    out.mkdir(exist_ok=False);start=time.monotonic()
    paths=[Path(__file__),SOURCE]+[ROOT/'scripts'/name for name in ('latent_cause_world.py','stable_plastic_world.py','developmental_plastic_world.py','plasticity_law_suite.py','plastic_law_world.py','adaptation_pair_isolation.py','developmental_plastic_eval.py')]
    paths += [ROOT/'docs/ATANOR_LATENT_CAUSE_V1_PREREGISTRATION.md']
    hashes={str(p):digest(p) for p in paths}
    (out/'attempt.json').write_text(json.dumps(hashes,indent=2))
    rows=[];retention=[];bank=[];reloads=0
    def write(name,row):
        with (out/name).open('a') as f:f.write(json.dumps(row)+'\n')
    def cap():
        if time.monotonic()-start>1800:raise TimeoutError('30min one trial cap')
    for life in range(4):
        cap();seed=941800+life;warm=PlasticWorld(seed);warm.enter_body(4)
        a=LawWorld(seed,4,2,'restrict');rng=random.Random(seed+100)
        try:
            for step in range(1024):
                before=frame(a);action=[rng.randrange(4),rng.randrange(4)]
                accepted=bool(a.do(native.FK_ACTIONS[action[0]],action[1]));after=frame(a)
                warm.learn(before,action,after)
                write('warm.jsonl',dict(life=life,step=step,before=before,action=action,after=after,accepted=accepted))
        finally:a.dispose()
        state=warm.checkpoint();torch.save(state,out/f'warm-{life}.pt')
        models=dict(weights_adam=PlasticWorld.restore(compose(state)['weights_adam']),
                    anchored=StablePlasticWorld.from_life(state),latent=LatentCauseWorld(state))
        seen=[]
        for phase,regime in enumerate(SEQUENCE):
            if regime not in seen:seen.append(regime)
            for count in range(65):
                cap()
                if count in COUNTS:
                    for arm,m in models.items():
                        for r in tasks(m,regime,9600000+life*100000+phase*1000):
                            row=dict(r,life=life,phase=phase,arm=arm,count=count)
                            rows.append(row);write('tasks.jsonl',row)
                if count==64:break
                e=observation(regime,9500000+life*100000+phase*1000+count,count)
                write('events.jsonl',dict(e,life=life,phase=phase,ordinal=count+1))
                for m in models.values():teach(m,e)
            # Recoverable bank evaluated on counterfactual branches: four actual
            # calibration events, no identity signal, never merged into main life.
            for si,oldregime in enumerate(seen):
                es=[observation(oldregime,9800000+life*100000+phase*1000+si*20+j,j) for j in range(4)]
                for arm,m in models.items():
                    clone=copy.deepcopy(m)
                    for e in es:teach(clone,e)
                    for r in tasks(clone,oldregime,9900000+life*100000+phase*1000+si*20):
                        row=dict(r,life=life,phase=phase,arm=arm,regime_index=si,calibration=es)
                        retention.append(row);write('retention.jsonl',row)
            latent=models['latent'];cp=latent.checkpoint();path=out/f'latent-{life}-{phase}.pt';torch.save(cp,path)
            restored=LatentCauseWorld.restore(torch.load(path,weights_only=True))
            e=observation(regime,9950000+life*10000+phase,0)
            for obj in (restored,copy.deepcopy(latent)):
                teach(obj,e);obj.enter_body(4)
                p=obj.forecasts(e['before'],[e['action']])[0]
                if obj is restored:expected=p
                else:assert torch.equal(expected,p);reloads+=1
            info=dict(life=life,phase=phase,archive=len(latent.archive),recruits=latent.recruits,
                      candidate=latent.candidate is not None,saturated=latent.saturated,
                      belief=latent.belief,
                      parameters=sum(p.numel() for m in latent.models() for net in m.models for p in net.parameters()))
            bank.append(info);write('bank.jsonl',info)
            print(json.dumps(dict(life=life,phase=phase,seconds=time.monotonic()-start,archive=info['archive'])),flush=True)
    acq={arm:[acquisition(rows,arm,p) for p in range(6)] for arm in ARMS}
    usable={}
    for arm in ARMS:
        usable[arm]={}
        for phase in range(6):
            selected=[r for r in retention if r['arm']==arm and r['phase']==phase]
            indices=sorted({r['regime_index'] for r in selected})
            usable[arm][phase]=sum(all(sum(r[k] for r in selected if r['regime_index']==i)>=.75*sum(r['regime_index']==i for r in selected) for k in ('whole','success')) for i in indices)
    score=lambda x:65 if x is None else x
    novel=(0,1,2,4)
    gates=dict(novel_acquired=all(acq['latent'][p] is not None for p in novel),
               acquisition_noninferior=all(score(acq['latent'][p])<=1.25*score(acq['weights_adam'][p])+4 for p in novel),
               return_within_four=all(acq['latent'][p] is not None and acq['latent'][p]<=4 for p in (3,5)),
               cumulative_three=usable['latent'][2]>=3,cumulative_four=usable['latent'][4]>=4 and usable['latent'][5]>=4,
               improvement_over_controls=usable['latent'][5]>max(usable[a][5] for a in ('weights_adam','anchored')),
               bounded_growth=not any(r['saturated'] for r in bank))
    assert all(digest(Path(p))==h for p,h in hashes.items())
    report=dict(verdict='LATENT_CAUSE_BOUNDED_PASS' if all(gates.values()) else 'LATENT_CAUSE_NO_GO',
                gates=gates,acquisition=acq,usable_regimes=usable,task_rows=len(rows),retention_rows=len(retention),
                reload_after_learning_equal=reloads,seconds=time.monotonic()-start,hashes=hashes,
                scope='New instances and four new warm histories; known SQL law family; supplied balanced experience; one-step native control, not general planning or autonomous exploration')
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='hashes'}),flush=True)

if __name__=='__main__':run(Path(sys.argv[1]))
