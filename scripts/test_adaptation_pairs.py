import copy
from scripts.adaptation_pair_isolation import compose
from scripts.developmental_plastic_world import PlasticWorld
from scripts.test_adaptation_state_ablation import equal


def test_pairs_exact_fields():
    m=PlasticWorld(45);m.enter_body(2)
    f=dict(kinds=[1,2],scalars=[.5,.6],edges=[[[0,0],[1,0]],[[0,0],[1,0]]])
    aft=copy.deepcopy(f);aft['kinds']=[0,1];m.learn(f,[3,0],aft)
    old=m.checkpoint();arms=compose(old)
    for arm in ('weights_adam','weights_replay'):
        assert equal(arms[arm]['models'],old['models'])
    assert equal(arms['weights_adam']['optimizers'],old['optimizers'])
    assert arms['weights_adam']['replay']==[]
    assert equal(arms['weights_replay']['optimizers'],arms['fresh']['optimizers'])
    assert equal(arms['weights_replay']['replay'],old['replay'])
    assert equal(arms['weights_replay']['rng'],old['rng'])
    for state in arms.values():
        p=PlasticWorld.restore(state);p.enter_body(2);p.learn(f,[3,0],aft)
    assert equal(m.checkpoint(),old)
