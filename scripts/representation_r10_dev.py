"""One exposed feasibility execution; no task-capability/fresh claim."""
import json
from pathlib import Path
import random
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox
from packages.shared_world.relational import RelationalLearner
from packages.shared_world.intervention_synthesis import synthesize
from packages.shared_world.effect_hypotheses import inspect_effects
from scripts.representation_r1_dev import SCHEMA
from scripts.representation_r3_dev import configuration


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    rng = random.Random(119031)
    cfg, _, reference, payload = configuration(3,119031)
    records=[]; eliminated=0; stopped=None; cpu=time.process_time()
    with tempfile.TemporaryDirectory(prefix='atanor_r10_dev_') as root:
        body=Sandbox(Path(root)/'current',**cfg)
        model=RelationalLearner(schema=SCHEMA,partitioned=True)
        for step in range(32):
            before=body.observe(); snapshot=model.snapshot()
            proposal=None
            if step<6:
                action=rng.choice(body.actions())
            else:
                proposal=synthesize(model,before,body.actions(),remaining=32-step,cpu_deadline=cpu+120)
                if proposal['status']!='PROPOSED':
                    stopped=proposal; break
                action=proposal['sequence'][0]
            assert model.snapshot()==snapshot
            pre=inspect_effects(model,before,action)
            prediction=model.predict(before,[action])[0][0]
            success=body.step(action); after=body.observe()
            model.learn(step,before,action,after)
            post=inspect_effects(model,before,action)
            old={(c['field'],tuple(c['address'])):set(c['possible_values']) for c in pre.get('disagreement_cells',[])}
            new={(c['field'],tuple(c['address'])):set(c['possible_values']) for c in post.get('disagreement_cells',[])}
            resolved=bool(old) and post['status']=='FINITE_SET_AGREEMENT'
            if proposal and len(proposal['sequence'])==1 and resolved: eliminated+=1
            if proposal:proposal={**proposal,'sequence':[a.to_dict() for a in proposal['sequence']]}
            records.append({'step':step,'phase':'bootstrap' if step<6 else 'synthesis',
                'before':before.to_dict(),'action':action.to_dict(),'prediction':prediction.to_dict(),
                'after':after.to_dict(),'success':success,'proposal':proposal,
                'pre_hypotheses':pre,'post_hypotheses':post,'resolved':resolved})
            assert body._paths[reference].read_bytes()==payload
        report={'status':'DEV_WITNESS_REQUIRES_AUDIT' if eliminated else 'DEV_NO_WITNESS',
                'capability_claim':False,'eliminated_candidates':eliminated,'actions':len(records),
                'cpu_seconds':time.process_time()-cpu,'stop':stopped,'records':records,'snapshot':model.snapshot()}
    with (output/'report.json').open('x') as stream:json.dump(report,stream,sort_keys=True,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k not in ('records','snapshot')}))


if __name__=='__main__':run(Path(sys.argv[1]))
