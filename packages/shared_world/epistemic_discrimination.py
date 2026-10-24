"""Ask real experiments that distinguish residual finite effect hypotheses.

Questions include typed one-step forecasts, never training observations. Unlike
footprint coverage, different query VALUES are retained. Agreement is not truth.
Selection is only within an owner-supplied permitted menu, with explicit budgets.
"""
from packages.action_core.world import Frame,Action
from .epistemic_lookahead import _query_projection
from .epistemic_coverage import footprint
from .effect_hypotheses import inspect_effects

def select_discriminating(model,candidates,frontier,*,remaining,rng,max_queries=2048):
    if type(remaining) is not int or remaining<0 or type(max_queries) is not int or not 1<=max_queries<=2048:
        raise ValueError('invalid acquisition/query budget')
    if any(type(x) not in (list,tuple) or len(x)>512 for x in (candidates,frontier)):
        raise ValueError('bounded observation menus required')
    for row in (*candidates,*frontier):
        if type(row) is not tuple or len(row)!=2 or type(row[0]) is not Frame or type(row[1]) is not Action:
            raise ValueError('observed candidate pairs only')
    if remaining==0 or not candidates or not frontier:return None
    questions={};states={}
    def add(original,frame,action):
        key=(repr(frame.to_dict()),action)
        if key not in questions and len(questions)>=max_queries:
            raise ValueError('complete question expansion exceeds budget')
        questions.setdefault(key,(original,frame,action))
    for frame,action in frontier:
        add(frame,frame,action);states.setdefault(repr(frame.to_dict()),(frame,[]))[1].append(action)
    for frame,actions in states.values():
        for hypothesis,_ in model.predict(frame,actions):
            for weight,predicted in hypothesis.outcomes:
                if weight<=0:continue
                algebra=_query_projection(predicted)
                if algebra is None:raise ValueError('soft question unsupported')
                for action in actions:add(predicted,algebra,action)
    needed=set()
    for original,algebra,action in questions.values():
        if inspect_effects(model,original,action)['status']!='FINITE_SET_AGREEMENT':
            needed.add(footprint(model,algebra,action))
    best=None;choices=[]
    for i,(frame,action) in enumerate(candidates):
        if footprint(model,frame,action) not in needed:continue
        report=inspect_effects(model,frame,action);status=report['status']
        if status=='FINITE_SET_AGREEMENT':continue
        n=len(frame.handles);cells=2*n+(1+len(frame.relations))*n*n
        score=(2,len(report['disagreement_cells'])/cells) if status=='RESIDUAL_DISAGREEMENT' else (1,0.)
        if best is None or score>best:best=score;choices=[i]
        elif score==best:choices.append(i)
    return rng.choice(choices) if choices else None
