import pytest
from scripts.plasticity_law_suite import LAWS,case,make
from scripts.plastic_law_world import native


@pytest.mark.parametrize('law',LAWS)
def test_real_conflicting_laws_share_codec(law):
    for seed,n in ((11,4),(12,6)):
        c=case(law,seed,n);i=c['primary'];a=c['old'][i];b=c['new'][i]
        assert c['changed'] and a['after']['kinds']!=b['after']['kinds']
        assert set(c['before'])=={'kinds','scalars','edges'}
        if law=='unique_link':assert a['accepted'] and not b['accepted']
        else:assert b['accepted']
        if law in ('null','cascade'):assert not a['accepted']
        if law=='parent_insert':assert all(x==2 for x in b['after']['kinds'][1:])
        if law=='cleanup_delete':assert b['after']['kinds'][0]==0 and 2 not in b['after']['kinds']
        if law=='broadcast_unlink':assert 2 not in b['after']['kinds']
        if law=='steal_link':assert b['after']['kinds'].count(2)==1
        body,_=make(law,seed,n,True)
        try:assert type(body).do is native.FKWorld.do
        finally:body.dispose()
