"""Counterexample fixture, NOT learned capability or domain runtime cognition."""
from packages.action_core.world import Frame,Action
from packages.action_core.schema import bind_schema
from packages.action_core.planner import Goal
from packages.shared_world.relational import _view
from packages.shared_world.epistemic_lookahead import _query_projection
from packages.shared_world.planning import choose
from packages.shared_world.partial_goal import select,arbitrate

class FixtureOracle:
    schema=bind_schema([{'id':op,'arity':1} for op in ('a','b','c')])
    def outcome(self,frame,action):
        f=frame if type(frame) is Frame else _query_projection(frame)
        current=tuple(f.kinds)
        # a offers immediate partial success but is an absorbing dead end;
        # b temporarily loses a satisfied literal; c then completes all goals.
        states={((1,0,0),'a'):(1,1,0),((1,0,0),'b'):(0,0,0),((0,0,0),'c'):(1,1,1)}
        return Frame(list(states.get((current,action.op),current)),list(f.sizes),
                     f.equal,f.parent,f.handles)
    def predict(self,frame,actions,history=()):
        return [(_view(self.outcome(frame,a)),0.) for a in actions]
    def predict_cells(self,frame,action):
        after=self.outcome(frame,action)
        return [('kind',(i,),[v]) for i,v in enumerate(after.kinds)]

def test_immediate_progress_can_override_a_valid_complete_plan():
    f=Frame([1,0,0],[0.]*3,[[1,0,0],[0,1,0],[0,0,1]],[[0]*3 for _ in range(3)],('n0','n1','n2'))
    actions=[Action(op,('n0',)) for op in ('a','b','c')]
    goal=Goal('g',kinds=tuple((h,1) for h in f.handles))
    oracle=FixtureOracle()
    planned=choose(oracle,f,goal,actions,horizon=2)[0]
    greedy=select(oracle,f,goal,actions)[0]
    assert planned.op=='b' and greedy.op=='a'
    trap=oracle.outcome(f,greedy)
    assert all(oracle.outcome(trap,a).kinds==trap.kinds for a in actions)
    assert goal.probability(oracle.outcome(oracle.outcome(f,planned),actions[2]))==1
    repaired=arbitrate(oracle,f,goal,actions,horizon=2)
    assert repaired[0]==planned
    assert repaired[2]<=4096
