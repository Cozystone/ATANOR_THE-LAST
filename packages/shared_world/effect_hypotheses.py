"""Inspect surviving finite effect expressions; agreement is NOT verified truth.

The legacy predictor chooses the first surviving expression for each slot. This
read-only mechanism exposes when those expressions disagree on a query instead
of mistaking program applicability for identification. No learning, authorization,
confidence calibration, automatic promotion or production wiring occurs here.
Results are relative to the current bounded grammar, stored examples and routed
leaf. The true mechanism may lie outside all these hypotheses.
"""
from packages.action_core.world import Frame,Action
from packages.action_core.model import Forecast
from .relational import _actual,_action,_view,_history,_context,_leaf,_apply,_bindings,_groups,_evaluate
from .epistemic_lookahead import _query_projection

def inspect_effects(model, query, action, history=()):
    if type(query) is Frame:
        frame=_actual(query)
        query_kind='observation_view'
    elif type(query) is Forecast:
        frame=_query_projection(query)
        query_kind='hypothesis'
        if frame is None:
            return {'status':'SOFT_QUERY_UNSUPPORTED','query_kind':query_kind,'truth_claim':False}
    else:
        raise ValueError('typed observation or forecast query required; no caller status')
    _action(action,frame,model.schema)
    history=_history(history,frame,model.schema)
    if model.rows and model.rows[0][0].relations.keys()!=frame.relations.keys():
        raise ValueError('relation vocabulary differs from learned model')
    if model.cache is None:
        model._compile()
    state=model.cache.get(action.op)
    common={'query_kind':query_kind,'truth_claim':False,'learning_revision':model.revision}
    if state is None:
        return {**common,'status':'NO_LEARNED_OPERATION','disagreement_cells':[]}
    leaf=_leaf(state['tree'],_context(frame,action,history,model.schema))
    binding=_bindings(frame,action);groups=_groups(frame,binding,model.partitioned)
    values={};applicable=[];unrouted=[]
    for label in leaf['counts']:
        program=state['programs'][label]
        if _apply(program,frame,action,model.partitioned) is None:
            unrouted.append(int(label));continue
        applicable.append(int(label))
        for slot,addresses in groups.items():
            for address in addresses:
                cell=(slot[0],address)
                for expression in program[slot]:
                    values.setdefault(cell,set()).add(_evaluate(expression,slot[0],address,frame,binding))
    disagreements=[{'field':field,'address':list(address),'possible_values':sorted(v)}
                   for (field,address),v in sorted(values.items()) if len(v)>1]
    status=('NO_APPLICABLE_ROUTED_BRANCH' if not applicable else
            'PARTIAL_ROUTING_UNSUPPORTED' if unrouted else
            'RESIDUAL_DISAGREEMENT' if disagreements else 'FINITE_SET_AGREEMENT')
    return {**common,'status':status,'routed_labels':list(map(int,leaf['counts'])),
            'applicable_labels':applicable,'unsupported_labels':unrouted,
            'disagreement_cells':disagreements}
