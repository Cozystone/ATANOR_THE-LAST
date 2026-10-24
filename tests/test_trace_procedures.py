from packages.shared_world.trace_procedures import canonical,mine,instantiate
from packages.action_core.world import Action


def test_role_binding_preserved_without_operation_meaning():
    assert canonical([Action('a',('n2',)),Action('b',('n2','n0'))])==(('a',(0,)),('b',(0,1)))
    library=[((('a',(0,)),('b',(0,))),2)]
    allowed=[Action('a',('n0',)),Action('b',('n0',)),Action('a',('n1',))]
    assert instantiate(library,('n0','n1'),allowed)==[(allowed[0],allowed[1])]


def test_no_failed_or_discontinuous_trace_becomes_procedure():
    rows=[{'before':0,'after':1,'action':Action('a',('n0',)).to_dict(),'success':True},
          {'before':1,'after':2,'action':Action('b',('n0',)).to_dict(),'success':True}]
    assert len(mine([rows,rows]))==1
    rows[1]['before']=99
    assert mine([rows,rows])==[]
    rows[1]['before']=1;rows[1]['success']=False
    assert mine([rows,rows])==[]
