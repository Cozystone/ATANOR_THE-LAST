from packages.shared_world.index_rewrite import remap,IndexRewrite
from packages.action_core.world import Frame,Action


def test_generic_gather_mask_and_untouched_positions():
    assert remap([3,8,5],(0,1),(-2,0))==[0,3,5]
    assert remap([[1,0,1],[0,0,0],[1,0,1]],(0,1),(-2,0))==[[0,0,0],[0,1,1],[0,1,1]]


def test_unknown_operation_abstains():
    frame=Frame([1,0],[.5,0],[[1,0],[0,0]],[[0,0],[0,0]],('n0','n1'))
    assert all(not v for _,_,v in IndexRewrite([]).predict(frame,Action('opaque',('n0','n1'))))


def test_learning_has_no_operation_name_semantics():
    before=Frame([1,0,1],[.5,0,.5],[[1,0,1],[0,0,0],[1,0,1]],[[0]*3 for _ in range(3)],('n0','n1','n2'))
    after=Frame([0,1,1],[0,.5,.5],[[0,0,0],[0,1,1],[0,1,1]],[[0]*3 for _ in range(3)],before.handles)
    action=Action('opaque_17',('n0','n1'))
    record={'before':before.to_dict(),'after':after.to_dict(),'action':action.to_dict()}
    learner=IndexRewrite([record])
    prediction=learner.predict(before,action)
    assert all(len(v)==1 for _,_,v in prediction)
    assert all(not v for _,_,v in learner.predict(before,Action('rename',action.args)))
