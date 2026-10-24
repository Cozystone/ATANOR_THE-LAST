"""Frozen four-life replication; NOT a seed search or single persistent life.

Four independent same-initial-state comparisons, all reported including failures.
Acquisition seeds148001..148004, choice seeds148101..148104, task seeds149001/2,
149003/4,149005/6,149007/8. Reverse acquisition action order on odd life indices.
Unchanged8actions/full menu/effect languages/scoring,2tasks per arm/life. Task
action order unchanged. Per-life180s cap inherited; no retries. PASS if missing
>=6/8, >=random+2 and >=none+2, no paired life success loss vs random, all native
replays and retention pass. This is robustness on same mechanics, NOT transfer,
persistent-self continuity, policy learning, or autonomous world construction.
"""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_directory_acquisition import run


def main(output):
    output.mkdir(exist_ok=False);results=[]
    for life in range(4):
        result=run(output/str(life),acquisition_seed=148001+life,
            task_seed=149001+2*life,choice_seed=148101+life,reverse_actions=bool(life%2))
        results.append(dict(life=life,summary=result['summary'],verified=result['verified']))
    total={arm:sum(r['summary'][arm] for r in results) for arm in ('none','random','missing')}
    passed=(all(r['verified'] for r in results) and total['missing']>=6
        and all(total['missing']>=total[a]+2 for a in ('none','random'))
        and all(r['summary']['missing']>=r['summary']['random'] for r in results))
    report=dict(verdict='BOUNDED_REPLICATION_GAIN' if passed else 'REPLICATION_NO_GO',
        scope=__doc__,totals=total,lives=results)
    (output/'report.json').write_text(json.dumps(report,sort_keys=True))
    print(json.dumps({k:v for k,v in report.items() if k!='scope'}))


if __name__=='__main__':main(Path(sys.argv[1]))
