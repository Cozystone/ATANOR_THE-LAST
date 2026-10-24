"""New sensor-contract DEV, not a retry of the sealed lossy-codec task gate."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_fk_tasks import encode,run
from packages.shared_world.sql_schema_sensor import schema_observation

def schema_encode(body):
    frame=encode(body)
    # This is the historical body's explicit actuator/entity binding, not a
    # cognitive feature or a rule that action on entity zero should do anything.
    sensor=schema_observation(body.con,['anchor']+['row_']*(body.n-1))
    frame.sizes=sensor['scalars']
    frame.relations['r_1']=sensor['references']
    return type(frame).from_dict(frame.to_dict())

if __name__=='__main__':
    run(*(Path(p) for p in sys.argv[1:]),encoder=schema_encode,seed_base=86001)
