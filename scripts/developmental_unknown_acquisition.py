"""Frozen small DEV comparison: missing support vs disagreement vs random.

Two continuous native bodies seeds117001/117002,count4/5, mixed linked and one
independent equal-content object. Same195 retained events, same8-action allowance.
No body reset/menu/goal during acquisition. Missing-support arm lexicographically
maximizes unknown then disagreeing cell counts; disagreement arm uses latter only;
ties uniform with same seed. Random samples same whole permitted action surface.
Only actual native outcomes enter learner; no answer-specific action preference.
Exposed sealed frontier36 records measure post-learning prediction usefulness;
sealed contextual12 measure retained new skill. They never train acquisition.
GO only if missing wins >=4 complete predictions vs BOTH other arms and initial,
with no extra wrong cells or retention loss relative to initial. DEV, not fresh
capability;120s cap. No sweep/retry. All48 native acquisition actions charged.
"""
import json,sys,tempfile,random,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox,Frame,Action
from scripts.developmental_lookahead_probe import adapter
from scripts.representation_r3_dev import configuration
from scripts.developmental_active_eval import event
from scripts.developmental_continual_probe import score


def measure(model,records):
    full=wrong=0
    for record in records:
        prediction=model.predict_cells(Frame.from_dict(record['before']),Action.from_dict(record['action']))
        counts=score(prediction,Frame.from_dict(record['after']))
        full+=counts.get('correct_singleton',0)==len(prediction);wrong+=counts.get('wrong',0)
    return {'complete':full,'wrong':wrong,'total':len(records)}


def run(output):
    output.mkdir(exist_ok=False);start=time.monotonic();old=[];rows=[]
    for name in ('developmental-continual.json','developmental-online-eval.json'):
        old+=json.loads((ROOT/'evidence'/name).read_text())['records']
    examples=[json.loads((ROOT/'evidence/developmental-composition-probe.json').read_text())['rows'][0]['native_record']]
    examples += [r['record'] for r in json.loads((ROOT/'evidence/developmental-rewrite-scope.json').read_text())['rows'] if r['case'] in ('declared_absent','declared_present')]
    frontier=[r['record'] for r in json.loads((ROOT/'evidence/developmental-frontier-audit.json').read_text())['rows']]
    retained=[r['record'] for r in json.loads((ROOT/'evidence/developmental-contextual-v1/report.json').read_text())['rows']]
    with tempfile.TemporaryDirectory(prefix='atanor_unknown_dev_') as root:
        for life in range(2):
            cfg,aliases,ref,payload=configuration(4+life,117001+life)
            cfg={**cfg,'initial':dict(cfg['initial']),'initial_links':dict(cfg['initial_links']),
                'operations':cfg['operations']+[{'id':'rename','arity':2}]}
            separate=cfg['paths'][int(aliases[-1][1:])]
            cfg['initial_links'].pop(separate);cfg['initial'][separate]=payload
            initial=adapter(old,examples,cfg['operations'])
            initial_scores={'frontier':measure(initial,frontier),'retained':measure(initial,retained),
                            'old':measure(initial,old)}
            for arm in ('missing','disagreement','random'):
                body=Sandbox(Path(root)/f'{life}_{arm}',**cfg);history=list(examples);trace=[];rng=random.Random(117001+life)
                model=adapter(old,history,cfg['operations']);cpu=time.process_time()
                for step in range(8):
                    if time.monotonic()-start>120:raise TimeoutError('registered120s cap')
                    before=body.observe();actions=body.actions();rank=[]
                    for action in actions:
                        cells=model.predict_cells(before,action)
                        rank.append((sum(not v for _,_,v in cells),sum(len(v)>1 for _,_,v in cells)))
                    scores=rank if arm=='missing' else [(0,r[1]) for r in rank] if arm=='disagreement' else [(0,0)]*len(actions)
                    best=max(scores);index=rng.choice([i for i,s in enumerate(scores) if s==best]);action=actions[index]
                    record=event(body,action);history.append(record)
                    trace.append({**record,'unknown_cells':rank[index][0],'disagreement_cells':rank[index][1]})
                    assert body._paths[ref].read_bytes()==payload
                    model=adapter(old,history,cfg['operations'])
                rows.append({'life':life,'arm':arm,'trace':trace,'cpu_seconds':time.process_time()-cpu,
                    'initial':initial_scores,'frontier':measure(model,frontier),'retained':measure(model,retained),'old':measure(model,old)})
    summary={arm:{'complete':sum(r['frontier']['complete'] for r in rows if r['arm']==arm),
        'wrong':sum(r['frontier']['wrong'] for r in rows if r['arm']==arm),
        'retained':sum(r['retained']['complete'] for r in rows if r['arm']==arm),
        'actions':sum(len(r['trace']) for r in rows if r['arm']==arm)} for arm in ('missing','disagreement','random')}
    clean=all(r['frontier']['wrong']<=r['initial']['frontier']['wrong'] and r['retained']['wrong']<=r['initial']['retained']['wrong']
        and r['old']['wrong']<=r['initial']['old']['wrong'] and r['retained']['complete']>=r['initial']['retained']['complete'] for r in rows if r['arm']=='missing')
    initial_full=sum(r['initial']['frontier']['complete'] for r in rows if r['arm']=='missing')
    passed=clean and all(summary['missing']['complete']>=x+4 for x in (summary['random']['complete'],summary['disagreement']['complete'],initial_full))
    result={'verdict':'DEV_ACQUISITION_GAIN' if passed else 'NO_DEV_ACQUISITION_GAIN','summary':summary,'clean':clean,'rows':rows,
            'scope':'exposed prediction probes, not fresh task capability or autonomous developmental agenda'}
    (output/'report.json').write_text(json.dumps(result,sort_keys=True,separators=(',',':')))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':run(Path(sys.argv[1]))
