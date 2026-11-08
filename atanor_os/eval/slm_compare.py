"""SLM_COMPARE_PROTOCOL.md: ATANOR (BAYES tau 0.99) and local small language models predict, from the same experiences,
what one call will do. The SLMs are evaluation opponents only: nothing here is imported by the learner.
  make  <body> <course_dir> <eval_seed> <out.json> [n_sample]   queries (stage-2 queries, truth from lab copies) + ATANOR
  ask   <model> <queries.json> <out.jsonl>                      one SLM, temperature 0, one try per query (resumable)
  score <dir>                                                   per body and model, over every queries/answers in <dir>
Each query carries every course experience of the same action (tool + constant arguments), oldest first; if they do not
fit, the most recent ones that fit (the number cut is recorded). The SLM answers the body's response and, per argument,
the attributes that change; everything it does not name stays as it was. Or {"unknown": true}.
"""
import json
import random
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

PROMPT_VERSION = 'p2'                                      # chosen on dev seeds 1-5 (SLM_COMPARE_RESULTS.md), then frozen
CHAR_BUDGET = 30000                                        # experiences text; about 10k tokens, inside num_ctx 16384 with room to answer
NUM_CTX = 16384
OLLAMA = 'http://127.0.0.1:11434/api/generate'

INTRO = """You predict what one call of a tool does in a small software world, using only past examples of the same call.
Each argument of the call is an object with attributes. "-" means "no value" (for kind=absent: the object does not exist).
The body answers "ok" (done), "failed" (could not be done) or "blocked" (not allowed).
In the examples, "changes" lists, per argument, only the attributes whose value changed; every other attribute stayed the same.
"""
ASK = {'p1': """Now predict this call. Answer with JSON only, in this form:
{"response": "ok" | "failed" | "blocked", "changes": [{...changed attributes of argument 1...}, {...argument 2...}]}
List one object per argument, in order ({} if nothing about it changes). If the examples do not let you tell, answer {"unknown": true}.
""", 'p2': """Now predict this call. Answer with JSON only, in this form:
{"response": "ok" | "failed" | "blocked", "changes": {"arg1": {...changed attributes of arg1...}, "arg2": {...changed attributes of arg2...}}}
Name every argument ({} if nothing about it changes). If the examples do not let you tell, answer {"unknown": true}.
"""}


def _attrs(o):
    return ' '.join(f'{k}={v}' for k, v in sorted((o or {}).items()))


def _split(x, n):
    objs = [dict() for _ in range(n)]
    for k, v in x.items():
        objs[k[0]][k[1]] = v
    return objs


def _case(c, n):
    before = _split(c.x, n)
    ch = [{} for _ in range(n)]
    for k, v in c.y.items():
        if k != ('r',) and before[k[0]].get(k[1], '-') != v:
            ch[k[0]][k[1]] = v
    return {'before': before, 'r': c.y.get(('r',), '?'), 'ch': ch}


def _case_text(c, version):
    args = ' | '.join(f'arg{i + 1}: {_attrs(b)}' for i, b in enumerate(c['before']))
    ch = c['ch'] if version == 'p1' else {f'arg{i + 1}': d for i, d in enumerate(c['ch'])}
    return f'before: {args}\n  -> response: {c["r"]}, changes: {json.dumps(ch, sort_keys=True)}'


def experiences_text(q, version=None):
    """The most recent experiences that fit, oldest first; and how many were cut."""
    version = version or PROMPT_VERSION
    lines, size = [], 0
    for c in reversed(q['cases']):
        t = _case_text(c, version)
        if size + len(t) > CHAR_BUDGET:
            break
        lines.append(t)
        size += len(t) + 1
    lines.reverse()
    return '\n'.join(f'{i + 1}. {t}' for i, t in enumerate(lines)), len(q['cases']) - len(lines)


def describe(key):
    tool, n, consts = key
    cs = dict(consts)
    return f'{tool}(' + ', '.join(f'{cs[i]!r} (always this object)' if i in cs else f'arg{i + 1}' for i in range(n)) + ')'


def make(body, course_dir, eval_seed, out, n_sample=None):
    from ..rebuild.bench_predict import judge, novelty, queries, train
    from ..rebuild.effects import flat
    eff, _ = train(body, course_dir, slack=1, tiered=True)
    qs = queries(body, course_dir, eval_seed, Path(out).with_suffix('.work'))
    idx = list(range(len(qs)))
    if n_sample is not None and n_sample < len(idx):
        idx = sorted(random.Random(f'{body}-{eval_seed}').sample(idx, n_sample))
    rows = []
    for i in idx:
        w, tool, args, before, truth, _ = qs[i]
        m = eff.model(tool, args)
        if m is None or not m.cases:
            continue
        p = eff.predict(tool, args, before, reader='BAYES0.99')['outcome']
        cases = [_case(c, len(args)) for c in sorted(m.cases + m.superseded, key=lambda c: c.t)]
        rows.append({'id': f'{body}-{eval_seed}-{i}', 'body': body, 'eval_seed': eval_seed, 'action': describe(m.key),
                     'n_args': len(args), 'before': before, 'novelty': novelty(m, flat(before)),
                     'cases': cases,
                     'truth': [[list(k), v] for k, v in truth.items()],
                     'atanor': judge(p, truth)})
    rows.sort(key=lambda r: r['action'])                   # same action in a row: the same prompt prefix
    Path(out).write_text(json.dumps(rows), encoding='utf-8')
    return rows


