import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_fk_tasks import run
from scripts.developmental_fk_schema_tasks import schema_encode
if __name__=='__main__':
    run(*(Path(p) for p in sys.argv[1:]),encoder=schema_encode,seed_base=88001,policy_comparison=True)
