from contextlib import closing
import pytest
from packages.action_core.world import Sandbox
from packages.shared_world.runtime import WorldSession, verify_world


class Idle:
    def snapshot(self): return {'revision':0}
    def restore(self, value): assert value == {'revision':0}


def settings():
    return dict(paths=['source','container/dest'], initial={'source':b'x'}, protected=[])


def verify(path, cfg, budget=2):
    return verify_world(path, expected_config=cfg, expected_total_budget=0,
        expected_world_id='w', expected_self_id='s', expected_goals=[], expected_sensor_budget=budget)


def test_sense_persists_replays_and_budget_survives_restart(tmp_path):
    cfg=settings(); body=Sandbox(tmp_path/'body',**cfg); path=tmp_path/'life.sqlite'
    kw=dict(config=cfg,total_budget=0,world_id='w',self_id='s',sensor_budget=2)
    with closing(WorldSession(path,body,Idle(),**kw)) as world:
        original=world.state['frame']
        got=world.sense(['n1'])
        assert got['added']==['n2'] and got['frame']['kinds'][-1]==0
        assert world.state['frame']==original and body.handles==('n0','n1')
        assert world.state['sensing']==2
    with closing(WorldSession(path,body,Idle(),**kw)) as world:
        assert world.state['last_sense']==got
        with pytest.raises(ValueError): world.sense(['n1'])
    result=verify(path,cfg)
    assert result['green'],result
    assert not verify(path,cfg,budget=3)['green']


def test_rehashed_forged_sensor_observation_fails_native_replay(tmp_path):
    cfg=settings(); body=Sandbox(tmp_path/'body',**cfg); path=tmp_path/'life.sqlite'
    with closing(WorldSession(path,body,Idle(),config=cfg,total_budget=0,
            world_id='w',self_id='s',sensor_budget=4)) as world:
        forged=world.sense(['n1'])
        forged['frame']['kinds'][-1]=2
        # Deliberately produce a valid hash chain/checkpoint containing a lie.
        world._record('SENSE',forged,sensing=4,last_sense=forged)
    result=verify(path,cfg,budget=4)
    assert not result['green'] and 'sensor_native_mismatch' in result['errors']


def test_sensors_are_disabled_by_default(tmp_path):
    cfg=settings()
    with closing(WorldSession(tmp_path/'life.sqlite',Sandbox(tmp_path/'body',**cfg),Idle(),
            config=cfg,total_budget=0,world_id='w',self_id='s')) as world:
        before=world.state
        with pytest.raises(ValueError): world.sense(['n1'])
        assert world.state==before
