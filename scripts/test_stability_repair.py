import torch
from scripts.developmental_plastic_world import PlasticWorld
from scripts.stable_plastic_world import StablePlasticWorld


def test_teacher_is_immutable_and_new_observation_updates_only_student():
    f=dict(kinds=[0,1],scalars=[0.,0.],edges=[[[0,0],[0,0]],[[0,0],[0,0]]])
    a=dict(f,kinds=[1,1])
    original=PlasticWorld(23);original.enter_body(2)
    original.learn(f,[0,0],a)
    m=StablePlasticWorld.from_life(original.checkpoint());m.enter_body(2)
    before=[{k:v.clone() for k,v in t.state_dict().items()} for t in m.teachers]
    p=m.forecasts(f,[[0,0]])[0].clone()
    m.learn(f,[0,0],dict(f,kinds=[2,1]))
    assert all(torch.equal(v,before[i][k]) for i,t in enumerate(m.teachers) for k,v in t.state_dict().items())
    assert all(p.grad is None for t in m.teachers for p in t.parameters())
    m.enter_body(2)
    assert not torch.equal(p,m.forecasts(f,[[0,0]])[0])
    assert len(m.anchors)==8
