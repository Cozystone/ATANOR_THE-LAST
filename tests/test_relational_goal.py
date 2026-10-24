import pytest
from packages.action_core.planner import Goal
from packages.action_core.world import Frame, Action
from packages.shared_world.partial_goal import select


def view():
    return Frame([1,1],[.2,.2],[[1,1],[1,1]],[[0,0],[0,0]],('n0','n1'),
                 {'r_0':[[1,0],[0,1]]})


def test_relation_goal_roundtrip_and_direction():
    goal=Goal('x',relations=(('r_0','n0','n1',1),))
    assert Goal.from_dict(goal.to_dict())==goal
    frame=view()
    assert goal.probability(frame)==0
    frame.relations['r_0'][0][1]=1
    assert goal.probability(frame)==1
    assert Goal('reverse',relations=(('r_0','n1','n0',1),)).probability(frame)==0
    assert not goal.holds({'n0':{'kind':1},'n1':{'kind':1}})


def test_legacy_encoding_preserved():
    goal=Goal('old',kinds=(('n0',1),))
    assert goal.to_dict()=={'id':'old','kinds':[['n0',1]],'equal':[]}
    assert Goal.from_dict(goal.to_dict())==goal


def test_fail_closed_invalid_or_unobserved():
    for rows in [(('r_0','n0','n1',True),), (('kind','n0','n1',1),),
                 (('r_0','n0','n1',1),('r_0','n0','n1',0))]:
        with pytest.raises(ValueError):Goal('x',relations=rows)
    for channel,handle in [('r_missing','n0'),('r_0','missing')]:
        with pytest.raises(ValueError):
            Goal('x',relations=((channel,handle,'n1',1),)).probability(view())


def test_partial_selector_does_not_ignore_relation_or_unknown():
    class Model:
        def predict_cells(self,frame,action):
            return [('r_0',(0,1),[] if action.op=='unknown' else [1])]
    actions=[Action('unknown',('n0',)),Action('opaque',('n0',))]
    goal=Goal('x',relations=(('r_0','n0','n1',1),))
    assert select(Model(),view(),goal,actions)[0]==actions[1]
    assert select(Model(),view(),goal,actions[:1]) is None
