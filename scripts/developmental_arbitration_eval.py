"""One new paired cross-body regression gate, not shared learned-world transfer."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_fk_tasks import run as sql_run
from scripts.developmental_fk_schema_tasks import schema_encode
from scripts.developmental_task_eval import run as file_run

def run(native,output):
    output.mkdir(exist_ok=False)
    paths=[native,*[ROOT/p for p in (
        'packages/shared_world/planning.py','packages/shared_world/partial_goal.py',
        'scripts/developmental_task_eval.py','scripts/developmental_fk_tasks.py',
        'scripts/developmental_conditional_eval.py','packages/shared_world/conditional_support.py',
        'evidence/developmental-continual.json','evidence/developmental-online-eval.json',
        'evidence/developmental-fk-learning.json')]]
    digests={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    sql_run(native,ROOT/'evidence/developmental-fk-learning.json',output/'sql.json',
        encoder=schema_encode,seed_base=92001,policy_comparison=True,arbitration=True)
    file_run(ROOT/'evidence/developmental-continual.json',ROOT/'evidence/developmental-online-eval.json',
        output/'file.json',policy_comparison=True,seed_base=93001,arbitration=True)
    assert digests=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    sql=json.loads((output/'sql.json').read_text()); files=json.loads((output/'file.json').read_text())
    passed=(sql['summary']['relational']['success']==16 and sql['summary']['relational']['actions']<=28
            and files['verdict']=='RETENTION_PASS')
    result={'verdict':'BOUNDED_ARBITRATION_PASS' if passed else 'BOUNDED_ARBITRATION_FAIL',
            'sql':sql['summary'],'file':files['summary'],'source_digests':digests,
            'scope':'same cognitive algorithm, separately learned bodies; NOT knowledge transfer/agency/AGI'}
    with (output/'receipt.json').open('x') as stream:json.dump(result,stream,sort_keys=True,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='source_digests'}))

if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]))
