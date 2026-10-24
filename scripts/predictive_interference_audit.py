"""Diagnostic parameter intervention ONLY. Oracle labels never enter a learner.

Tests a specified initial-sensitivity hypothesis, not all possible nonlinear
interference. No training, no changed preregistered capability result.
"""
import json
import time
import sys
from pathlib import Path
import statistics
import torch
from torch.nn.utils import parameters_to_vector, vector_to_parameters
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_plastic_world import PlasticWorld
from scripts.developmental_plasticity_eval import NEW_LAWS
from scripts.adaptation_pair_isolation import digest


def measure(model,c,index,gradient=False):
    model.enter_body(c['n'])
    probs=torch.stack([m(c['before'],[c['actions'][index]],h)[0].softmax(-1)
                       for m,h in zip(model.models,model.hidden)]).mean(0)[0]
    truth=torch.tensor(c['new'][index]['after']['kinds'])
    loss=-probs.gather(1,truth[:,None]).clamp_min(1e-12).log().mean()
    params=[p for m in model.models for p in m.parameters()]
    g=torch.cat([v.flatten() for v in torch.autograd.grad(loss,params)]) if gradient else None
    return float(loss.detach()),probs.argmax(-1).tolist()==truth.tolist(),g


def projection(delta,gradient):
    dot=float(delta@gradient)
    return gradient*(max(0.,dot)/max(float(gradient@gradient),1e-30))


def run(out):
    out.mkdir(exist_ok=False);start=time.monotonic()
    src=ROOT/'evidence/developmental-plasticity-panel-v1'
    rows=list(map(json.loads,(src/'probes.jsonl').read_text().splitlines()))
    cases={r['id']:r['data'] for r in map(json.loads,(src/'cases.jsonl').read_text().splitlines())}
    idx={(r['law'],r['life'],r['probe'],r['count']):r for r in rows if r['arm']=='weights_adam'}
    paths=[Path(__file__),ROOT/'scripts/developmental_plastic_world.py',ROOT/'docs/ATANOR_INTERFERENCE_V1_PREREGISTRATION.md',src/'probes.jsonl',src/'cases.jsonl']
    paths += [src/f'{law}-{life}-weights_adam-{count}.pt' for law in NEW_LAWS for life in range(8) for count in (0,16)]
    hashes={str(p):digest(p) for p in paths}
    (out/'attempt.json').write_text(json.dumps(hashes,indent=2))
    findings=[]
    for law in NEW_LAWS:
        for life in range(8):
            old=PlasticWorld.restore(torch.load(src/f'{law}-{life}-weights_adam-0.pt',weights_only=True))
            new=PlasticWorld.restore(torch.load(src/f'{law}-{life}-weights_adam-16.pt',weights_only=True))
            params=[p for m in new.models for p in m.parameters()]
            initial=parameters_to_vector([p for m in old.models for p in m.parameters()]).detach().clone()
            final=parameters_to_vector(params).detach().clone();delta=final-initial
            for q in range(4):
                c=cases[idx[law,life,q,0]['case_id']]
                for action in c['common']:
                    if time.monotonic()-start>1200:raise TimeoutError('single audit20min cap')
                    truth=c['new'][action]['after']['kinds']
                    if idx[law,life,q,0]['predictions'][action]!=truth:continue
                    vector_to_parameters(final.clone(),params)
                    l0,correct0,g=measure(old,c,action,True)
                    l1,correct1,_=measure(new,c,action)
                    assert correct0
                    assert correct1==(idx[law,life,q,16]['predictions'][action]==truth)
                    remove=projection(delta,g)
                    vector_to_parameters((final-remove).clone(),params)
                    lp,cp,_=measure(new,c,action)
                    generator=torch.Generator().manual_seed(972000+len(findings))
                    random=torch.randn(delta.shape,generator=generator)
                    random=random/random.norm().clamp_min(1e-30)*remove.norm()
                    vector_to_parameters((final-random).clone(),params)
                    lr,cr,_=measure(new,c,action)
                    row=dict(law=law,life=life,probe=q,action=action,before=l0,after=l1,
                             projected_loss=lp,random_loss=lr,lost=not correct1,
                             projected_correct=cp,random_correct=cr,
                             sensitivity_dot=float(delta@g),
                             cosine=float((delta@g)/(delta.norm()*g.norm()).clamp_min(1e-30)),
                             removed_fraction=float(remove.norm()/delta.norm().clamp_min(1e-30)))
                    findings.append(row)
                    with (out/'raw.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
            vector_to_parameters(final,params)
        print(json.dumps(dict(law=law,rows=len(findings),seconds=time.monotonic()-start)),flush=True)
    lost=[r for r in findings if r['lost']];kept=[r for r in findings if not r['lost']]
    assert len(findings)==396 and len(lost)==234
    harmful=sum(r['sensitivity_dot']>0 for r in lost)/len(lost)
    rescue=sum(r['projected_correct'] for r in lost)/len(lost)
    random_rescue=sum(r['random_correct'] for r in lost)/len(lost)
    damage=sum(max(0,r['after']-r['before']) for r in lost)
    reduction=sum(r['after']-r['projected_loss'] for r in lost)/max(damage,1e-30)
    random_reduction=sum(r['after']-r['random_loss'] for r in lost)/max(damage,1e-30)
    gates=dict(harmful_alignment=harmful>=.75,actual_rescue=rescue>=.20,
               rescue_over_random=rescue-random_rescue>=.10,
               loss_damage_reduced=reduction>=.25,
               loss_reduction_over_random=reduction-random_reduction>=.20)
    assert all(digest(Path(p))==h for p,h in hashes.items())
    report=dict(verdict='INTERFERENCE_SUPPORTED' if all(gates.values()) else 'INTERFERENCE_TEST_INCONCLUSIVE',
                gates=gates,previous_correct=len(findings),lost=len(lost),kept=len(kept),
                harmful_fraction=harmful,rescue_fraction=rescue,random_rescue_fraction=random_rescue,
                loss_damage_reduction=reduction,random_damage_reduction=random_reduction,
                mean_removed_fraction=statistics.mean(r['removed_fraction'] for r in lost),
                seconds=time.monotonic()-start,hashes=hashes,
                scope='Initial old-loss sensitivity projection of total observed parameter displacement. Oracle diagnostic only; no learning algorithm or capability claim.')
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='hashes'}),flush=True)

if __name__=='__main__':run(Path(sys.argv[1]))
