from scripts.developmental_fk_tasks import encode
from packages.action_core.world import Frame

class Connection:
    def execute(self, query):
        return [(1,0),(2,None)]

class Sensor:
    n=3
    con=Connection()
    def config(self): return (1,2,1)

def test_codec_preserves_observed_states_and_edges_in_valid_frame():
    frame=encode(Sensor())
    assert Frame.from_dict(frame.to_dict()).to_dict()==frame.to_dict()
    assert frame.kinds==[1,2,1]
    assert frame.relations['r_0']==[[0,0,0],[1,0,0],[0,0,0]]
