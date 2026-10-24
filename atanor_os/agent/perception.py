"""P7 perception tool: the ONLY place where a language model is reached.

One interface: `extract(excerpt, ext)` -> fact candidates with verbatim quotes. The prompt is fixed by
code (PROMPT_VERSION); ATANOR chooses the excerpt; the model never sees the goal, never plans,
selects sources, judges trust, chooses actions or edits code. Every candidate is verified by ATANOR:
the quote must occur verbatim in the excerpt and the value must occur in the quote; anything else is
rejected. Every call is logged (model, digest, prompt version, excerpt sha256 and length, raw reply,
latency, accepted/rejected candidates) so model-on and model-off runs can be compared.
"""
import hashlib
import json
import time
import urllib.request

PROMPT_VERSION = 'p7-extract-v1'
PROMPT = (
    'You extract facts from a text excerpt. Do not use outside knowledge.\n'
    'Question: according to this excerpt, what is the name of the file format that uses the file extension ".{ext}"?\n'
    'Answer only with JSON: {{"candidates": [{{"value": "<name exactly as written in the excerpt>", '
    '"quote": "<a short passage copied exactly from the excerpt that contains the name and supports it>"}}]}}. '
    'Use an empty list if the excerpt does not say. At most 3 candidates.\n\nExcerpt:\n"""\n{excerpt}\n"""'
)
MAX_EXCERPT = 1800


class OllamaBackend:
    """Local model through Ollama's HTTP API (localhost only; the web body blocks localhost for everything else)."""

    def __init__(self, model, host='http://127.0.0.1:11434', timeout=120):
        self.model, self.host, self.timeout = model, host, timeout
        self.digest = None
        try:
            with urllib.request.urlopen(urllib.request.Request(f'{host}/api/tags'), timeout=10) as r:
                for m in json.loads(r.read()).get('models', []):
                    if m.get('name') == model or m.get('model') == model:
                        self.digest = m.get('digest')
        except Exception:
            pass

    def complete(self, prompt):
        body = json.dumps({'model': self.model, 'prompt': prompt, 'stream': False, 'format': 'json',
                           'options': {'temperature': 0, 'seed': 7, 'num_predict': 300}}).encode()
        req = urllib.request.Request(f'{self.host}/api/generate', data=body, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            d = json.loads(r.read())
        return d.get('response', ''), {'prompt_tokens': d.get('prompt_eval_count'), 'output_tokens': d.get('eval_count')}


class Perception:
    def __init__(self, backend, log_path):
        self.backend, self.log_path = backend, log_path
        self.calls = 0

    def extract(self, excerpt, ext):
        excerpt = excerpt[:MAX_EXCERPT]
        prompt = PROMPT.format(ext=ext, excerpt=excerpt)
        t0 = time.time()
        self.calls += 1
        rec = {'at': t0, 'model': getattr(self.backend, 'model', type(self.backend).__name__),
               'digest': getattr(self.backend, 'digest', None), 'prompt_version': PROMPT_VERSION, 'ext': ext,
               'excerpt_sha256': hashlib.sha256(excerpt.encode()).hexdigest(), 'excerpt_chars': len(excerpt)}
        try:
            raw, usage = self.backend.complete(prompt)
            rec.update(raw=raw[:2000], usage=usage)
            data = json.loads(raw) if raw.strip() else {}
            cands = data.get('candidates', []) if isinstance(data, dict) else []
        except Exception as e:
            rec.update(error=f'{type(e).__name__}: {e}'[:300])
            cands = []
        accepted, rejected = [], []
        low = excerpt.lower()
        for c in cands[:3] if isinstance(cands, list) else []:
            v = str(c.get('value', '')).strip() if isinstance(c, dict) else ''
            q = str(c.get('quote', '')).strip() if isinstance(c, dict) else ''
            ok = bool(v) and bool(q) and q.lower() in low and v.lower() in q.lower() and len(v) <= 80
            (accepted if ok else rejected).append({'value': v, 'quote': q[:300]})
        rec.update(seconds=round(time.time() - t0, 3), accepted=accepted, rejected=rejected)
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        return accepted
