"""Use predictions as experiment questions, NEVER as observed training data.

One-step horizon and finite query budget. No goal or operation-specific logic.
Frame-shaped local projections are algebraic query views only; not returned,
journaled, dispatched or passed to learn(). Actual candidates remain observations.
"""
import copy
from packages.action_core.world import Frame, Action
from packages.action_core.model import Forecast
from .contracts import JointForecast
from .epistemic_coverage import footprint
from .experiment_choice import select
from .relational import _apply

def _query_projection(forecast):
    if type(forecast) is not Forecast:
        raise ValueError('typed hypothesis required')
    clean=Forecast.from_dict(forecast.to_dict())
    if (any(sum(x==1 for x in row)!=1 or any(x not in (0,1) for x in row) for row in clean.kinds)
        or any(x not in (0,1) for matrix in (clean.equal,clean.parent,*clean.relations.values()) for row in matrix for x in row)):
        return None
    return Frame([row.index(1) for row in clean.kinds],list(clean.sizes),copy.deepcopy(clean.equal),
                 copy.deepcopy(clean.parent),clean.handles,copy.deepcopy(clean.relations))

def select_for_lookahead(model,candidates,frontier,*,remaining,rng,max_queries=512):
    if type(remaining) is not int or remaining<0 or type(max_queries) is not int or not 1<=max_queries<=512:
        raise ValueError('invalid query/action budget')
    if any(type(x) not in (list,tuple) or len(x)>512 for x in (candidates,frontier)):
        raise ValueError('bounded menus required')
    for row in (*candidates,*frontier):
        if type(row) is not tuple or len(row)!=2 or type(row[0]) is not Frame or type(row[1]) is not Action:
            raise ValueError('actual candidate pairs only, no self-attested metadata')
    if remaining==0 or not candidates or not frontier:
        return None
    if model.cache is None:
        model._compile()
    queries={}
    def add(frame,action):
        key=footprint(model,frame,action)
        if key not in queries and len(queries)>=max_queries:
            raise ValueError('complete query expansion exceeds budget')
        queries.setdefault(key,(frame,action))
    states={}
    for frame,action in frontier:
        add(frame,action)
        key=repr(frame.to_dict())
        states.setdefault(key,(frame,[]))[1].append(action)
    for frame,actions in states.values():
        for hypothesis,_ in model.predict(frame,actions):
            if type(hypothesis) is not JointForecast:
                raise ValueError('joint forecast required')
            for weight,state in hypothesis.outcomes:
                if weight<=0: continue
                query=_query_projection(state)
                if query is None:
                    raise ValueError('soft hypothesis cannot support complete discrete query expansion')
                for action in actions:
                    add(query,action)
    needed=set()
    for key,(frame,action) in queries.items():
        programs=model.cache.get(action.op,{}).get('programs',[])
        if not any(_apply(p,frame,action,model.partitioned) is not None for p in programs):
            needed.add(key)
    eligible=[i for i,(frame,action) in enumerate(candidates) if footprint(model,frame,action) in needed]
    if not eligible:
        return None
    chosen=select(model,[candidates[i] for i in eligible],remaining=remaining,rng=rng)
    return eligible[chosen]
