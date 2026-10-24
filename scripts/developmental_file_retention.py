import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_task_eval import run
if __name__=='__main__':
    run(*(Path(p) for p in sys.argv[1:]),policy_comparison=True,seed_base=91001)
