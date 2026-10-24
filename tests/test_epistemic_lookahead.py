import random
import pytest
from packages.action_core.world import Action,Sandbox
from packages.shared_world.relational import RelationalLearner
from packages.shared_world.epistemic_coverage import select_for_frontier
from packages.shared_world.epistemic_lookahead import select_for_lookahead
from scripts.representation_r3_dev import configuration
from scripts.representation_r1_dev import SCHEMA

def setup(tmp_path):
    model=RelationalLearner(schema=SCHEMA,partitioned=True)
    cfg,aliases,_,_=configuration(3,812)
    actions=[Action(op,(aliases[0],)) for op in ('empty','unlink')]
    frontier=[]
    for i,action in enumerate(actions):
        body=Sandbox(tmp_path/f'train{i}',**cfg); before=body.observe()
        body.step(action); model.learn(i,before,action,body.observe())
        frontier.append((before,action))
    intermediate=Sandbox(tmp_path/'intermediate',**cfg)
    intermediate.step(actions[1])
    candidates=[(intermediate.observe(),actions[0])]
    return model,candidates,frontier

def test_predicted_intermediate_requests_real_experiment(tmp_path):
    model,candidates,frontier=setup(tmp_path)
    assert select_for_frontier(model,candidates,frontier,remaining=1,rng=random.Random(1)) is None
    snapshot=model.snapshot()
    assert select_for_lookahead(model,candidates,frontier,remaining=1,rng=random.Random(1))==0
    assert model.snapshot()==snapshot # predictions NEVER become experiences

def test_query_budget_fails_closed(tmp_path):
    model,candidates,frontier=setup(tmp_path)
    with pytest.raises(ValueError,match='budget'):
        select_for_lookahead(model,candidates,frontier,remaining=1,rng=random.Random(1),max_queries=1)

def test_forecast_cannot_be_smuggled_as_actual_candidate(tmp_path):
    model,candidates,frontier=setup(tmp_path)
    prediction=model.predict(frontier[0][0],[frontier[0][1]])[0][0].outcomes[0][1]
    with pytest.raises(ValueError):
        select_for_lookahead(model,[(prediction,candidates[0][1])],frontier,remaining=1,rng=random.Random(1))
