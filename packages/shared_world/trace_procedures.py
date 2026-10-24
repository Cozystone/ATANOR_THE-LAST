"""Parameterize repeated observed action sequences; no effects or applicability.

Mining is not verification. Caller owns provenance; every proposed instance must
be checked by the learned model and body. No task IDs or operation semantics.
"""
import itertools
from collections import Counter
from packages.action_core.world import Action


def canonical(sequence):
    roles={};result=[]
    for action in sequence:
        indices=[]
        for handle in action.args:
            if handle not in roles:roles[handle]=len(roles)
            indices.append(roles[handle])
        result.append((action.op,tuple(indices)))
    return tuple(result)


def mine(traces,*,length=2,min_episodes=2):
    counts=Counter()
    for trace in traces:
        sequences=set()
        for i in range(len(trace)-length+1):
            rows=trace[i:i+length]
            if any(r.get('success') is not True or 'action' not in r for r in rows):continue
            if any(a['after']!=b['before'] for a,b in zip(rows,rows[1:])):continue
            sequences.add(canonical([Action.from_dict(r['action']) for r in rows]))
        counts.update(sequences)
    return [(template,count) for template,count in sorted(counts.items(),key=lambda x:(-x[1],x[0])) if count>=min_episodes]


def instantiate(library,handles,permitted):
    allowed=set(permitted);result=[]
    for template,_ in library:
        arity=1+max(i for _,args in template for i in args)
        for binding in itertools.permutations(handles,arity):
            sequence=tuple(Action(op,tuple(binding[i] for i in args)) for op,args in template)
            if all(a in allowed for a in sequence):result.append(sequence)
    return result
