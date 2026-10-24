"""Offline learning curve for the H6 report (archived H6 TRAINING pages only, truth-labelled as the teacher did):
train the reader (span model + ranking + trust) on the first k training formats, test on the last 24, on
relevant pages (page mentions the extension and an accepted name). Does reading improve with more data?"""
import gzip
import json
from pathlib import Path
from atanor_os.agent.autonomy import norm
from atanor_os.agent.reader import NameReader
from atanor_os.eval.p6 import load_snapshot

snap = load_snapshot()
extra = json.load(open('atanor_os/results/p6-truth/train_extra.json', encoding='utf-8'))['formats']
names = lambda e: extra.get(e) or [snap['formats'][e]['label']] + snap['formats'][e]['aliases']
tl = json.load(open('atanor_os/results/h6-train/train_log.json', encoding='utf-8'))
exts = tl['teach_exts']
log = [json.loads(l) for l in open('atanor_os/results/h6-train/web/fetch_log.jsonl', encoding='utf-8')]
pages = {}
for r in log:
    if r.get('ok') and r['kind'] == 'page' and r['url'] not in pages:
        pages[r['url']] = json.loads(gzip.decompress(Path(f"atanor_os/results/h6-train/web/pages/{r['sha256']}.json.gz").read_bytes()))['text']
title = lambda u: u.rstrip('/').rsplit('/', 1)[-1].replace('_', ' ')
by_ext = {e: [(u, t) for u, t in pages.items() if e.lower() in t.lower() and any(n.lower() in t.lower() for n in names(e))] for e in exts}
test = exts[-24:]
print('relevant pages per test format (mean):', round(sum(len(by_ext[e]) for e in test) / len(test), 1))
for k in (12, 24, 48):
    rd = NameReader()
    for e in exts[:k]:
        ok = lambda n, e=e: norm(n) in {norm(x) for x in names(e)}
        for u, t in by_ext[e]:
            rd.spans.learn(t, e, [n for n in names(e) if n.lower() in t.lower()])
        for u, t in by_ext[e]:
            rd.train(t, e, title(u), ok, refit=False)
    rd.fit()
    present = first = total = 0
    for e in test:
        ok = lambda n, e=e: norm(n) in {norm(x) for x in names(e)}
        for u, t in by_ext[e]:
            total += 1
            cs = rd.all_candidates(t, e, title(u))
            present += any(ok(n) for n, _ in cs)
            b = rd.best(t, e, title(u))
            first += bool(b) and ok(b['name'])
    print(f'trained on {k:2d} formats: test relevant pages {total}, name among candidates {present} ({present / max(1, total):.2f}), ranked first {first} ({first / max(1, total):.2f})')
