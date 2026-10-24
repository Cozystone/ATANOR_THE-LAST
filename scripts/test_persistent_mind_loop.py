from scripts.persistent_mind_loop import completed_count,decode_config


def test_unfinished_goal_summary_does_not_crash():
    assert completed_count([{'result':None},{},{'result':{'completed':False}},
                            {'result':{'completed':True}}])==1


def test_config_decode_preserves_absent_and_bytes():
    assert decode_config(dict(initial={'a':None,'b':'ff00'}))['initial']=={'a':None,'b':b'\xff\x00'}
