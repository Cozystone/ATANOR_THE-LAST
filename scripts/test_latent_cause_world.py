import copy
import inspect
import torch
from scripts.developmental_plastic_world import PlasticWorld
from scripts.latent_cause_world import LatentCauseWorld


def event():
    f=dict(kinds=[0,1],scalars=[0.,0.],edges=[[[0,0],[0,0]],[[0,0],[0,0]]])
    return f,[0,0],dict(f,kinds=[2,2])


def test_archive_immutable_and_resume_learning_equivalent():
    a=LatentCauseWorld(PlasticWorld(64).checkpoint());e=event();a.enter_body(2)
    tensors=copy.deepcopy(a.archive[0].checkpoint()['models'])
    for _ in range(6):a.learn(*e)
    b=LatentCauseWorld.restore(a.checkpoint())
    for obj in (a,b):obj.enter_body(2);obj.learn(*e)
    assert torch.equal(a.forecasts(e[0],[e[1]])[0],b.forecasts(e[0],[e[1]])[0])
    assert a.belief==b.belief and a.recruits==b.recruits
    assert all(torch.equal(t[k],v) for t,m in zip(tensors,a.archive[0].models) for k,v in m.state_dict().items())
    assert list(inspect.signature(a.learn).parameters)==['before','action','after']


def test_uncertainty_preserves_multiple_hypotheses():
    a=LatentCauseWorld(PlasticWorld(65).checkpoint())
    a.archive.append(PlasticWorld(66));a.belief=[.5,.5];a.enter_body(2)
    f,act,_=event()
    expected=sum(m.forecasts(f,[act])[0]*.5 for m in a.archive)
    assert torch.equal(a.forecasts(f,[act])[0],expected)
