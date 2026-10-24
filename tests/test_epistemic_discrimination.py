import random
import pytest
from packages.action_core.world import Action,Sandbox
from packages.shared_world.relational import RelationalLearner
from packages.shared_world.epistemic_discrimination import select_discriminating
from scripts.representation_r3_dev import configuration
from scripts.representation_r1_dev import SCHEMA

def setup(tmp_path):
    model=RelationalLearner(schema=SCHEMA,partitioned=True)
    cfg,aliases,_,_=configuration(2,1281,'independent_mixed',b'x'*23)
    actions=[Action(op,(aliases[0],)) for op in ('empty','unlink')];frontier=[]
    for i,action in enumerate(actions):
        body=Sandbox(tmp_path/str(i),**cfg);before=body.observe();body.step(action)
        model.learn(i,before,action,body.observe());frontier.append((before,action))
    body=Sandbox(tmp_path/'candidate',**cfg);body.step(actions[1])
    return model,[(frontier[0][0],actions[0]),(body.observe(),actions[0])],frontier

def test_selects_actual_discriminator_not_already_agreeing_example(tmp_path):
    model,candidates,frontier=setup(tmp_path);snapshot=model.snapshot()
    assert select_discriminating(model,candidates,frontier,remaining=1,rng=random.Random(1))==1
    assert model.snapshot()==snapshot

def test_values_not_just_footprints_preserved(tmp_path):
    model,candidates,frontier=setup(tmp_path)
    assert candidates[0][0].kinds!=candidates[1][0].kinds
    assert select_discriminating(model,candidates,frontier,remaining=1,rng=random.Random(12))==1

def test_overflow_does_not_silently_claim_identification(tmp_path):
    model,candidates,frontier=setup(tmp_path)
    with pytest.raises(ValueError,match='budget'):
        select_discriminating(model,candidates,frontier,remaining=1,rng=random.Random(1),max_queries=1)

def test_no_budget_no_experiment(tmp_path):
    model,candidates,frontier=setup(tmp_path)
    assert select_discriminating(model,candidates,frontier,remaining=0,rng=random.Random(1)) is None
