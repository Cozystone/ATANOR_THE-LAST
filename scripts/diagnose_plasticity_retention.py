"""Post-hoc paired accounting, no extra learner run and no replacement gate."""
import collections
import json
from pathlib import Path
import sys


def run(out):
    cases={r['id']:r['data'] for r in map(json.loads,(out/'cases.jsonl').read_text().splitlines())}
    rows=list(map(json.loads,(out/'probes.jsonl').read_text().splitlines()))
    before={(r['law'],r['life'],r['probe']):r for r in rows if r['arm']=='weights_adam' and r['count']==0 and r['law'] not in ('null','cascade')}
    totals=collections.Counter();laws=collections.defaultdict(collections.Counter)
    for r in rows:
        if r['arm']!='weights_adam' or r['count']!=16 or r['law'] in ('null','cascade'):continue
        old=before[(r['law'],r['life'],r['probe'])];c=cases[r['case_id']]
        for i in c['common']:
            truth=c['new'][i]['after']['kinds']
            x=old['predictions'][i]==truth;y=r['predictions'][i]==truth
            label=('kept' if y else 'lost') if x else ('gained' if y else 'never_correct')
            totals[label]+=1;laws[r['law']][label]+=1
    result=dict(status='POST_HOC_PAIRED_RETENTION_ONLY',totals=totals,laws=laws,
                interpretation='Counts of matched probe transitions, not distinct learned concepts. Already-incorrect cases not counted as forgetting. No task regression or production damage inferred.')
    with (out/'retention_diagnosis.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))


if __name__=='__main__':run(Path(sys.argv[1]))
