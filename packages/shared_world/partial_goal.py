"""One-step goal-literal optimization over partial hypotheses.

No imagined complete state, learning, domain action names or success authority.
Progress means a conservative score WITHIN the finite candidate hypothesis set,
not a guaranteed bound on reality. Native verification remains mandatory.
"""
from dataclasses import dataclass

@dataclass
class PartialGoalPrediction:
    cells: list
    score: float
    def to_dict(self):
        return {'type':'partial_goal_hypothesis','cells':self.cells,
                'goal_score':self.score,'truth_claim':False}

def select(model,frame,goal,actions):
    requirements={}
    for handle,kind in goal._required_kinds().items():
        requirements['kind',(frame.handles.index(handle),)]=kind
    for handle,size in goal.sizes:
        requirements['size',(frame.handles.index(handle),)]=size
    for left,right in goal.equal:
        requirements['equal',(frame.handles.index(left),frame.handles.index(right))]=1
    for channel,left,right,value in goal.relations:
        if channel not in frame.relations:
            raise ValueError('unobserved goal relation channel')
        requirements[channel,(frame.handles.index(left),frame.handles.index(right))]=value
    def matches(field,address,wanted):
        actual=(frame.kinds[address[0]] if field=='kind' else frame.sizes[address[0]]
                if field=='size' else (frame.equal if field=='equal' else frame.relations[field])[address[0]][address[1]])
        return abs(actual-wanted)<=1e-12
    current=sum(matches(field,address,wanted) for (field,address),wanted in requirements.items())
    best=None; best_score=current
    for action in actions:
        cells=model.predict_cells(frame,action)
        values={(field,tuple(address)):possible for field,address,possible in cells}
        supported=sum(bool(values.get(key)) and all(abs(v-wanted)<=1e-12 for v in values[key])
                      for key,wanted in requirements.items())
        if supported>best_score:
            best=(action,PartialGoalPrediction(cells,supported/len(requirements)),len(actions))
            best_score=supported
    return best

def arbitrate(model,frame,goal,actions,*,horizon=2,width=8,limit=4096):
    """Preserve a complete model-supported plan before local heuristic progress.

    Completeness is recomputed by the planner from outcomes, not caller metadata.
    It is relative to the learned model, never a guarantee about native reality.
    Account for both searches within one decision budget. No progress -> abstain.
    """
    from .planning import choose
    reserve=len(actions)
    planned=choose(model,frame,goal,actions,horizon=horizon,width=width,
                   limit=limit-reserve,allow_partial=True,complete_only=True)
    if planned[0] is not None:
        return planned
    progress=select(model,frame,goal,actions)
    used=planned[2]+reserve
    return (None,None,used) if progress is None else (progress[0],progress[1],used)
