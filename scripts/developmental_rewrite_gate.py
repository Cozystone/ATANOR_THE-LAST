"""New-instance prediction gate: learned index effects vs rooted exact contexts.

Four exposed native examples used as training, OLD192 experiences retained by
the baseline. Candidate falls back to baseline when its new algebra cannot
predict a whole state. No learned transfer/agency claim; grammar is authored.
"""
import hashlib,json,sys,tempfile
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.action_core.world import Sandbox,Action,Frame
from packages.shared_world.index_rewrite import IndexRewrite
from scripts.developmental_conditional_eval import Model
from scripts.developmental_continual_probe import score
from scripts.developmental_active_eval import event
from scripts.representation_r3_dev import configuration


def run(source,output,training_count=4,seed_base=105001):
    raw=source.read_bytes();examples=[r['native_record'] for r in json.loads(raw)['rows']][:training_count]
    if training_count not in (1,4):raise ValueError('registered training counts only')
    old=[]
    for name in ('developmental-continual.json','developmental-online-eval.json'):
        old+=json.loads((ROOT/'evidence'/name).read_text())['records']
    baseline=Model(old+examples);candidate=IndexRewrite(examples);rows=[]
    totals={arm:Counter() for arm in ('baseline','candidate')};complete=Counter()
    with tempfile.TemporaryDirectory(prefix='atanor_rewrite_gate_') as root:
        for ordinal in range(16):
            pattern='detached_absent' if ordinal%2==0 else 'independent_full'
            cfg,aliases,reference,payload=configuration(5+ordinal%3,seed_base+ordinal,pattern)
            cfg={**cfg,'operations':cfg['operations']+[{'id':'rename','arity':2}]}
            body=Sandbox(Path(root)/str(ordinal),**cfg);preparation=[]
            if ordinal%2:preparation.append(event(body,Action('unlink',(aliases[0],))))
            before=body.observe();action=Action('rename',(aliases[1],aliases[0]))
            predictions={'baseline':baseline.predict(before,action,True),'candidate':candidate.predict(before,action)}
            if any(len(v)!=1 for _,_,v in predictions['candidate']):predictions['candidate']=predictions['baseline']
            record=event(body,action);after=Frame.from_dict(record['after'])
            assert body._paths[reference].read_bytes()==payload
            counts={arm:score(prediction,after) for arm,prediction in predictions.items()}
            for arm,measured in counts.items():
                totals[arm].update(measured)
                complete[arm]+=measured.get('correct_singleton',0)==len(predictions[arm])
            rows.append({'ordinal':ordinal,'preparation':preparation,'record':record,'counts':counts})
    assert source.read_bytes()==raw
    passed=totals['candidate']['wrong']==0 and complete['candidate']>=complete['baseline']+4
    result={'verdict':'PREDICTION_GAIN' if passed else 'NO_PREDICTION_GAIN','complete':complete,'totals':totals,
            'training_count':training_count,'seed_base':seed_base,
            'source_sha256':hashlib.sha256(raw).hexdigest(),'rows':rows,
            'scope':'16 novel surfaces/scales, known new operation; no task capability, old-knowledge transfer, or agency'}
    with output.open('x') as stream:json.dump(result,stream,separators=(',',':'),sort_keys=True)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]),*(int(v) for v in sys.argv[3:]))
