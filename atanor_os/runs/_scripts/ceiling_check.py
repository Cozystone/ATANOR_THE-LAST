"""Reading ceiling on archived TRAINING pages: for how many training formats is an accepted name a candidate
(either generator) on >= 2 pages / exactly 1 page."""
import json, gzip
from pathlib import Path
from atanor_os.agent.reader import candidates, definitional
from atanor_os.agent.autonomy import norm
from atanor_os.eval.p6 import load_snapshot
from atanor_os.eval.web_truth import accepts
snap = load_snapshot(); ex = json.load(open('atanor_os/results/p6-truth/train_extra.json', encoding='utf-8'))['formats']
tl = json.load(open('atanor_os/results/p6-train/train_log.json', encoding='utf-8'))
def ok(e, n): return norm(n) in {norm(l) for l in ex[e]} if e in ex else accepts(snap, e, n)
rows = [json.loads(l) for l in open('atanor_os/results/p6-train/web/fetch_log.jsonl', encoding='utf-8')]
pages = {r['url']: json.loads(gzip.decompress(Path(f"atanor_os/results/p6-train/web/pages/{r['sha256']}.json.gz").read_bytes()))['text'] for r in rows if r['kind'] == 'page' and r.get('ok')}
c2 = c1 = 0
for e in tl['teach_exts']:
    n = 0
    for u, t in pages.items():
        if e.lower() not in t.lower():
            continue
        ti = u.rsplit('/', 1)[-1].replace('_', ' ')
        n += any(ok(e, nm) for nm, _ in candidates(t, e, ti) + definitional(t, e, ti))
    c2 += n >= 2
    c1 += n == 1
print('ceiling with both generators: >=2 pages', c2, '| exactly 1', c1, 'of', len(tl['teach_exts']))
