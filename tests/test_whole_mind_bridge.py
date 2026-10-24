import pytest
from packages.action_core.world import Frame, Action
from packages.action_core.planner import Goal
from scripts.whole_mind_bridge import WholeMindClient

SCHEMA=[{'id':s,'arity':1} for s in ('mkdir','empty','unlink')]
def frame(kind):
    return Frame([kind],[0.],[[0.]],[[0.]],('n0',))
def record(before, op, after):
    return dict(before=frame(before).to_dict(), action=Action(op,('n0',)).to_dict(), after=frame(after).to_dict())
def test_historical_multistep_plan_and_no_side_effect():
    client=WholeMindClient([record(1,'unlink',0),record(0,'mkdir',2)],SCHEMA)
    actions=[Action(r['id'],('n0',)) for r in SCHEMA]
    before=frame(1)
    action,forecast,_=client.choose(before,Goal('g',kinds=(('n0',2),)),actions,[])
    assert action.op=='unlink' and before.kinds==[1]
    assert forecast.cells==[('kind',[0],[0])]
    assert client.state['revision']==0
def test_unknown_is_not_observation():
    client=WholeMindClient([],SCHEMA)
    reply=client.choose(frame(1),Goal('g',kinds=(('n0',2),)),[Action(r['id'],('n0',)) for r in SCHEMA],[])
    assert reply[1].cells[0][2]==[] and client.snapshot()['records']==[]
def test_checkpoint_and_ablation():
    c=WholeMindClient([],SCHEMA,'no_memory')
    c.learn('e',frame(1),Action('unlink',('n0',)),frame(0),[])
    restored=WholeMindClient([],SCHEMA,'no_memory');restored.restore(c.snapshot())
    assert restored.snapshot()==c.snapshot() and restored.memory().d=={}
    with pytest.raises(ValueError):WholeMindClient([],SCHEMA).restore(c.snapshot())
def test_no_semantic_widening():
    with pytest.raises(ValueError):WholeMindClient([],[{'id':'copy','arity':2}])
    c=WholeMindClient([],SCHEMA)
    with pytest.raises(ValueError):c.choose(frame(1),Goal('g',sizes=(('n0',1),)),[],[])

def test_native_directory_cannot_be_converted_by_selected_alphabet():
    # Post-run diagnostic, NOT a mission retry or a repaired success claim.
    import tempfile
    from pathlib import Path
    from packages.action_core.world import Sandbox
    with tempfile.TemporaryDirectory(prefix='atanor_semantics_') as tmp:
        body=Sandbox(Path(tmp)/'body',paths=['entry'],initial={'entry':None},operations=SCHEMA)
        for operation in SCHEMA:
            assert body.step(Action(operation['id'],('n0',))) is False
            assert body.observe().kinds==[2]
