"""P6 evaluator truth: official names of file formats, from a Wikidata snapshot. Never imported by agent/.

Source: the Wikidata Query Service (the Wikimedia service for programs; queried with an identifying
User-Agent, once, at snapshot time). Candidates: items with a file extension (P1195), an instance of
one of CLASSES, an English Wikipedia article, and an English label. Kept only when the extension is
unambiguous across ALL of Wikidata (exactly one item carries it) and the label is usable as a folder
or file name. The judge accepts the English label or any English alias (normalized), so a name ATANOR
finds in a different but recognised form still counts.
"""
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = 'ATANOR-research-bot/0.1 (evaluator truth snapshot; https://github.com/Cozystone/ATANOR_THE-LAST)'
CLASSES = {'Q105599390': 'raster-graphics file format', 'Q1572121': 'image file format', 'Q682626': 'audio file format',
           'Q18359031': 'video file format', 'Q336705': 'document file format', 'Q24451526': 'data serialization format',
           'Q55281818': 'font file format', 'Q105599400': 'vector graphics file format'}
SPARQL = 'https://query.wikidata.org/sparql'


def _query(q):
    u = SPARQL + '?' + urllib.parse.urlencode({'query': q, 'format': 'json'})
    with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': UA}), timeout=180) as r:
        return json.loads(r.read())['results']['bindings']


def norm(s):
    return re.sub(r'[^0-9a-z]+', '', s.casefold())


def build_snapshot(out):
    vals = ' '.join(f'wd:{c}' for c in CLASSES)
    rows = _query(f'''SELECT ?item ?ext ?label ?cls WHERE {{
      VALUES ?cls {{ {vals} }} ?item wdt:P31 ?cls; wdt:P1195 ?ext; rdfs:label ?label.
      FILTER(LANG(?label) = "en") ?art schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>. }}''')
    cand = {}
    for b in rows:
        ext = b['ext']['value'].strip().lstrip('.').lower()
        if not re.fullmatch(r'[a-z0-9]{1,8}', ext):
            continue
        item = b['item']['value'].rsplit('/', 1)[1]
        cand.setdefault(ext, {}).setdefault(item, {'label': b['label']['value'], 'classes': set()})['classes'].add(b['cls']['value'].rsplit('/', 1)[1])
    time.sleep(2)
    # ambiguity across all of Wikidata (any item, any class)
    exts = sorted(cand)
    counts = {}
    for i in range(0, len(exts), 150):
        chunk = ' '.join(json.dumps(e) for e in exts[i:i + 150]) + ' ' + ' '.join(json.dumps('.' + e) for e in exts[i:i + 150])
        for b in _query(f'SELECT ?ext (COUNT(DISTINCT ?item) AS ?n) WHERE {{ VALUES ?ext {{ {chunk} }} ?item wdt:P1195 ?ext. }} GROUP BY ?ext'):
            e = b['ext']['value'].lstrip('.').lower()
            counts[e] = counts.get(e, 0) + int(b['n']['value'])
        time.sleep(2)
    keep = {}
    for ext, items in cand.items():
        if len(items) != 1 or counts.get(ext, 0) != 1:
            continue
        item, d = next(iter(items.items()))
        if any(c in d['label'] for c in '/\\:*?"<>|') or len(d['label']) > 60 or norm(d['label']) == norm(ext):
            continue
        keep[ext] = {'item': item, 'label': d['label'], 'classes': sorted(d['classes'])}
    time.sleep(2)
    items = ' '.join(f"wd:{v['item']}" for v in keep.values())
    aliases = {}
    for b in _query(f'SELECT ?item ?alias WHERE {{ VALUES ?item {{ {items} }} ?item skos:altLabel ?alias. FILTER(LANG(?alias) = "en") }}'):
        aliases.setdefault(b['item']['value'].rsplit('/', 1)[1], []).append(b['alias']['value'])
    for v in keep.values():
        v['aliases'] = sorted(set(aliases.get(v['item'], [])))
    snap = {'built_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'source': SPARQL, 'classes': CLASSES,
            'candidates_before_filters': len(cand), 'formats': dict(sorted(keep.items()))}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, indent=1, ensure_ascii=False), encoding='utf-8')
    return snap


def split(snapshot):
    """Deterministic, frozen with protocol_p6 v2: an extension is in the evaluation pool iff the first hex
    digit of sha256('p6-pool:' + ext) is < 8; otherwise training."""
    out = {'train': [], 'eval': []}
    for ext in snapshot['formats']:
        out['eval' if int(hashlib.sha256(f'p6-pool:{ext}'.encode()).hexdigest()[0], 16) < 8 else 'train'].append(ext)
    return out


def accepts(snapshot, ext, name):
    f = snapshot['formats'].get(ext)
    return f is not None and norm(name) in {norm(f['label'])} | {norm(a) for a in f['aliases']}


def build_training_extra(snapshot, out, limit=400):
    """Training-only material (never evaluated): Wikidata file formats (any subclass of file format) with an
    English Wikipedia article whose extension is NOT in the evaluation pool. Looser than the evaluation
    filters: an extension shared by several items accepts any of their English labels."""
    ev = set(split(snapshot)['eval'])
    rows = _query('''SELECT ?item ?ext ?label WHERE {
      ?item wdt:P31/wdt:P279* wd:Q235557; wdt:P1195 ?ext; rdfs:label ?label. FILTER(LANG(?label) = "en")
      ?art schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>. } LIMIT 20000''')
    extra = {}
    for b in rows:
        ext = b['ext']['value'].strip().lstrip('.').lower()
        if not re.fullmatch(r'[a-z0-9]{2,8}', ext) or ext in ev or ext in snapshot['formats']:
            continue
        lab = b['label']['value']
        if norm(lab) == norm(ext) or any(c in lab for c in r'/\:*?"<>|'):
            continue
        extra.setdefault(ext, {'labels': set()})['labels'].add(lab)
    picked = sorted(extra, key=lambda e: hashlib.sha256(f'p6-extra:{e}'.encode()).hexdigest())[:limit]
    data = {e: sorted(extra[e]['labels']) for e in sorted(picked)}
    Path(out).write_text(json.dumps({'built_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'n_available': len(extra), 'formats': data},
                                    indent=1, ensure_ascii=False), encoding='utf-8')
    return data
