import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.representation_r5_dev import run_arm

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    out=p.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    root=Path(tempfile.mkdtemp(prefix='atanor_r6_dev_'));start=time.process_time()
    r=run_arm(root/'lookahead',44017,'lookahead')
    ready=r['successes']>4 and r['actions_per_success']<3 and r['acquisition_actions']<32
    report={'verdict':'R6_DEV_READY' if ready else 'R6_DEV_NO_GO','capability_claim':False,
            'cpu_seconds':time.process_time()-start,'result':r}
    (out/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2))
    print(json.dumps({**report,'result':{k:v for k,v in r.items() if k not in ('tasks','acquisitions')}},indent=2))
