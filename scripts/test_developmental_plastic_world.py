import copy
import io
import random
import torch
import pytest
from scripts.developmental_plastic_world import PlasticWorld


def frame(n=3):
    return dict(kinds=[1]*n,scalars=[.5]*n,
                edges=[[[int(i==j) for j in range(n)] for i in range(n)] for _ in range(2)])


def test_variable_size_and_predictions_do_not_learn():
    m=PlasticWorld(1)
    for n in (3,5):
        m.enter_body(n)
        old=[h.clone() for h in m.hidden]
        p,u=m.forecasts(frame(n),[[0,0],[1,n-1]])
        assert p.shape==(2,n,3) and u.shape==(2,)
        assert torch.allclose(p.sum(-1),torch.ones(2,n))
        assert m.revision==0 and not m.replay
        assert all(torch.equal(a,b) for a,b in zip(old,m.hidden))


def test_actual_update_restart_and_same_next_update():
    m=PlasticWorld(2);m.enter_body(3)
    before=frame();after=copy.deepcopy(before);after['kinds'][0]=0
    m.learn(before,[0,0],after)
    out=io.BytesIO();torch.save(m.checkpoint(),out);out.seek(0)
    restored=PlasticWorld.restore(torch.load(out,weights_only=True))
    assert torch.equal(m.forecasts(after,[[1,0]])[0],restored.forecasts(after,[[1,0]])[0])
    m.learn(after,[1,0],before);restored.learn(after,[1,0],before)
    assert all(torch.equal(x,y) for a,b in zip(m.models,restored.models)
               for x,y in zip(a.parameters(),b.parameters()))


def test_permutation_equivariance_not_target_id_solver():
    m=PlasticWorld(3);m.enter_body(3)
    f=frame();f['kinds']=[0,1,2];order=[2,0,1]
    perm=dict(kinds=[f['kinds'][i] for i in order],scalars=[f['scalars'][i] for i in order],
              edges=[[[e[i][j] for j in order] for i in order] for e in f['edges']])
    p,_=m.forecasts(f,[[2,0]])
    q,_=m.forecasts(perm,[[2,order.index(0)]])
    assert torch.allclose(p[:,order],q,atol=1e-6)


def test_cold_mind_still_acts_and_external_fields_rejected():
    m=PlasticWorld(4);m.enter_body(3);actions=[[0,0],[1,2]]
    assert m.choose_task(frame(),actions,[0,1,2],random.Random(1)) in actions
    bad=frame();bad['goal']=[0,1,2]
    with pytest.raises(ValueError):m.forecasts(bad,actions)
