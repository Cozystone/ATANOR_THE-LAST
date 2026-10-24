from packages.action_core.world import Frame,Action
from packages.action_core.planner import Goal
from packages.shared_world.relational import _view
from packages.shared_world.cost_ordered_search import search
from scripts.developmental_procedure_probe import search as previous


class Model:
    def predict(self,state,actions):
        return [(_view(Frame([1],[0],[[1]],[[0]],('n0',))),0.) for _ in actions]


def test_long_proposal_cannot_preempt_shorter_native_solution():
    f=Frame([0],[0],[[0]],[[0]],('n0',));a=Action('opaque',('n0',));g=Goal('g',kinds=(('n0',1),))
    options=[(a,a),(a,)]
    assert len(previous(Model(),f,g,options)[0])==2
    assert len(search(Model(),f,g,options)[0])==1


def test_no_partial_macro_on_exhaustion_or_budget_violation():
    f=Frame([0],[0],[[0]],[[0]],('n0',));a=Action('opaque',('n0',));g=Goal('g',kinds=(('n0',1),))
    assert search(Model(),f,g,[(a,a)],limit=1)==((),(),1)
    assert search(Model(),f,g,[(a,a)],budget=1)==((),(),0)
