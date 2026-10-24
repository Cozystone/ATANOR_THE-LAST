"""Goal-directed stopping inside the finite effect hypothesis set, not authority.

A supported plan is NOT verified native success, safety, or complete causal truth.
Actual execution still belongs to the owner and must be checked natively. No
operator-specific branch or hidden desired outcome enters this generic search.
"""
from packages.action_core.world import Frame,Action
from packages.action_core.planner import Goal
from .effect_hypotheses import inspect_effects
from .epistemic_discrimination import select_discriminating
from .epistemic_lookahead import _query_projection
from .planning import choose

def agreeing_plan(model,frame,goal,actions,*,limit=4096):
    if type(frame) is not Frame or type(goal) is not Goal:
        raise ValueError('actual start view and typed requested goal required')
    frame=Frame.from_dict(frame.to_dict());goal=Goal.from_dict(goal.to_dict());goal.validate_handles(frame.handles)
    if type(actions) not in (list,tuple) or not 1<=len(actions)<=512 or any(type(a) is not Action for a in actions):
        raise ValueError('bounded permitted action surface required')
    if type(limit) is not int or limit<1:raise ValueError('query budget required')
    if goal.probability(frame)==1.:return ()
    used=0
    def successors(query,action):
        nonlocal used
        used+=1
        if used>limit:raise ValueError('complete plan support search exceeds budget')
        if inspect_effects(model,query,action)['status']!='FINITE_SET_AGREEMENT':return None
        return [s for w,s in model.predict(query,[action])[0][0].outcomes if w>0]
    for first in actions:
        states=successors(frame,first)
        if not states:continue
        if all(goal.probability(s)==1. for s in states):return (first,)
        for second in actions:
            # ONE common continuation, not a hindsight action per outcome.
            ends=[]
            for state in states:
                following=successors(state,second)
                if following is None:break
                ends.extend(following)
            else:
                if ends and all(goal.probability(s)==1. for s in ends):return (first,second)
    return None

def selected_plan_agrees(model,frame,goal,actions):
    """The unchanged execution policy must actually choose an agreeing plan.

    Existence of a good alternative is insufficient. Projected query views are
    temporary algebra for policy inspection, never observations or learned rows.
    """
    # Cheap rejection of wholly unknown paths before inspecting the full policy.
    if agreeing_plan(model,frame,goal,actions) is None:return False
    current=frame
    for _ in range(2):
        if goal.probability(current)==1.:return True
        algebra=current if type(current) is Frame else _query_projection(current)
        if algebra is None:return False
        action,_,_=choose(model,algebra,goal,actions,horizon=2,limit=32768)
        if inspect_effects(model,current,action)['status']!='FINITE_SET_AGREEMENT':return False
        states=[s for w,s in model.predict(current,[action])[0][0].outcomes if w>0]
        if not states or any(s.to_dict()!=states[0].to_dict() for s in states[1:]):return False
        current=states[0]
    return goal.probability(current)==1.

def select_for_requested_goals(model,candidates,agendas,*,remaining,rng):
    if type(remaining) is not int or remaining<0:raise ValueError('invalid acquisition budget')
    if type(agendas) not in (list,tuple) or not 1<=len(agendas)<=32:raise ValueError('bounded requested agenda required')
    if remaining==0:return None
    unresolved={}
    for item in agendas:
        if type(item) is not tuple or len(item)!=3:raise ValueError('no caller support/verified metadata')
        frame,goal,actions=item
        if type(frame) is not Frame or type(goal) is not Goal:raise ValueError('typed observation/request required')
        if not selected_plan_agrees(model,frame,goal,actions):
            for action in actions:unresolved[(repr(frame.to_dict()),action)]=(frame,action)
    if not unresolved:return None
    if len(unresolved)>512:raise ValueError('agenda frontier exceeds budget')
    return select_discriminating(model,candidates,list(unresolved.values()),remaining=remaining,rng=rng)
