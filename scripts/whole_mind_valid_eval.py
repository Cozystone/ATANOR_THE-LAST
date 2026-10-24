"""Evaluator-only native reachability, external event replay, and fixed trial.

Not imported by cognition or worker. No solution sequence is saved or supplied.
"""
import hashlib
import itertools
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from collections import deque
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox,Action
from packages.action_core.episode import digest,encode_config
from packages.action_core.planner import Goal
from packages.shared_world import runtime

SCHEMA=[dict(id=x,arity=1) for x in ('mkdir','empty','unlink')]
INITIAL=(1,1,0,0,1,1,0,0);TARGET=(2,0,1,2,2,0,1,2)
MANIFEST=b'ATANOR validation manifest: preserve exactly.\n'
FROZEN=('scripts/whole_mind_bridge.py','packages/shared_world/runtime.py',
        'packages/shared_world/historical_goal_world.py','packages/action_core/world.py',
        'packages/action_core/planner.py','packages/action_core/schema.py',
        'packages/shared_world/contracts.py','packages/action_core/episode.py')

def hashes():
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FROZEN}

def frozen_equal():
    return all(subprocess.run(['git','diff','--quiet','a890256','--',p],cwd=ROOT).returncode==0 for p in FROZEN)

def fixture():
    paths=['entry'+str(i) for i in range(8)]+['manifest']
    initial={paths[i]:b'owned input '+str(i).encode() for i,k in enumerate(INITIAL) if k==1}
    initial['manifest']=MANIFEST
    return dict(paths=paths,initial=initial,protected=['n8'],operations=SCHEMA)

def force_file(body):
    # Evaluator-only event: exact authorized n7, never a user-controlled path.
    root=body.root.resolve();p=body._paths['n7']
    if p.parent.resolve()!=root or not root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise ValueError('external event escaped owned temporary body')
    if p.is_symlink():raise ValueError('external event symlink')
    if p.is_dir():p.rmdir()  # Empty single directory only, never recursive.
    p.write_bytes(b'external peer update\n')
    return True

class ExternalFileEvent:
    """Not an Action; impossible to submit through frozen learner contract."""

class ReplayBody(Sandbox):
    def step(self, action):
        if type(action) is ExternalFileEvent:return force_file(self)
        return super().step(action)  # all ATANOR actions use frozen native code

def transitions():
    table={};checks=[]
    with tempfile.TemporaryDirectory(prefix='atanor_preflight_') as tmp:
        for kind,op in itertools.product(range(3),[x['id'] for x in SCHEMA]):
            init={} if kind==0 else {'slot':b'x' if kind==1 else None}
            b=Sandbox(Path(tmp)/(str(kind)+'_'+op),paths=['slot','manifest'],
                      initial={**init,'manifest':MANIFEST},protected=['n1'],operations=SCHEMA)
            success=b.step(Action(op,('n0',)));out=b.observe().kinds[0]
            assert b.evidence()['n1']['sha256']==hashlib.sha256(MANIFEST).hexdigest()
            assert all('n1' not in a.args for a in b.actions())
            table[(kind,op)]=out;checks.append(dict(kind=kind,op=op,result=out,success=success))
    return table,checks

def successors(state,table):
    for i in range(8):
        for r in SCHEMA:
            v=table[(state[i],r['id'])]
            if v!=state[i]:yield state[:i]+(v,)+state[i+1:]

def search(start,table):
    # BFS of actual measured primitive effects on a flat shadow state.
    q=deque([(tuple(start),0)]);seen={tuple(start)}
    while q:
        state,n=q.popleft()
        if state==TARGET:return n
        for nxt in successors(state,table):
            if nxt not in seen:seen.add(nxt);q.append((nxt,n+1))
    return None

def distance(state,table):
    # Independent per-locator lower bound is exact for this flat unary body.
    total=0
    for s,t in zip(state,TARGET):
        q=deque([(s,0)]);seen={s};found=None
        while q:
            k,n=q.popleft()
            if k==t:found=n;break
            for op in (r['id'] for r in SCHEMA):
                v=table[k,op]
                if v not in seen:seen.add(v);q.append((v,n+1))
        if found is None:return None
        total+=found
    return total

