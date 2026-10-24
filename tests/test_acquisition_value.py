from packages.action_core.world import Frame,Action
from packages.shared_world.acquisition_value import AcquisitionValue


def test_credit_not_preferred_argument_determines_choice():
    frame=Frame([1,1],[0.,0.],[[1.,1.],[1.,1.]],[[0.,0.],[0.,0.]],('n0','n1'))
    action=Action('opaque',('n0','n1'))
    policy=AcquisitionValue()
    policy.learn(frame,action,'n0',-1.)
    policy.learn(frame,action,'n1',1.)
    assert policy.choose(frame,action)=='n1'
    # New operation spelling and reversed handle roles do not encode the answer.
    reversed_action=Action('unseen',('n1','n0'))
    assert policy.choose(frame,reversed_action)=='n0'
    policy=AcquisitionValue()
    policy.learn(frame,action,'n0',1.)
    policy.learn(frame,action,'n1',-1.)
    assert policy.choose(frame,action)=='n0'


def test_balanced_exploration_visits_untried_roles():
    import random
    from packages.shared_world.acquisition_value import features
    frame=Frame([1]*3,[0.]*3,[[1.]*3 for _ in range(3)],[[0.]*3 for _ in range(3)],('n0','n1','n2'))
    action=Action('opaque',('n0','n1')); policy=AcquisitionValue(); rng=random.Random(7)
    seen=set()
    for _ in range(3):
        h=policy.explore(frame,action,rng); seen.add(features(frame,action,h))
        policy.learn(frame,action,h,0.)
    assert len(seen)==3