def prompt(q, version=None):
    version = version or PROMPT_VERSION
    call = ' | '.join(f'arg{i + 1}: {_attrs(b)}' for i, b in enumerate(q['before']))
    text, _ = experiences_text(q, version)
    return (f'{INTRO}\nThe call: {q["action"]}\nPast examples of this call, oldest first:\n{text}\n\n{ASK[version]}'
            f'The call now: before: {call}\n')


def call_ollama(model, text):
    body = {'model': model, 'prompt': text, 'stream': False, 'format': 'json', 'keep_alive': '30m',
            'options': {'temperature': 0, 'seed': 0, 'num_ctx': NUM_CTX, 'num_predict': 2048}}
    if model.startswith('gpt-oss'):
        body['think'] = 'low'
    req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read())


def parse(raw, q):
    """The SLM's text -> outcome {key: value} (the before with its changes), 'unknown', or 'invalid'."""
    try:
        a = json.loads(raw)
    except Exception:
        return 'invalid'
    if not isinstance(a, dict):
        return 'invalid'
    if a.get('unknown') is True or a.get('response') == 'unknown':
        return 'unknown'
    resp, ch = a.get('response'), a.get('changes', [])
    if isinstance(ch, dict):                               # {"arg1": {...}, ...}
        ch = [ch.get(f'arg{i + 1}', {}) for i in range(len(q['before']))]
    if isinstance(ch, list):                               # a change written as a JSON string of an object
        ch = [json.loads(c) if isinstance(c, str) and c.strip().startswith('{') else c for c in ch]
    if resp not in ('ok', 'failed', 'blocked') or not isinstance(ch, list) or not all(isinstance(c, dict) for c in ch):
        return 'invalid'
    y = {('r',): resp}
    for i, b in enumerate(q['before']):
        c = ch[i] if i < len(ch) else {}
        for k in set(b or {}) | set(c):
            y[(i, k)] = str(c[k]) if k in c else (b or {}).get(k, '-')
    return y


def judge_slm(y, q):
    if y in ('unknown', 'invalid'):
        return y
    return 'right' if all(y.get(tuple(k), '-') == v for k, v in q['truth']) else 'wrong'


def ask(model, qfile, out, version=None):
    version = version or PROMPT_VERSION
    qs = json.loads(Path(qfile).read_text(encoding='utf-8'))
    done = set()
    if Path(out).exists():
        done = {json.loads(l)['id'] for l in Path(out).read_text(encoding='utf-8').splitlines() if l.strip()}
    with open(out, 'a', encoding='utf-8') as f:
        for q in qs:
            if q['id'] in done:
                continue
            t0 = time.time()
            try:
                r = call_ollama(model, prompt(q, version))
                raw, err = r.get('response', ''), None
            except Exception as e:
                r, raw, err = {}, '', repr(e)
            y = parse(raw, q) if err is None else 'invalid'
            f.write(json.dumps({'id': q['id'], 'model': model, 'prompt_version': version, 'raw': raw, 'error': err,
                                'outcome': judge_slm(y, q), 's': round(time.time() - t0, 3),
                                'prompt_tokens': r.get('prompt_eval_count'), 'out_tokens': r.get('eval_count')}) + '\n')
            f.flush()


def score(d):
    d = Path(d)
    qs = {}
    for f in sorted(d.glob('q-*.json')):
        for q in json.loads(f.read_text(encoding='utf-8')):
            qs[q['id']] = q
    tab = defaultdict(lambda: defaultdict(Counter))
    secs = defaultdict(list)
    for q in qs.values():
        for part in ('all', q['novelty']):
            tab[(q['body'], 'ATANOR')][part][q['atanor']] += 1
    for f in sorted(d.glob('a-*.jsonl')):
        for l in f.read_text(encoding='utf-8').splitlines():
            a = json.loads(l)
            q = qs.get(a['id'])
            if q is None:
                continue
            for part in ('all', q['novelty']):
                tab[(q['body'], a['model'])][part][a['outcome']] += 1
            secs[(q['body'], a['model'])].append(a['s'])
    res = {}
    for (b, m), parts in sorted(tab.items()):
        def rate(c):
            n = sum(c.values())
            ans = c['right'] + c['wrong']
            return {'n': n, 'right': c['right'], 'wrong': c['wrong'], 'unknown': c['unknown'], 'invalid': c['invalid'],
                    'right_rate': round(c['right'] / n, 3) if n else None,
                    'wrong_rate': round(c['wrong'] / n, 3) if n else None,
                    'coverage': round(ans / n, 3) if n else None}
        s = sorted(secs.get((b, m), []))
        res.setdefault(b, {})[m] = {p: rate(c) for p, c in parts.items()} | (
            {'sec_median': s[len(s) // 2], 'sec_total': round(sum(s), 1)} if s else {})
    cut = Counter(q['body'] for q in qs.values() if experiences_text(q)[1] > 0)
    res['_cut'] = {f'{b} queries with experiences cut': n for b, n in cut.items()}
    return res


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'make':
        rows = make(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5], int(sys.argv[6]) if len(sys.argv) > 6 else None)
        print(len(rows), 'queries')
    elif cmd == 'ask':
        ask(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else None)
    elif cmd == 'score':
        print(json.dumps(score(sys.argv[2]), indent=1))
