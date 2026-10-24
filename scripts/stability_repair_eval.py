"""Single exposed-cohort repair trial; never a replacement for sealed panel."""
import json
import statistics
import time
from pathlib import Path
import sys
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.stable_plastic_world import StablePlasticWorld
from scripts.developmental_plastic_world import PlasticWorld
from scripts.developmental_plasticity_eval import COUNTS,NEW_LAWS,evaluate_gates
from scripts.adaptation_pair_isolation import compose,digest


def run(out):
    out.mkdir(exist_ok=False)
    source=ROOT/'evidence/developmental-plasticity-panel-v1'
    files=[Path(__file__),ROOT/'scripts/stable_plastic_world.py',ROOT/'scripts/developmental_plastic_world.py',
           ROOT/'docs/ATANOR_STABILITY_REPAIR_V1_PREREGISTRATION.md',source/'probes.jsonl',source/'cases.jsonl',source/'events.jsonl']
    files += [source/f'A-{i}.pt' for i in range(8)]
    hashes={str(p):digest(p) for p in files}
    (out/'attempt.json').write_text(json.dumps(hashes))
    start=time.monotonic()
    reference=[json.loads(s) for s in (source/'probes.jsonl').read_text().splitlines()]
    cases={r['id']:r['data'] for r in map(json.loads,(source/'cases.jsonl').read_text().splitlines())}
    events=[json.loads(s) for s in (source/'events.jsonl').read_text().splitlines()]
    rows=[];baseline_equal=0;restart_equal=0
    for life in range(8):
        state=torch.load(source/f'A-{life}.pt',weights_only=True)
        for law in NEW_LAWS:
            model=StablePlasticWorld.from_life(state)
            baseline=PlasticWorld.restore(compose(state)['weights_adam'])
            teacher_before=[{k:v.clone() for k,v in m.state_dict().items()} for m in model.teachers]
            for count in range(17):
                if time.monotonic()-start>1200:raise TimeoutError('hard cap; no retry')
                if count in COUNTS:
                    saved=model.checkpoint();torch.save(saved,out/f'{law}-{life}-{count}.pt')
                    for ref in reference:
                        if (ref['law'],ref['life'],ref['arm'],ref['count'])!=(law,life,'weights_adam',count):continue
                        c=cases[ref['case_id']]
                        probe=PlasticWorld.restore(saved);probe.enter_body(c['n'])
                        p=probe.forecasts(c['before'],c['actions'])[0]
                        reload=PlasticWorld.restore(torch.load(out/f'{law}-{life}-{count}.pt',weights_only=True));reload.enter_body(c['n'])
                        assert torch.equal(p,reload.forecasts(c['before'],c['actions'])[0]);restart_equal+=1
                        pred=p.argmax(-1).tolist();idx=c['primary']
                        baseline.enter_body(c['n']);bp=baseline.forecasts(c['before'],c['actions'])[0]
                        assert bp.argmax(-1).tolist()==ref['predictions'],'baseline mismatch';baseline_equal+=1
                        row=dict(ref,predictions=pred,primary_probabilities=p[idx].tolist(),
                            whole_exact=pred[idx]==c['new'][idx]['after']['kinds'],
                            changed_exact=all(pred[idx][i]==c['new'][idx]['after']['kinds'][i] for i in c['changed']),
                            common_correct=sum(pred[i]==c['new'][i]['after']['kinds'] for i in c['common']))
                        rows.append(row)
                        with (out/'probes.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
                if count==16:break
                event=next(e for e in events if (e['law'],e['life'],e['ordinal'])==(law,life,count+1))
                c=cases[event['case_id']];idx=c['primary']
                for m in (model,baseline):m.enter_body(c['n']);m.learn(c['before'],c['actions'][idx],c['new'][idx]['after'])
            assert all(torch.equal(v,teacher_before[i][k]) for i,m in enumerate(model.teachers) for k,v in m.state_dict().items())
        print(json.dumps(dict(life=life,seconds=time.monotonic()-start)),flush=True)
    fresh=[r for r in reference if r['arm']=='fresh' and r['law'] in NEW_LAWS]
    metrics=evaluate_gates(rows+fresh)
    retention=metrics['retention'];before=statistics.mean(v[0] for v in retention.values());after=statistics.mean(v[16] for v in retention.values())
    repair=dict(cost_at_most_six=metrics['means']['weights_adam']<=6,
                macro_preserved=after>=before-.02,each_preserved=all(v[16]>=v[0]-.05 for v in retention.values()),
                negative_transfer=metrics['gates']['severe_pairs'] and metrics['gates']['no_severe_law'])
    assert all(digest(Path(p))==h for p,h in hashes.items())
    report=dict(verdict='REPAIR_SIGNAL_ONLY' if all(repair.values()) else 'REPAIR_NO_GO',repair_gates=repair,
                original_panel_gates=metrics,baseline_exact_rows=baseline_equal,restart_exact_rows=restart_equal,
                retention_before=before,retention_after=after,source_hashes=hashes,seconds=time.monotonic()-start,
                scope='Exposed diagnostic; no fresh validation; prediction checkpoints only, not resumable teacher checkpoint')
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':run(Path(sys.argv[1]))
