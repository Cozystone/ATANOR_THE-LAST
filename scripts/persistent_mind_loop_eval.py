"""One bounded continuity/causal-contribution test; not a Mind-existence proof."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.developmental_directory_acquisition import config
from packages.action_core.episode import encode_config,digest
from packages.action_core.planner import Goal
from packages.shared_world.runtime import verify_world


def initial_records():
    read=lambda n:json.loads((ROOT/'evidence'/n).read_text())
    records=read('developmental-continual.json')['records']+read('developmental-online-eval.json')['records']
    records += [read('developmental-composition-probe.json')['rows'][0]['native_record']]
    records += [r['record'] for r in read('developmental-rewrite-scope.json')['rows'] if r['case'] in ('declared_absent','declared_present')]
    return records


def run(out):
    out.mkdir(exist_ok=False);cfg,aliases=config(4,150001)
    goals=[Goal(str(i),kinds=((aliases[s],0),(aliases[d],2))) for i,(s,d) in enumerate(((1,0),(0,2),(2,1)))]
    summary={}
    with tempfile.TemporaryDirectory(prefix='atanor_continuous_loop_') as temp:
        for arm in ('continuous','resumed','frozen','no_prediction'):
            folder=out/arm;folder.mkdir()
            intent=dict(arm=arm,config=encode_config(cfg),body_root=str(Path(temp)/arm),
                        goals=[g.to_dict() for g in goals],initial_records=initial_records())
            (folder/'intent.json').write_text(json.dumps(intent))
            workers=[]
            for budget in ([1,24] if arm=='resumed' else [24]):
                command=[sys.executable,str(ROOT/'scripts/persistent_mind_loop.py'),str(folder),digest(intent),str(budget)]
                process=subprocess.run(command,capture_output=True,text=True,timeout=180)
                if process.returncode:raise RuntimeError(process.stderr)
                workers.append(json.loads(process.stdout))
            verification=verify_world(folder/'world.sqlite',expected_config=cfg,expected_total_budget=24,
                expected_world_id='persistent-world',expected_self_id='persistent-self',expected_goals=[(g,8) for g in goals])
            with sqlite3.connect(folder/'world.sqlite') as db:
                events=[dict(seq=s,kind=k,payload=json.loads(p)) for s,k,p in db.execute('SELECT seq,kind,payload FROM events ORDER BY seq')]
            (folder/'journal.json').write_text(json.dumps(events,indent=2))
            thoughts=list(map(json.loads,(folder/'thoughts.jsonl').read_text().splitlines()))
            predictions=[e for e in events if e['kind']=='PREDICT']
            chosen=[e['payload']['action'] for e in predictions]
            thinks=[r for r in thoughts if r['kind']=='THINK' and r['chosen'] is not None]
            assert [r['chosen'] for r in thinks]==chosen
            assert [r['prediction'] for r in thinks]==[e['payload']['prediction'] for e in predictions]
            summary[arm]=dict(workers=workers,verification=verification,actions=chosen,
                completed=workers[-1]['completed'],steps=workers[-1]['steps'],
                belief_revisions=sum(r['kind']=='REVISE' and r['changed'] for r in thoughts),
                alternatives=sum(len(r['alternatives']) for r in thinks))
    a=summary['continuous'];b=summary['resumed']
    gates=dict(native_replay=all(s['verification']['green'] for s in summary.values()),
        restart_exact=a['actions']==b['actions'] and a['completed']==b['completed'],
        checkpoint_continuity=b['workers'][0]['final_model_digest']==b['workers'][1]['initial_model_digest'],
        separate_processes=b['workers'][0]['pid']!=b['workers'][1]['pid'],
        full_goals=a['completed']==3,belief_revision=a['belief_revisions']>0,
        revision_contribution=a['completed']>summary['frozen']['completed'],
        prediction_contribution=a['completed']>summary['no_prediction']['completed'])
    result=dict(verdict='BOUNDED_LOOP_SUPPORTED' if all(gates.values()) else 'LOOP_PARTIAL',gates=gates,summary=summary,
                scope='Previously exposed filesystem skill; supplied goals and heuristic; not autonomous concept/goal formation, consciousness or general intelligence')
    (out/'report.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(verdict=result['verdict'],gates=gates,summary={k:{f:v[f] for f in ('completed','steps','belief_revisions')} for k,v in summary.items()})))

if __name__=='__main__':run(Path(sys.argv[1]))
