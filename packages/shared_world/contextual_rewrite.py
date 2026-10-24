"""Conditional index effects from observations, not authored applicability rules.

Generic action-root features: scalar values, argument-to-argument relation values
and typed incoming/outgoing histograms. Histograms alone alias different pair
relations. Every observed relation including topology is treated alike. Preserve
all consistent single-predicate partitions with existing conditional_support.
No filesystem calls, operation-name semantics, hidden-context inference or truth
guarantees. Unobserved context can still falsify this finite hypothesis family.
"""
import itertools
from .conditional_support import fit
from .index_rewrite import fields,signature,remap
from .relational import _matrices
from packages.action_core.world import Frame,Action


def context(frame,args):
    matrices={'parent':frame.parent,**_matrices(frame)}
    names=tuple(sorted(matrices))
    values=[frame.sizes[i] for i in args]
    values.extend(int(i==j) for i in args for j in args)
    for name in names:
        matrix=matrices[name]
        values.extend(matrix[i][j] for i in args for j in args)
        for i in args:
            for kind in range(3):
                values.append(sum(matrix[i][j] for j,k in enumerate(frame.kinds) if k==kind))
                values.append(sum(matrix[j][i] for j,k in enumerate(frame.kinds) if k==kind))
    return names,tuple(values)


class ContextualRewrite:
    def __init__(self,records,*,fitter=fit):
        self.fitter=fitter
        self.examples={}
        self.rules={}
        self.learn(records)

    def learn(self,records):
        touched=set()
        for record in records:
            before,after=(Frame.from_dict(record[k]) for k in ('before','after'))
            action=Action.from_dict(record['action']);key,args=signature(before,action)
            names,features=context(before,args);target=fields(after)
            candidates=tuple(itertools.product(range(-2,len(args)),repeat=len(args)))
            for name,values in fields(before).items():
                surviving=frozenset(m for m in candidates if remap(values,args,m)==target[name])
                slot=(key,names,name)
                self.examples.setdefault(slot,[]).append((features,surviving))
                touched.add(slot)
        for key in touched:
            self.rules[key]=self.fitter(self.examples[key])

    def predict(self,frame,action,conditional=True):
        key,args=signature(frame,action);names,features=context(frame,args);result=[]
        for name,values in fields(frame).items():
            rule=self.rules.get((key,names,name))
            maps=() if rule is None else rule.query(features)
            possible=[remap(values,args,m) for m in sorted(maps)]
            for address in itertools.product(range(len(values)),repeat=2 if isinstance(values[0],list) else 1):
                choices={v[address[0]][address[1]] if len(address)==2 else v[address[0]] for v in possible}
                result.append((name,address,sorted(choices)))
        return result
