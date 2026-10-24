import random
import pytest
from packages.action_core.world import Frame, Action
from packages.shared_world.experiment_choice import select

class Model:
    def predict(self, frame, actions):
        return [(None, .9 if actions[0].args == ('n1',) else .1)]

def pairs():
    f = Frame([1,1],[0.,0.],[[1.,1.],[1.,1.]],[[0.,0.],[0.,0.]],('n0','n1'))
    return [(f,Action('opaque',('n0',))), (f,Action('opaque',('n1',)))]

def test_model_not_caller_selects_uncertainty():
    assert select(Model(),pairs(),remaining=1,rng=random.Random(1)) == 1

def test_budget_zero_never_calls_model():
    assert select(None,pairs(),remaining=0,rng=random.Random(1)) is None

def test_caller_attested_priority_rejected():
    forged = [(pairs()[0][0],pairs()[0][1],{'verified':True,'uncertainty':1})]
    with pytest.raises(ValueError):
        select(Model(),forged,remaining=1,rng=random.Random(1))

def test_ties_replay_from_same_seed():
    p = [pairs()[0]]*4
    assert select(Model(),p,remaining=1,rng=random.Random(42)) == select(Model(),p,remaining=1,rng=random.Random(42))
