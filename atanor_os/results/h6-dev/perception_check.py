"""Offline diagnosis for the H6 report (no learning, no threshold change): how much of the 'given the right
page' failure is perception? Same archived article texts, same frozen H6 reader; only the page text is
reduced to its paragraph lines (lines with >= 8 words), which removes navigation/menu boilerplate."""
import gzip
import json
from pathlib import Path
from atanor_os.agent.autonomy import norm
from atanor_os.eval.p6 import load_state

ref = json.load(open('atanor_os/results/h6-dev/reference.json', encoding='utf-8'))['formats']
lex, rd, _ = load_state('atanor_os/results/h6-train/state.json')
d = json.load(open('atanor_os/results/h6-dev/h6.json', encoding='utf-8'))
log = [json.loads(l) for l in open('atanor_os/results/h6-dev/web_h6/fetch_log.jsonl', encoding='utf-8')]
sha = {r['url']: r['sha256'] for r in log if r.get('ok') and r['kind'] == 'page'}
ok = lambda e, n: norm(n) in {norm(x) for x in ref[e]['names']}
rows = {'as_seen': [0, 0, 0], 'paragraphs_only': [0, 0, 0]}
first_lines = []
for e, v in d['per_format'].items():
    g = v.get('given_page')
    if not g or g['url'] not in sha:
        continue
    text = json.loads(gzip.decompress(Path(f"atanor_os/results/h6-dev/web_h6/pages/{sha[g['url']]}.json.gz").read_bytes()))['text']
    title = g['url'].rstrip('/').rsplit('/', 1)[-1].replace('_', ' ')
    para = '\n'.join(l for l in text.split('\n') if len(l.split()) >= 8)
    if len(first_lines) < 3:
        first_lines.append((e, text.split('\n')[:6]))
    for k, t in (('as_seen', text), ('paragraphs_only', para)):
        cs = rd.all_candidates(t, e, title)
        b = rd.best(t, e, title)
        rows[k][0] += any(ok(e, n) for n, _ in cs)
        rows[k][1] += bool(b) and ok(e, b['name'])
        rows[k][2] += bool(b) and ok(e, b['name']) and b['score'] > rd.threshold
n = sum(1 for v in d['per_format'].values() if v.get('given_page'))
for k, (c, f, t) in rows.items():
    print(f'{k:16s} of {n}: name among candidates {c}, ranked first {f}, trusted and first {t}')
print('first lines of extracted text (examples):')
for e, ls in first_lines:
    print('  ', e, [l[:40] for l in ls])
