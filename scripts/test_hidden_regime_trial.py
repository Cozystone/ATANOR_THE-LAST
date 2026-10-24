from scripts.hidden_regime_trial import body,frame,observation,acquisition,COUNTS


def test_regime_identity_not_in_observation():
    seen=[]
    for law in ('null','cascade','steal_link','attached_insert'):
        b,actions=body(law,17,6)
        try:seen.append((frame(b),actions))
        finally:b.dispose()
    assert all(x==seen[0] for x in seen)
    assert observation('null',17,0)['after']!=observation('cascade',17,0)['after']


def test_acquisition_requires_control_prediction_and_later_stability():
    rows=[dict(arm='latent',phase=0,count=c,life=i,whole=c>=4,success=c>=4)
          for c in COUNTS for i in range(4) for _ in range(8)]
    assert acquisition(rows,'latent',0)==4
    for r in rows:
        if r['count']==64:r['success']=False
    assert acquisition(rows,'latent',0) is None
