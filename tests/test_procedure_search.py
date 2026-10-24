from packages.action_core.world import Frame,Action
from packages.action_core.planner import Goal
from packages.shared_world.relational import _view
from scripts.developmental_procedure_probe import search


class Model:
    def predict(self,state,actions):
        return [(_view(Frame([1],[0],[[1]],[[0]],('n0',))),0.) for _ in actions]


def test_expanded_action_budget_not_macro_count():
    f=Frame([0],[0],[[0]],[[0]],('n0',));a=Action('opaque',('n0',));g=Goal('g',kinds=(('n0',1),))
    plan,_,used=search(Model(),f,g,[(a,a)],budget=1,limit=10)
    assert plan==() and used==0


def test_primitive_query_exhaustion_does_not_return_half_procedure():
    f=Frame([0],[0],[[0]],[[0]],('n0',));a=Action('opaque',('n0',));g=Goal('g',kinds=(('n0',1),))
    plan,_,used=search(Model(),f,g,[(a,a)],budget=2,limit=1)
    assert plan==() and used==1


def test_unsupported_effect_never_defaults_to_keep():
    class Unknown:
        def predict(self,state,actions):return [None for _ in actions]
    f=Frame([0],[0],[[0]],[[0]],('n0',));a=Action('opaque',('n0',));g=Goal('g',kinds=(('n0',1),))
    assert search(Unknown(),f,g,[(a,)],budget=2)[0]==()