def preflight(out):
    out=Path(out);out.mkdir(exist_ok=False)
    assert frozen_equal()
    table,checks=transitions();nominal=search(INITIAL,table)
    assert nominal is not None and nominal==distance(INITIAL,table) and nominal<=32
    # Enumerate all possible prefixes, not the candidate's decisions. Thus no
    # capability run is hidden inside preflight. Self-created dead ends are
    # classified separately from damage caused by the fixed external event.
    states={INITIAL}
    for _ in range(5):states|={n for s in states for n in successors(s,table)}
    safe=[];dead=0
    for s in states:
        post=s[:7]+(1,)
        before_cost=distance(s,table);after_cost=distance(post,table)
        if before_cost is not None:
            assert after_cost is not None
            safe.append(after_cost)
        else:dead+=1
    baseline_post=INITIAL[:7]+(1,)
    assert search(baseline_post,table)==distance(baseline_post,table)
    total=max(nominal,5+max(safe));cap=max(32,2*total);assert cap<=64
    first=dict(reachable=True,minimum_or_verified_action_count=nominal,
        action_set_hash=digest(SCHEMA),initial_state_hash=digest(INITIAL),goal_hash=digest(TARGET),
        frozen_hashes=hashes(),native_transition_checks=checks,protected_manifest_verified=True,cap=cap)
    second=dict(reachable=True,baseline_post_minimum=search(baseline_post,table),
        all_prefix_states_checked=len(states),solvable_prefix_states=len(safe),
        agent_created_dead_end_states=dead,max_post_disturbance_recovery=max(safe),
        verified_reachable_total_length=total,cap=cap,
        theorem='For every still-solvable five-action prefix, forcing n7 to FILE preserves reachability. Exact realized state is also checked before mutation. Agent-created irreversible directories elsewhere remain capability failures, not fixture repair permission.')
    (out/'PREFLIGHT.json').write_text(json.dumps(first,indent=2));(out/'DISTURBANCE_PREFLIGHT.json').write_text(json.dumps(second,indent=2))
    print(json.dumps(dict(nominal=nominal,cap=cap,prefix_states=len(states),worst_recovery=max(safe))))

def native_state(body):
    e=body.evidence();return dict(evidence=e,conditions=[e['n'+str(i)]['kind']==k for i,k in enumerate(TARGET)],
        manifest_unchanged=e['n8']['sha256']==hashlib.sha256(MANIFEST).hexdigest())

