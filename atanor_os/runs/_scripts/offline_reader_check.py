"""Teacher-supervised offline dev check of the name reader on archived TRAINING pages (no web traffic):
fit on half of the training formats, measure two-page agreement on the other half."""
import json, gzip, sys
from pathlib import Path
from atanor_os.agent.reader import NameReader
from atanor_os.agent.autonomy import norm
from atanor_os.eval.p6 import load_snapshot
from atanor_os.eval.web_truth import accepts
snap = load_snapshot(); ex = json.load(open('atanor_os/results/p6-truth/train_extra.json', encoding='utf-8'))['formats']
tl = json.load(open('atanor_os/results/p6-train/train_log.json', encoding='utf-8'))
def ok(e, n): return norm(n) in {norm(l) for l in ex[e]} if e in ex else accepts(snap, e, n)
rows = [json.loads(l) for l in open('atanor_os/results/p6-train/web/fetch_log.jsonl', encoding='utf-8')]
pages = {r['url']: json.loads(gzip.decompress(Path(f"atanor_os/results/p6-train/web/pages/{r['sha256']}.json.gz").read_bytes()))['text'] for r in rows if r['kind'] == 'page' and r.get('ok')}
exts = tl['teach_exts']; title = lambda u: u.rsplit('/', 1)[-1].replace('_', ' ')
res = []
for fold in (0, 1):
    A = exts[fold::2]; Bx = exts[1 - fold::2]
    r = NameReader()
    for e in A:
        for u, t in pages.items():
            if e.lower() in t.lower(): r.train(t, e, title(u), lambda n, e=e: ok(e, n), refit=False)
    r.fit()
    for th in (-1.0, 0.0, 1.0):
        good = bad = none = 0
        for e in Bx:
            c = {}
            for u, t in pages.items():
                if e.lower() in t.lower():
                    b = r.best(t, e, title(u))
                    if b and b['score'] > th: c.setdefault(norm(b['name']), []).append((u, b['name']))
            agreed = [v for v in c.values() if len({u for u, _ in v}) >= 2]
            if not agreed: none += 1
            else:
                v = max(agreed, key=len); good += ok(e, v[0][1]); bad += not ok(e, v[0][1])
        res.append((fold, th, good, bad, none, len(Bx)))
for x in res: print('fold %d threshold %.1f: correct %d wrong %d none %d of %d' % x)
