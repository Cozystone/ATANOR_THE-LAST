from packages.shared_world.partial_goal import select
from packages.action_core.world import Frame,Action
from packages.action_core.planner import Goal

class Partial:
    def predict_cells(self,frame,action):
        return [('kind',(0,),[1]),('kind',(1,),[1]),('equal',(0,1),[])]

def test_goal_progress_without_fabricated_relation():
    f=Frame([1,0],[0.,0.],[[1,0],[0,0]],[[0,0],[0,0]],('n0','n1'))
    a=Action('opaque',('n1',)); old=f.to_dict()
    chosen=select(Partial(),f,Goal('goal',kinds=(('n0',1),('n1',1))),[a])
    assert chosen[0]==a and chosen[1].to_dict()['truth_claim'] is False
    assert chosen[1].cells[-1][-1]==[] and f.to_dict()==old
    # Equality requires two existing files; creating one is legitimate progress,
    # but is NOT proof of equality. Once both already exist, unknown equality
    # alone must not count as progress.
    equality_progress=select(Partial(),f,Goal('goal',equal=(('n0','n1'),)),[a])
    assert equality_progress[1].score<1
    both=Frame([1,1],[0.,0.],[[1,0],[0,1]],[[0,0],[0,0]],('n0','n1'))
    assert select(Partial(),both,Goal('goal',equal=(('n0','n1'),)),[a]) is None
