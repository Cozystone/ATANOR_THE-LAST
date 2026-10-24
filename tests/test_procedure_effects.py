import pytest
from packages.action_core.world import Action
from packages.shared_world.procedure_effects import symbol,endpoints
from packages.shared_world.trace_procedures import mine


def test_symbols_bind_roles_not_native_names_or_effects():
    a=symbol([Action('x',('n0',)),Action('y',('n0',))])
    b=symbol([Action('x',('n9',)),Action('y',('n9',))])
    assert a.op==b.op and a.args!=b.args
    assert a.op!=symbol([Action('y',('n0',)),Action('x',('n0',))]).op
    with pytest.raises(ValueError):symbol([Action('x',('n0','n1')),Action('y',('n2',))])


def test_endpoints_are_derived_and_require_continuous_success():
    rows=[dict(before=0,after=1,action=Action('x',('n0',)).to_dict(),success=True),
          dict(before=1,after=2,action=Action('y',('n0',)).to_dict(),success=True)]
    library=mine([rows,rows]);folded=endpoints([rows],library)
    assert folded[0]['before']==0 and folded[0]['after']==2
    assert folded[0]['derived_sequence'] and folded[0]['source_window']==[0,0,2]
    rows[1]['before']=3
    assert endpoints([rows],library)==[]
