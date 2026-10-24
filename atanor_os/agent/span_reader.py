"""H6-1: learned span locations and learned page relevance. Trained from teacher annotations in training
(where on a page the official name is written; which opened pages were about something else) and,
without a teacher, from ATANOR's own agreeing evidence. No LLM.

SpanModel: for every annotated name occurrence it counts the token context (1-2 tokens left/right,
with the extension replaced by <EXT> and digits by <N>), the capitalization shape of the span and its
length, and compares them with background counts from the same pages. At read time it proposes spans
whose shape was seen and whose context scores above background; the scores become ranking features.
PageModel: logistic regression over the URL/title of a search result (title words, extension in the
title, host) -> probability that the page is about the format; used to order which results to open.
"""
import math
import re
from collections import defaultdict

TOK = re.compile(r"[A-Za-z0-9][A-Za-z0-9+'\-]*|[(),.:;]")


def tokens(text):
    return [(m.group(0), m.start()) for m in TOK.finditer(text)]


def _ctx(tok, ext):
    t = tok.lower()
    if t == ext.lower() or t == '.' + ext.lower():
        return '<EXT>'
    if t.isdigit():
        return '<N>'
    return t


def _shape(span):
    out = []
    for t in span:
        if t.isdigit():
            out.append('N')
        elif t.isupper() and len(t) > 1:
            out.append('U')
        elif t[:1].isupper():
            out.append('C')
        elif t[:1].isalpha():
            out.append('l')
        else:
            out.append('P')
    return ''.join(out)


class SpanModel:
    MAXLEN = 7

    def __init__(self):
        self.c = defaultdict(float)      # (kind, key) -> count at name spans
        self.b = defaultdict(float)      # (kind, key) -> background count
        self.ns = self.nb = 0.0

    def _keys(self, toks, i, j, ext):
        L1 = _ctx(toks[i - 1], ext) if i >= 1 else '<S>'
        L2 = (_ctx(toks[i - 2], ext) if i >= 2 else '<S>') + ' ' + L1
        R1 = _ctx(toks[j], ext) if j < len(toks) else '<E>'
        R2 = R1 + ' ' + (_ctx(toks[j + 1], ext) if j + 1 < len(toks) else '<E>')
        return [('L1', L1), ('L2', L2), ('R1', R1), ('R2', R2), ('LR', L1 + '|' + R1), ('shape', _shape(toks[i:j])), ('len', str(j - i))]

    def learn(self, text, ext, names):
        """names: the accepted names the teacher located on this page (exact occurrences are found here)."""
        toks = [t for t, _ in tokens(text)]
        low = [t.lower() for t in toks]
        hits = 0
        for name in names:
            nt = [t.lower() for t, _ in tokens(name)]
            if not nt:
                continue
            for i in range(len(low) - len(nt) + 1):
                if low[i:i + len(nt)] == nt:
                    for k in self._keys(toks, i, i + len(nt), ext):
                        self.c[k] += 1
                    self.ns += 1
                    hits += 1
        step = max(1, len(toks) // 400)                       # background sample of spans on the same page
        for i in range(0, len(toks), step):
            for L in (1, 2, 3):
                if i + L <= len(toks):
                    for k in self._keys(toks, i, i + L, ext):
                        self.b[k] += 1
                    self.nb += 1
        return hits

    def _lr(self, k):
        return math.log((self.c[k] + 0.1) / (self.ns + 1.0)) - math.log((self.b[k] + 0.1) / (self.nb + 1.0))

    def propose(self, text, ext, limit=40):
        """(name, features) for spans with a seen shape whose context beats the background."""
        if self.ns < 3:
            return []
        toks = [t for t, _ in tokens(text)]
        low_ext = ext.lower()
        idx = [i for i, t in enumerate(toks) if t.lower() in (low_ext, '.' + low_ext)]
        if not idx:
            return []
        window = set()
        for m in idx:
            window.update(range(max(0, m - 25), min(len(toks), m + 25)))
        window.update(range(0, min(len(toks), 60)))           # page opening
        out = []
        for i in sorted(window):
            for L in range(1, self.MAXLEN + 1):
                j = i + L
                if j > len(toks) or any(not toks[x][0].isalnum() for x in range(i, j)):
                    break
                ks = self._keys(toks, i, j, ext)
                if self.c[ks[5]] == 0:                          # span shape never seen at a name
                    continue
                f = {'sp_' + kind: self._lr((kind, key)) for kind, key in ks}
                ctx = f['sp_L1'] + f['sp_R1'] + f['sp_L2'] + f['sp_R2']
                if ctx <= 0:
                    continue
                name = ' '.join(toks[i:j])
                if name.lower() == low_ext:
                    continue
                f['sp_ctx'] = ctx / 10.0
                f['sp_bias'] = 1.0
                out.append((name, {k: max(-5.0, min(5.0, v)) / 5.0 for k, v in f.items()}))
        out.sort(key=lambda x: -x[1]['sp_ctx'])
        return out[:limit]

    def state(self):
        return {'c': {'\t'.join(k): v for k, v in self.c.items()}, 'b': {'\t'.join(k): v for k, v in self.b.items()}, 'ns': self.ns, 'nb': self.nb}

    def load(self, st):
        for k, v in st.get('c', {}).items():
            self.c[tuple(k.split('\t', 1))] = v
        for k, v in st.get('b', {}).items():
            self.b[tuple(k.split('\t', 1))] = v
        self.ns, self.nb = st.get('ns', 0.0), st.get('nb', 0.0)


def _url_features(url, ext):
    host = url.split('/')[2] if '//' in url else ''
    title = re.sub(r'[_%()]+', ' ', url.rstrip('/').rsplit('/', 1)[-1]).lower()
    ws = set(re.findall(r'[a-z0-9]+', title))
    f = {'bias': 1.0, 'title_is_ext': float(title.strip() == ext.lower()), 'title_has_ext': float(ext.lower() in ws),
         'host:' + host: 1.0, 'n_words': min(len(ws), 8) / 8.0}
    for w in ws:
        if w != ext.lower() and len(w) >= 3:
            f['t:' + w] = 1.0
    return f


class PageModel:
    def __init__(self):
        self.w = defaultdict(float)
        self.examples = []

    def learn(self, url, ext, relevant):
        self.examples.append((_url_features(url, ext), 1.0 if relevant else 0.0))

    def fit(self, epochs=8, lr=0.1, l2=1e-3):
        pos = sum(y for _, y in self.examples) or 1
        neg = (len(self.examples) - pos) or 1
        for _ in range(epochs):
            for f, y in self.examples:
                z = sum(self.w[k] * v for k, v in f.items())
                p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
                g = (p - y) * (min(5.0, neg / pos) if y else 1.0)
                for k, v in f.items():
                    self.w[k] -= lr * (g * v + l2 * self.w[k])

    def score(self, url, ext):
        return sum(self.w[k] * v for k, v in _url_features(url, ext).items())

    def state(self):
        return {'w': dict(self.w), 'n_examples': len(self.examples)}

    def load(self, st):
        for k, v in st.get('w', {}).items():
            self.w[k] = v