def trial(out):
    out=Path(out);pre=json.loads((out/'PREFLIGHT.json').read_text());cap=pre['cap']
    assert frozen_equal() and hashes()==pre['frozen_hashes']
    (out/'TRIAL_STARTED').open('x').close()  # fail closed on any attempted retry
    cfg=fixture();goal=Goal('reconfigure-workspace',kinds=tuple(('n'+str(i),k) for i,k in enumerate(TARGET)))
    root=Path(tempfile.mkdtemp(prefix='atanor_whole_mind_valid_'));results={}
    table={(r['kind'],r['op']):r['result'] for r in pre['native_transition_checks']}
    for arm in ('full','no_memory','no_planning'):
        folder=out/arm;folder.mkdir()
        intent=dict(config=encode_config(cfg),body_root=str(root/arm),arm=arm,goal=goal.to_dict(),cap=cap)
        (folder/'intent.json').write_text(json.dumps(intent,indent=2))
        cmd=[sys.executable,str(ROOT/'scripts/whole_mind_valid_worker.py'),str(folder),digest(intent)]
        p=subprocess.Popen(cmd+['first'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        ready=json.loads(p.stdout.readline());assert ready['ready'] and ready['steps']==5
        body=Sandbox.attach(root/arm,**{k:v for k,v in cfg.items() if k!='initial'})
        before=body.observe();post=tuple(before.kinds[:7])+(1,)
        recovery=search(post,table)
        assert recovery==distance(post,table)
        with sqlite3.connect(folder/'world.sqlite') as db:seq=db.execute('SELECT MAX(seq) FROM events').fetchone()[0]+1
        force_file(body);after=body.observe()
        intervention=dict(observation_seq=seq,kind='EXTERNAL_OS_EVENT',target='n7',forced_kind=1,
            before=before.to_dict(),after=after.to_dict(),exact_post_reachable=recovery is not None,
            exact_post_minimum=recovery,agent_dead_end_before=distance(tuple(before.kinds[:8]),table) is None,
            learner_action=False)
        (folder/'intervention.json').write_text(json.dumps(intervention,indent=2))
        stdout,stderr=p.communicate('external-event-done\n',timeout=180)
        (folder/'first_worker_stderr.txt').write_text(stderr)
        if p.returncode:raise RuntimeError(stderr)
        first=json.loads(stdout)
        q=subprocess.run(cmd+['resume'],capture_output=True,text=True,timeout=180)
        (folder/'resume_worker_stderr.txt').write_text(q.stderr)
        if q.returncode:raise RuntimeError(q.stderr)
        last=json.loads(q.stdout)
        # Frozen verifier, evaluator-local external-event driver. Candidate never
        # imports this module or receives the extra event type/action authority.
        with patch.object(runtime,'Sandbox',ReplayBody):
            verified=runtime.verify_world(folder/'world.sqlite',expected_config=cfg,expected_total_budget=cap,
                expected_world_id='whole-mind-world-valid',expected_self_id='whole-mind-self-valid',
                expected_goals=[(goal,cap)],expected_external_actions={seq:[ExternalFileEvent()]})
        final=native_state(body);(folder/'final_native_state.json').write_text(json.dumps(final,indent=2))
        with sqlite3.connect(folder/'world.sqlite') as db:
            events=[dict(seq=s,kind=k,payload=json.loads(v)) for s,k,v in db.execute('SELECT seq,kind,payload FROM events ORDER BY seq')]
            checkpoint=json.loads(db.execute('SELECT payload FROM state').fetchone()[0])
        (folder/'journal.json').write_text(json.dumps(events,indent=2))
        thoughts=[json.loads(s) for s in (folder/'thoughts.jsonl').read_text().splitlines()]
        predictions=[e for e in events if e['kind']=='PREDICT'];outcomes=[e for e in events if e['kind']=='RESULT']
        b=json.loads((folder/'preview_before.json').read_text());a=json.loads((folder/'preview_after.json').read_text())
        learned_rows=[r for r in checkpoint['model']['records']]
        actual_rows=[]
        prior_frame=events[0]['payload']['frame']
        pending=None
        for e in events:
            if e['kind']=='OBSERVE':prior_frame=e['payload']['frame']
            elif e['kind']=='PREDICT':pending=(prior_frame,e['payload']['action'])
            elif e['kind']=='RESULT':
                actual_rows.append(dict(before=pending[0],action=pending[1],after=e['payload']['frame']))
                prior_frame=e['payload']['frame']
        causal=[]
        # Read-only paired decisions on recorded states. No native actions, no
        # future data: rebuild only the record prefix available at each decision.
        if arm=='full':
            from scripts.whole_mind_bridge import WholeMindClient
            for t in thoughts:
                rev=t['revision'];prefix=actual_rows[:rev];choices={}
                for mode in ('full','no_memory','no_planning'):
                    c=WholeMindClient([],SCHEMA,mode)
                    c.restore(dict(revision=rev,records=prefix,events={str(i):r for i,r in enumerate(prefix)},arm=mode))
                    frame=runtime.Frame.from_dict(t['before'])
                    reply=c.choose(frame,goal,body.actions(),[])
                    choices[mode]=None if reply is None else reply[0].to_dict()
                assert choices['full']==t['chosen']
                if choices['full']!=choices['no_memory'] or choices['full']!=choices['no_planning']:
                    causal.append(dict(revision=rev,choices=choices))
        first_dead_end=next((dict(action_index=i+1,action=r['action'],before=r['before']['kinds'],after=r['after']['kinds'])
                            for i,r in enumerate(actual_rows) if distance(tuple(r['after']['kinds'][:8]),table) is None),None)
        row=dict(completed=last['completed'],steps=last['steps'],workers=[first,last],
            noops=sum(r['before']==r['after'] for r in actual_rows),
            failed_actions=sum(not e['payload']['succeeded'] for e in outcomes),first_irreversible_dead_end=first_dead_end,
            verified=verified,native_final=final,continuity=first['final_model_digest']==last['initial_model_digest'],
            distinct_processes=first['pid']!=last['pid'],one_goal=sum(e['kind']=='GOAL' for e in events)==1,
            exact_post_reachable=recovery is not None,
            reobserved=a['canonical_frame']==after.to_dict() and a['canonical_frame']['kinds'][7]==1,
            preview_pure=all(v['model_digest_before']==v['model_digest_after'] for v in (a,b)),
            proposal_changed=b['action']!=a['action'],
            post_change_cognition=next((t['before'] for t in thoughts if t['revision']==5),None)==after.to_dict(),
            experiences_native_only=learned_rows==actual_rows,
            experience_retrieved=any(t['revision']>0 and any(v is not None for _,v in t['retrieved_edges']) for t in thoughts),
            thought_dispatch=[t['chosen'] for t in thoughts]==[e['payload']['action'] for e in predictions],
            causal_readonly_choices=causal)
        (folder/'receipt.json').write_text(json.dumps(row,indent=2));results[arm]=row
        print(json.dumps(dict(arm=arm,completed=row['completed'],steps=row['steps'],noops=row['noops'],native=verified['green'])),flush=True)
    source_unchanged=hashes()==pre['frozen_hashes'] and frozen_equal()
    f=results['full'];structural=all((source_unchanged,f['verified']['green'],f['continuity'],f['distinct_processes'],f['one_goal'],
        f['reobserved'],f['preview_pure'],f['post_change_cognition'],f['experiences_native_only'],f['thought_dispatch']))
    success=f['completed']==1 and all(f['native_final']['conditions']) and f['native_final']['manifest_unchanged']
    causal=bool(f['causal_readonly_choices']) and f['experience_retrieved']
    valid=structural and all(r['verified']['green'] and r['preview_pure'] for r in results.values())
    verdict=('INVALID_EXPERIMENT_AGAIN' if not valid else 'ATANOR_WHOLE_MIND_V0_INTEGRATED' if success and causal else 'WHOLE_MIND_V0_VALID_CAPABILITY_FAIL')
    status=dict(verdict=verdict,source_unchanged=source_unchanged,hashes_after=hashes(),structural=structural,
        full_success=success,causal_choices_observed=causal,cap=cap,
        results={a:{k:r[k] for k in ('completed','steps','noops','exact_post_reachable')} for a,r in results.items()},
        scope='One flat native filesystem mission only; no AGI, consciousness, general digital competence or all-organ claim',owned_root=str(root))
    (out/'FINAL_STATUS.json').write_text(json.dumps(status,indent=2));print(json.dumps(status))

if __name__=='__main__':
    (preflight if sys.argv[1]=='preflight' else trial)(Path(sys.argv[2]))
