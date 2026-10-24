import pytest
from packages.action_core.world import Frame, Action
from packages.action_core.schema import bind_schema
from packages.action_core.planner import Goal
from packages.shared_world.planning import choose


class Unknown:
    schema=bind_schema([{'id':'opaque','arity':1}])
    def predict(self,state,actions,history=()):
        return [None for _ in actions]


def test_unknown_is_explicit_abstention_not_persistence():
    frame=Frame([1],[.5],[[1]],[[0]],('n0',))
    original=frame.to_dict()
    goal=Goal('opaque-goal',sizes=(('n0',0.),))
    action,prediction,queries=choose(Unknown(),frame,goal,[Action('opaque',('n0',))],allow_partial=True)
    assert action is None and prediction is None and queries==1
    assert frame.to_dict()==original


def test_legacy_default_still_rejects_missing_prediction():
    frame=Frame([1],[.5],[[1]],[[0]],('n0',))
    with pytest.raises(ValueError,match='prediction row'):
        choose(Unknown(),frame,Goal('g',sizes=(('n0',0.),)),[Action('opaque',('n0',))])

def test_complete_only_cannot_invent_solution_from_absent_forecasts():
    frame=Frame([1],[.5],[[1]],[[0]],('n0',))
    result=choose(Unknown(),frame,Goal('g',sizes=(('n0',0.),)),[Action('opaque',('n0',))],
                  allow_partial=True,complete_only=True)
    assert result[:2]==(None,None)
