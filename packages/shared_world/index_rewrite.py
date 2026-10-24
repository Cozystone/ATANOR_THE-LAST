"""Empirically fitted index-remapping/zero-mask hypotheses, not action rules.

Engineer-supplied generic array algebra: each action argument position may gather
from any argument, itself, or zero-mask. Other positions retain their index.
All consistent maps survive independently per observed field. Applicability is
limited to observed operation/argument-kind signatures. No action-name branches,
native calls, prediction-as-observation, learned ontology, or truth guarantees.
"""
import itertools
from .relational import _matrices
from packages.action_core.world import Frame, Action


def fields(frame):
    return {'kind':frame.kinds,'size':frame.sizes,**_matrices(frame)}


def signature(frame,action):
    args=tuple(frame.handles.index(h) for h in action.args)
    return (action.op,tuple(frame.kinds[i] for i in args)),args


def remap(values,args,mapping):
    indices=[]
    for index in range(len(values)):
        rule=mapping[args.index(index)] if index in args else -1
        indices.append(index if rule==-1 else None if rule==-2 else args[rule])
    if isinstance(values[0],list):
        return [[0 if i is None or j is None else values[i][j] for j in indices] for i in indices]
    return [0 if i is None else values[i] for i in indices]


class IndexRewrite:
    def __init__(self,records):
        self.rules={}
        for record in records:
            before,after=(Frame.from_dict(record[k]) for k in ('before','after'))
            action=Action.from_dict(record['action']);key,args=signature(before,action)
            candidates=tuple(itertools.product(range(-2,len(args)),repeat=len(args)))
            target=fields(after)
            for name,values in fields(before).items():
                slot=(key,name)
                surviving=frozenset(m for m in candidates if remap(values,args,m)==target[name])
                self.rules[slot]=self.rules.get(slot,surviving)&surviving

    def predict(self,frame,action,conditional=True):
        key,args=signature(frame,action);result=[]
        for name,values in fields(frame).items():
            possible=[remap(values,args,m) for m in sorted(self.rules.get((key,name),()))]
            addresses=itertools.product(range(len(values)),repeat=2 if isinstance(values[0],list) else 1)
            for address in addresses:
                choices={v[address[0]][address[1]] if len(address)==2 else v[address[0]] for v in possible}
                result.append((name,address,sorted(choices)))
        return result
