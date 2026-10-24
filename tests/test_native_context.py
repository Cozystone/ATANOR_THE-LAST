from contextlib import closing
import pytest
from packages.action_core.world import Sandbox
from packages.shared_world.runtime import WorldSession,verify_world


class Idle:
    def snapshot(self):return {'revision':0}
    def restore(self,value):pass


def test_hidden_initial_context_is_replayable_not_an_action_handle(tmp_path):
    cfg=dict(paths=['src','box/dst'],initial={'src':b'x'},context_initial={'box':None},protected=[])
    body=Sandbox(tmp_path/'body',**cfg)
    bare=Sandbox(tmp_path/'bare',cfg['paths'],cfg['initial'])
    assert body.observe()==bare.observe()
    assert body.handles==('n0','n1')
    path=tmp_path/'world.sqlite'
    with closing(WorldSession(path,body,Idle(),config=cfg,total_budget=0,
            world_id='w',self_id='s',sensor_budget=2)) as world:
        got=world.sense(['n1'])
        assert got['frame']['kinds'][-1]==2
    def verify(config):
        return verify_world(path,expected_config=config,expected_total_budget=0,
            expected_world_id='w',expected_self_id='s',expected_goals=[],expected_sensor_budget=2)
    assert verify(cfg)['green']
    assert not verify({**cfg,'context_initial':{}})['green']


@pytest.mark.parametrize('context',[{'../escape':None},{'src':None},{'SRC':None},{'a/b':b'x'}])
def test_context_rejects_escape_overlap_and_missing_parent(tmp_path,context):
    with pytest.raises(ValueError):
        Sandbox(tmp_path/'body',['src'],{'src':b'x'},context_initial=context)
    assert not (tmp_path/'body').exists()
