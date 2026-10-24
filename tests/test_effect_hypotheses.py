import pytest
from packages.action_core.world import Sandbox,Action
from packages.shared_world.relational import RelationalLearner,_view
from packages.shared_world.effect_hypotheses import inspect_effects
from scripts.representation_r3_dev import configuration
from scripts.representation_r1_dev import SCHEMA

def body(tmp_path,name,pattern,seed=1281,count=2):
    cfg,aliases,_,_=configuration(count,seed,pattern,b'x'*23)
    return Sandbox(tmp_path/name,**cfg),Action('empty',(aliases[0],))

def trained(tmp_path):
    model=RelationalLearner(schema=SCHEMA,partitioned=True)
    b,a=body(tmp_path,'first','independent_mixed')
    before=b.observe();b.step(a);model.learn('existing',before,a,b.observe())
    return model

def test_applicable_does_not_mean_identified_then_native_counterexample_resolves(tmp_path):
    model=trained(tmp_path)
    b,a=body(tmp_path,'missing','detached_absent')
    before=b.observe();snapshot=model.snapshot()
    report=inspect_effects(model,before,a)
    assert report['status']=='RESIDUAL_DISAGREEMENT'
    assert report['truth_claim'] is False
    assert any(c['field']=='kind' and c['possible_values']==[0,1] for c in report['disagreement_cells'])
    predicted=model.predict(before,[a])[0][0].outcomes[0][1]
    b.step(a);after=b.observe()
    assert [k.index(1) for k in predicted.kinds]!=after.kinds
    assert model.snapshot()==snapshot
    model.learn('native-counterexample',before,a,after)
    assert inspect_effects(model,before,a)['status']=='FINITE_SET_AGREEMENT'
    actual_prediction=model.predict(before,[a])[0][0].outcomes[0][1]
    assert [k.index(1) for k in actual_prediction.kinds]==after.kinds
    assert actual_prediction.sizes==after.sizes and actual_prediction.equal==after.equal
    assert actual_prediction.relations==after.relations

def test_forecast_remains_a_question_never_a_learned_observation(tmp_path):
    model=trained(tmp_path);b,a=body(tmp_path,'hypothesis','detached_absent')
    before=model.snapshot();report=inspect_effects(model,_view(b.observe()),a)
    assert report['query_kind']=='hypothesis' and model.snapshot()==before
    assert report['status']=='RESIDUAL_DISAGREEMENT'

def test_forged_identified_receipt_rejected(tmp_path):
    model=trained(tmp_path);b,a=body(tmp_path,'forged','detached_absent')
    with pytest.raises(ValueError):inspect_effects(model,{'frame':b.observe().to_dict(),'identified':True},a)

def test_no_model_does_not_claim_agreement(tmp_path):
    b,a=body(tmp_path,'none','detached_absent')
    model=RelationalLearner(schema=SCHEMA,partitioned=True)
    assert inspect_effects(model,b.observe(),a)['status']=='NO_LEARNED_OPERATION'
