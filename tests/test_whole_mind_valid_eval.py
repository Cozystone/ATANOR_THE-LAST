import tempfile
from pathlib import Path
import pytest
from packages.action_core.world import Sandbox,Action
from scripts.whole_mind_valid_eval import (transitions,search,distance,INITIAL,TARGET,
    SCHEMA,MANIFEST,force_file,ReplayBody,ExternalFileEvent)

def test_native_preflight_has_ten_step_solution():
    table,checks=transitions()
    assert len(checks)==9
    assert search(INITIAL,table)==10==distance(INITIAL,table)
    assert search(INITIAL[:7]+(1,),table)==11
    assert distance((2,2,0,0,1,1,0,0),table) is None

@pytest.mark.parametrize('kind',[0,1,2])
def test_external_event_replay_and_protected_manifest(kind):
    with tempfile.TemporaryDirectory(prefix='atanor_external_fixture_') as tmp:
        paths=['entry'+str(i) for i in range(8)]+['manifest']
        initial={'manifest':MANIFEST}
        if kind:initial['entry7']=b'before' if kind==1 else None
        b=ReplayBody(Path(tmp)/'body',paths=paths,initial=initial,protected=['n8'],operations=SCHEMA)
        assert b.step(ExternalFileEvent())
        assert b.observe().kinds[7]==1 and (b.root/'manifest').read_bytes()==MANIFEST
        with pytest.raises((ValueError,TypeError,AttributeError)):
            Sandbox.step(b,ExternalFileEvent())
        assert b.step(Action('unlink',('n7',))) and b.observe().kinds[7]==0

def test_exhausted_finalization_adds_no_action_or_learning():
    from contextlib import closing
    from packages.shared_world.runtime import WorldSession
    from packages.action_core.planner import Goal
    from scripts.whole_mind_bridge import WholeMindClient
    from scripts.whole_mind_valid_finalize import close_exhausted
    with tempfile.TemporaryDirectory(prefix='atanor_terminal_fixture_') as tmp:
        cfg=dict(paths=['entry'],initial={},operations=[dict(id='empty',arity=1)],protected=[])
        b=Sandbox(Path(tmp)/'body',**cfg)
        c=WholeMindClient([],cfg['operations'])
        with closing(WorldSession(Path(tmp)/'world.sqlite',b,c,config=cfg,total_budget=1,world_id='test',self_id='test')) as w:
            w.issue_goal(Goal('g',kinds=(('n0',2),)),1);w.step()
            result=close_exhausted(w)
            assert result['native_actions_added']==0 and result['terminal']['reason']=='step_budget_exceeded'
