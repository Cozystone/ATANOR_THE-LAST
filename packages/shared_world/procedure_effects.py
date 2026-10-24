"""Derived sequence endpoints for an existing generic effect learner.

Not primitive observations or execution authority. Raw constituent records and
locations remain provenance; caller must authenticate lived history separately.
Only the current action learner's supported one/two-role arity is admitted.
"""
import hashlib,json
from packages.action_core.world import Action
from .trace_procedures import canonical


def symbol(sequence):
    template=canonical(sequence)
    name='procedure_'+hashlib.sha256(json.dumps(template,separators=(',',':')).encode()).hexdigest()
    handles=tuple(dict.fromkeys(h for a in sequence for h in a.args))
    if not 1<=len(handles)<=2:raise ValueError('unsupported procedure role arity')
    return Action(name,handles)


def endpoints(traces,library):
    allowed={template for template,count in library};result=[]
    lengths=sorted({len(t) for t in allowed})
    for t,trace in enumerate(traces):
        for length in lengths:
            for i in range(len(trace)-length+1):
                rows=trace[i:i+length]
                if any(r.get('success') is not True for r in rows):continue
                if any(a['after']!=b['before'] for a,b in zip(rows,rows[1:])):continue
                sequence=tuple(Action.from_dict(r['action']) for r in rows)
                if canonical(sequence) not in allowed:continue
                result.append({'before':rows[0]['before'],'after':rows[-1]['after'],
                    'action':symbol(sequence).to_dict(),'derived_sequence':True,
                    'source_window':[t,i,length],'constituents':[r['action'] for r in rows]})
    return result
