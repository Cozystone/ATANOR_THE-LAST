"""Verdict regression: the generalized verdict() must reproduce the frozen v1-v3 results exactly, and the
report must render with the new agreement table code."""
import json
from pathlib import Path
from atanor_os.eval import metrics
from atanor_os.eval.run import read_jsonl, source_identity

for res in ('p1-test-03-contrast', 'p1-test-03-scarce', 'p1-test-02', 'p1-test-01'):
    d = Path('atanor_os/results') / res
    if not (d / 'metrics.json').exists():
        print(res, 'no metrics.json'); continue
    m = json.loads((d / 'metrics.json').read_text(encoding='utf-8'))
    recs = read_jsonl(d / 'records.jsonl')
    s = metrics.summarize(recs, m['protocol'], m['checks'], m.get('learn_cost_s'), m.get('env'), m.get('storage'))
    same_pairs = all(abs(s['paired'][k]['mean_pp'] - m['paired'][k]['mean_pp']) < 1e-9 for k in m['paired'])
    print(f"{res}: stored={m['verdict']} recomputed={s['verdict']} pairs_same={same_pairs} "
          f"C-B={s['paired'].get('C-B', {}).get('mean_pp')}")
    rep = metrics.report(s)
    assert '학습 비용' in rep
print('report renders; agreement rows in last:', len(metrics.agreement_rows(s)))
print('working-tree source identity:', source_identity())
