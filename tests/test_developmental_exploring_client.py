from contextlib import closing
import pytest
from packages.action_core.world import Sandbox
from packages.action_core.planner import Goal
from packages.shared_world.runtime import WorldSession, verify_world
from scripts.developmental_exploring_client import ExploringClient
from scripts.developmental_persistent_client import PersistentClient


def test_default_abstains_exploration_learns_and_restarts(tmp_path):
    schema=[{'id':'rename','arity':2}]
    cfg=dict(paths=['a','b'],initial={'a':None},protected=set(),operations=schema)
    body=Sandbox(tmp_path/'body',**cfg)
    goal=Goal('move',kinds=(('n0',0),('n1',2)))
    base=PersistentClient([],schema=schema)
    assert base.choose(body.observe(),goal,body.actions(),[]) is None
    client=ExploringClient([],schema=schema,exploration_seed=3)
    before=client.snapshot()
    choice=client.choose(body.observe(),goal,body.actions(),[])
    assert choice is not None and choice[2]<=client.limit
    assert client.snapshot()==before  # prediction is not experience
    restored=ExploringClient([],schema=schema,exploration_seed=3)
    restored.restore(before)
    assert restored.choose(body.observe(),goal,body.actions(),[])[0]==choice[0]
    with pytest.raises(ValueError):
        ExploringClient([],schema=schema,exploration_seed=4).restore(before)
    path=tmp_path/'life.sqlite'
    kwargs=dict(config=cfg,total_budget=4,world_id='w',self_id='s')
    with closing(WorldSession(path,body,client,**kwargs)) as world:
        world.issue_goal(goal,4)
        world.step()
        checkpoint=client.snapshot()
        assert checkpoint['revision']==1
    with closing(WorldSession(path,body,restored,**kwargs)) as world:
        assert restored.snapshot()==checkpoint
        if world.state['active'] is not None: world.run_goal()
    assert verify_world(path,expected_config=cfg,expected_total_budget=4,
        expected_world_id='w',expected_self_id='s',expected_goals=[(goal,4)])['green']


def test_insufficient_query_budget_abstains(tmp_path):
    schema=[{'id':'rename','arity':2}]
    body=Sandbox(tmp_path/'b',paths=['a','b'],initial={'a':None},protected=set(),operations=schema)
    client=ExploringClient([],schema=schema,limit=4)
    assert client.choose(body.observe(),Goal('g',kinds=(('n1',2),)),body.actions(),[]) is None
