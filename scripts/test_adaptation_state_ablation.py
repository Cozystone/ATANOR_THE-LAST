import copy
import torch
from scripts.adaptation_state_ablation import compose
from scripts.developmental_plastic_world import PlasticWorld


def equal(x,y):
    if isinstance(x,torch.Tensor):return torch.equal(x,y)
    if isinstance(x,dict):return x.keys()==y.keys() and all(equal(x[k],y[k]) for k in x)
    if isinstance(x,(list,tuple)):return len(x)==len(y) and all(equal(a,b) for a,b in zip(x,y))
    return x==y


def test_state_interventions_are_exact_and_independent():
    m=PlasticWorld(44);m.enter_body(2)
    f=dict(kinds=[1,2],scalars=[.5,.6],edges=[[[0,0],[1,0]],[[0,0],[1,0]]])
    after=copy.deepcopy(f);after['kinds']=[0,0]
    m.learn(f,[3,0],after);old=m.checkpoint();arms=compose(old)
    assert equal(arms['full'],old)
    assert equal(arms['weights']['models'],old['models'])
    assert equal(arms['weights']['optimizers'],arms['fresh']['optimizers']) and not arms['weights']['replay']
    assert equal(arms['replay']['models'],arms['fresh']['models'])
    assert equal(arms['replay']['replay'],old['replay']) and equal(arms['replay']['rng'],old['rng'])
    assert equal(arms['optimizer']['models'],arms['fresh']['models'])
    assert equal(arms['optimizer']['optimizers'],old['optimizers']) and not arms['optimizer']['replay']
    for i,model in enumerate(arms['head_reset']['models']):
        for k,v in model.items():
            assert equal(v,arms['fresh']['models'][i][k] if k.startswith('output.') else old['models'][i][k])
    assert not arms['head_reset']['replay']
    for state in arms.values():
        restored=PlasticWorld.restore(state);restored.enter_body(2);restored.learn(f,[3,0],after)
    arms['weights']['models'][0]['output.bias'].zero_()
    assert equal(m.checkpoint(),old)
