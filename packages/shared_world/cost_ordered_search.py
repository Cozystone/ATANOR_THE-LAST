"""Bounded native-length search over proposed action sequences.

Every primitive is model-queried; macros carry no outcome authority. Keep a
model-supported incumbent on query exhaustion, without an optimality claim.
No beam pruning, no learned action semantics, no observation writes.
"""
import heapq,itertools
from .epistemic_lookahead import _query_projection


def search(model,frame,goal,options,budget=4,limit=2048):
    serial=itertools.count();queue=[(0,next(serial),frame,(),())]
    cache={};seen={repr(frame.to_dict()):0};used=0;incumbent=None
    while queue:
        cost,_,state,prefix,witnesses=heapq.heappop(queue)
        if incumbent is not None and cost>=len(incumbent[0]):break
        if seen[repr(state.to_dict())]<cost:continue
        if goal.probability(state)==1:return prefix,witnesses,used
        for sequence in options:
            total=cost+len(sequence)
            if not sequence or total>budget:continue
            if incumbent is not None and total>=len(incumbent[0]):continue
            current=state;path=[]
            for action in sequence:
                key=(repr(current.to_dict()),action)
                if key not in cache:
                    if used>=limit:return (*incumbent,used) if incumbent else ((),(),used)
                    row=model.predict(current,[action])[0];used+=1
                    cache[key]=None if row is None or row[1]!=0 else _query_projection(row[0])
                current=cache[key]
                if current is None:break
                path.append(current)
            if current is None:continue
            plan=prefix+sequence;predicted=witnesses+tuple(path)
            if goal.probability(current)==1:
                incumbent=(plan,predicted);continue
            key=repr(current.to_dict())
            if seen.get(key,budget+1)<=total:continue
            seen[key]=total
            heapq.heappush(queue,(total,next(serial),current,plan,predicted))
    return (*incumbent,used) if incumbent else ((),(),used)
