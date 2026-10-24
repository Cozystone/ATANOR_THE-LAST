"""Task-observation footprint acquisition; coverage is not truth or authority.

The existing effect grammar supplies the signature. No goal, result, operation
semantics or native path enters this selector. Stop once every current footprint
has an applicable learned program; this heuristic may stop too early and must be
tested on real subsequent actions. No production wiring.
"""
from packages.action_core.world import Frame, Action
from .relational import _actual, _action, _bindings, _groups, _apply
from .experiment_choice import select

def footprint(model, frame, action):
    frame = _actual(frame)
    _action(action, frame, model.schema)
    return action.op, tuple(sorted(_groups(frame,_bindings(frame,action),model.partitioned)))

def select_for_frontier(model, candidates, frontier, *, remaining, rng):
    if type(remaining) is not int or remaining < 0:
        raise ValueError('invalid acquisition budget')
    if any(type(x) not in (list,tuple) or len(x)>512 for x in (candidates,frontier)):
        raise ValueError('bounded observation/action menus required')
    for row in (*candidates,*frontier):
        if type(row) is not tuple or len(row)!=2 or type(row[0]) is not Frame or type(row[1]) is not Action:
            raise ValueError('no caller scores, outcomes or source assertions')
    if remaining==0 or not candidates or not frontier:
        return None
    if model.cache is None:
        model._compile()
    needed=set()
    for frame,action in frontier:
        signature=footprint(model,frame,action)
        programs=model.cache.get(action.op,{}).get('programs',[])
        if not any(_apply(p,frame,action,model.partitioned) is not None for p in programs):
            needed.add(signature)
    eligible=[i for i,(frame,action) in enumerate(candidates) if footprint(model,frame,action) in needed]
    if not eligible:
        # No menu action can address a currently missing footprint; do not buy
        # irrelevant experience. This is abstention, not proof of understanding.
        return None
    selected=select(model,[candidates[i] for i in eligible],remaining=remaining,rng=rng)
    return eligible[selected]
