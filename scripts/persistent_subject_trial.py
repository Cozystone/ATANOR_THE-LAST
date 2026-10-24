"""One composite intent; no intermediate goal schedule; bounded native test."""
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.persistent_mind_loop_eval import initial_records
from scripts.developmental_directory_acquisition import config
from packages.action_core.episode import encode_config,digest
from packages.action_core.world import Sandbox,Action
from packages.action_core.planner import Goal
from packages.shared_world.runtime import verify_world


def setup(seed):
    cfg,aliases=config(4,seed)
    cfg['initial'][cfg['paths'][int(aliases[3][1:])]]=None
    goal=Goal('arrange-workspace',kinds=tuple((h,2 if i in (0,2) else 0) for i,h in enumerate(aliases)))
    return cfg,goal


def run(out):
    out.mkdir(exist_ok=False);results=[]
    with tempfile.TemporaryDirectory(prefix='atanor_subject_') as tmp:
        for seed in (260001,260002,260003):
            cfg,goal=setup(seed)
            for arm in ('resumed','frozen','no_prediction'):
                folder=out/f'{seed}-{arm}';folder.mkdir();root=Path(tmp)/folder.name
                intent=dict(arm=arm,config=encode_config(cfg),body_root=str(root),goals=[goal.to_dict()],
                            initial_records=initial_records(),total_budget=24,goal_budget=24)
                (folder/'intent.json').write_text(json.dumps(intent))
                workers=[];external={};interventions=[]
                for part,budget in enumerate((1,1,1,24)):
                    p=subprocess.run([sys.executable,str(ROOT/'scripts/persistent_mind_loop.py'),
                                      str(folder),digest(intent),str(budget)],capture_output=True,text=True,timeout=180)
                    if p.returncode:raise RuntimeError(p.stderr)
                    worker=json.loads(p.stdout);workers.append(worker)
                    if part==0:
                        body=Sandbox.attach(root,**{k:v for k,v in cfg.items() if k!='initial'})
                        before=body.observe();dirs=[h for h,k in zip(before.handles,before.kinds) if k==2]
                        absent=[h for h,k in zip(before.handles,before.kinds) if k==0]
                        if not dirs or not absent:raise RuntimeError('environment intervention unavailable')
                        action=Action('rename',(dirs[0],absent[0]))
                        assert body.step(action)
                        with sqlite3.connect(folder/'world.sqlite') as db:seq=db.execute('SELECT MAX(seq) FROM events').fetchone()[0]+1
                        external[seq]=[action]
                        interventions.append(dict(observation_seq=seq,action=action.to_dict(),
                                                  before=before.to_dict(),after=body.observe().to_dict()))
                verification=verify_world(folder/'world.sqlite',expected_config=cfg,expected_total_budget=24,
                    expected_world_id='persistent-world',expected_self_id='persistent-self',expected_goals=[(goal,24)],
                    expected_external_actions=external)
                with sqlite3.connect(folder/'world.sqlite') as db:
                    journal=[dict(seq=s,kind=k,payload=json.loads(v)) for s,k,v in db.execute('SELECT seq,kind,payload FROM events ORDER BY seq')]
                thoughts=list(map(json.loads,(folder/'thoughts.jsonl').read_text().splitlines()))
                thinks=[r for r in thoughts if r['kind']=='THINK'];revisions=[r for r in thoughts if r['kind']=='REVISE']
                assert sum(e['kind']=='GOAL' for e in journal)==1
                predicts=[e for e in journal if e['kind']=='PREDICT']
                assert [r['chosen'] for r in thinks if r['chosen'] is not None]==[e['payload']['action'] for e in predicts]
                continuity=all(a['final_model_digest']==b['initial_model_digest'] for a,b in zip(workers,workers[1:]))
                observed=all(any(e['seq']==i['observation_seq'] and e['kind']=='OBSERVE' and e['payload']['changed'] and e['payload']['frame']==i['after'] for e in journal) for i in interventions)
                row=dict(seed=seed,arm=arm,completed=workers[-1]['completed'],steps=workers[-1]['steps'],
                         workers=workers,continuity=continuity,observed_external=observed,verification=verification,
                         belief_revisions=sum(r['changed'] for r in revisions),
                         modes={mode:sum(r['decision_mode']==mode for r in thinks) for mode in ('model_supported','unknown_exploration','prediction_disabled')},
                         interventions=interventions)
                (folder/'journal.json').write_text(json.dumps(journal));(folder/'receipt.json').write_text(json.dumps(row,indent=2))
                results.append(row);print(json.dumps({k:row[k] for k in ('seed','arm','completed','steps','modes')}),flush=True)
    scores={a:sum(r['completed'] for r in results if r['arm']==a) for a in ('resumed','frozen','no_prediction')}
    full=[r for r in results if r['arm']=='resumed']
    gates=dict(native=all(r['verification']['green'] for r in results),
               continuity=all(r['continuity'] for r in results),
               three_restarts=all(len({w['pid'] for w in r['workers']})==4 for r in results),
               external_observed=all(r['observed_external'] for r in results),
               composite_goals=scores['resumed']==3,
               revision_contribution=scores['resumed']>scores['frozen'],
               prediction_contribution=scores['resumed']>scores['no_prediction'],
               learned_state_modes=all(r['modes']['model_supported']>0 and r['modes']['unknown_exploration']>0 for r in full))
    report=dict(verdict='BOUNDED_SUBJECT_LOOP_SUPPORTED' if all(gates.values()) else 'SUBJECT_LOOP_PARTIAL',
                gates=gates,scores=scores,results=results,
                scope='Three new filesystem instances; operator composite goal; authored bounded control rules; no learned metacontrol, no consciousness or hour-long autonomy claim')
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(verdict=report['verdict'],scores=scores,gates=gates)))

if __name__=='__main__':run(Path(sys.argv[1]))
