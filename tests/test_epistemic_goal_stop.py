import json
from pathlib import Path
import random
import pytest
from packages.action_core.world import Frame,Action,Sandbox
from packages.shared_world.relational import RelationalLearner
from packages.shared_world.epistemic_goal_stop import agreeing_plan,select_for_requested_goals,selected_plan_agrees
from scripts.representation_r3_dev import configuration,make_goal,native_success
from scripts.representation_r1_dev import SCHEMA

def model_without_copy():
    model=RelationalLearner(schema=SCHEMA,partitioned=True)
    rows=json.loads((Path(__file__).parents[1]/'evidence/r3-training/experience.json').read_text())
    for i,row in enumerate(rows):
        if row['action']['op']=='copy':continue
        model.learn(i,Frame.from_dict(row['before']),Action.from_dict(row['action']),Frame.from_dict(row['after']))
    return model

@pytest.mark.parametrize('collective',[False,True])
def test_stops_with_native_successful_plan_despite_unlearned_unrelated_operation(tmp_path,collective):
    model=model_without_copy();cfg,aliases,reference,payload=configuration(4,992811)
    body=Sandbox(tmp_path/'body',**cfg);frame=body.observe();goal=make_goal(body,aliases,collective)
    snapshot=model.snapshot();plan=agreeing_plan(model,frame,goal,body.actions())
    assert plan is not None and len(plan)<=2 and 'copy' not in model.cache
    assert select_for_requested_goals(model,[(frame,body.actions()[0])],[(frame,goal,body.actions())],remaining=32,rng=random.Random(1)) is None
    assert model.snapshot()==snapshot
    for action in plan:body.step(action)
    assert native_success(body,aliases,reference,payload,collective)

def test_unknown_effects_do_not_claim_supported_plan(tmp_path):
    cfg,aliases,_,_=configuration(3,3219);body=Sandbox(tmp_path/'unknown',**cfg)
    model=RelationalLearner(schema=SCHEMA,partitioned=True)
    assert agreeing_plan(model,body.observe(),make_goal(body,aliases,False),body.actions()) is None

def test_good_alternative_does_not_excuse_bad_selected_policy(tmp_path,monkeypatch):
    model=model_without_copy();cfg,aliases,_,_=configuration(4,992812)
    body=Sandbox(tmp_path/'bad-policy',**cfg);goal=make_goal(body,aliases,False)
    assert agreeing_plan(model,body.observe(),goal,body.actions()) is not None
    monkeypatch.setattr('packages.shared_world.epistemic_goal_stop.choose',lambda *args,**kwargs:(Action('empty',(aliases[0],)),None,0))
    assert not selected_plan_agrees(model,body.observe(),goal,body.actions())

def test_forged_support_flag_rejected(tmp_path):
    cfg,aliases,_,_=configuration(3,3220);body=Sandbox(tmp_path/'forged',**cfg)
    model=RelationalLearner(schema=SCHEMA,partitioned=True)
    with pytest.raises(ValueError):
        select_for_requested_goals(model,[],[(body.observe(),make_goal(body,aliases,False),body.actions(),{'verified':True})],remaining=1,rng=random.Random(1))
