from scripts.developmental_plasticity_eval import COUNTS,ARMS,NEW_LAWS,acquire,evaluate_gates


def fake():
    return [dict(law=law,arm=arm,life=life,probe=q,count=count,
                 whole_exact=count>=(8 if arm=='fresh' else 4),common_correct=9,common_count=10)
            for law in NEW_LAWS for arm in ARMS for life in range(8) for q in range(4) for count in COUNTS]


def test_panel_cost_and_retention_gates():
    r=fake();v=evaluate_gates(r)
    assert all(v['gates'].values()) and v['means']==dict(fresh=8,weights_adam=4)
    for row in r:
        if row['arm']=='weights_adam' and row['count']==16:row['common_correct']=6
    assert not evaluate_gates(r)['gates']['retention_macro']


def test_censoring_and_stability():
    r=fake()
    for row in r:
        if row['law']==NEW_LAWS[0] and row['arm']=='weights_adam' and row['count']==16:row['whole_exact']=False
    assert acquire(r,NEW_LAWS[0],'weights_adam') is None
    assert evaluate_gates(r)['costs']['weights_adam'][NEW_LAWS[0]]==[None]*8
