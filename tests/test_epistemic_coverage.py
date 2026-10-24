import random
import pytest
from packages.action_core.world import Action, Sandbox
from packages.shared_world.relational import RelationalLearner
from packages.shared_world.epistemic_coverage import footprint,select_for_frontier
from scripts.representation_r3_dev import configuration
from scripts.representation_r1_dev import SCHEMA

def setup(tmp_path):
    cfg,aliases,_,_=configuration(3,812)
    body=Sandbox(tmp_path/'body',**cfg)
    action=Action('empty',(aliases[0],))
    return RelationalLearner(schema=SCHEMA,partitioned=True),body,action

def test_missing_effect_selected_then_actual_learning_stops(tmp_path):
    model,body,action=setup(tmp_path)
    before=body.observe(); menu=[(before,action)]
    assert select_for_frontier(model,menu,menu,remaining=1,rng=random.Random(1))==0
    body.step(action); model.learn('actual',before,action,body.observe())
    assert select_for_frontier(model,menu,menu,remaining=1,rng=random.Random(1)) is None

def test_selector_never_updates_model(tmp_path):
    model,body,action=setup(tmp_path); snapshot=model.snapshot()
    menu=[(body.observe(),action)]
    select_for_frontier(model,menu,menu,remaining=1,rng=random.Random(1))
    assert model.snapshot()==snapshot

def test_forged_coverage_metadata_rejected(tmp_path):
    model,body,action=setup(tmp_path)
    with pytest.raises(ValueError):
        select_for_frontier(model,[(body.observe(),action,{'covered':True})],[],remaining=1,rng=random.Random(1))

def test_footprint_transfers_across_cardinality_and_names(tmp_path):
    model,body,action=setup(tmp_path)
    cfg,aliases,_,_=configuration(5,543)
    other=Sandbox(tmp_path/'other',**cfg)
    assert footprint(model,body.observe(),action)==footprint(model,other.observe(),Action('empty',(aliases[0],)))

def test_zero_budget_abstains(tmp_path):
    model,body,action=setup(tmp_path); menu=[(body.observe(),action)]
    assert select_for_frontier(model,menu,menu,remaining=0,rng=random.Random(1)) is None
