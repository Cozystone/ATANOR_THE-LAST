import pathlib


def patch(rel, pairs):
    p = pathlib.Path(rel)
    s = p.read_text(encoding='utf-8')
    for old, new in pairs:
        assert old in s, f'{rel}: {old[:90]}'
        s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')


patch('atanor_os/agent/autonomy.py', [
    ("    def __init__(self, fs_model, web=None, condition='F', memory=None, lexicon=None, reader=None):\n",
     "    def __init__(self, fs_model, web=None, condition='F', memory=None, lexicon=None, reader=None, perception=None):\n"
     "        self.perception = perception                      # P7: language model as a reading tool (None = model off)\n"),
    ("""                b = self.reader.best(p['text'], ext, title_of(p['url']))
                snippet = None
                if b:
                    i = p['text'].find(b['name'])
                    snippet = p['text'][max(0, i - 80): i + len(b['name']) + 80] if i >= 0 else None
                self.log('open', f'candidate source for .{ext}', ext=ext, url=p['url'], ok=True, sha256=p.get('sha256'),
                         best=None if not b else {'name': b['name'], 'score': round(b['score'], 3)}, snippet=snippet)
                if b and b['score'] > self.reader.threshold:
""", """                if self.perception is not None:                    # P7: the model reads excerpts ATANOR chose
                    b, snippet = self._perceive(p, ext)
                else:
                    b = self.reader.best(p['text'], ext, title_of(p['url']))
                    snippet = None
                    if b:
                        i = p['text'].find(b['name'])
                        snippet = p['text'][max(0, i - 80): i + len(b['name']) + 80] if i >= 0 else None
                self.log('open', f'candidate source for .{ext}', ext=ext, url=p['url'], ok=True, sha256=p.get('sha256'),
                         best=None if not b else {'name': b['name'], 'score': round(b['score'], 3)}, snippet=snippet)
                if b and b['score'] > (self.reader.threshold if self.perception is None else 0.0):
"""),
    ("    # ---- 3/4. acting ----\n", '''    def excerpts(self, text, ext, width=700, max_n=3):
        """ATANOR's own choice of what the model may read: the page's first paragraph and windows around the
        first mentions of the extension (fixed rule, no model involved)."""
        out = []
        para = next((l for l in text.split('\\n') if len(l.split()) >= 8), '')
        if para:
            out.append(para[:width * 2])
        low = text.lower()
        pos, start = [], 0
        for tok in ('.' + ext.lower(), ' ' + ext.lower() + ' ', ext.upper()):
            i = low.find(tok.lower(), start) if tok != ext.upper() else text.find(tok)
            if i >= 0:
                pos.append(i)
        for i in sorted(set(pos))[:max_n]:
            w = text[max(0, i - width): i + width]
            if all(w not in o for o in out):
                out.append(w)
        return out[:max_n]

    def _perceive(self, p, ext):
        """Model-extracted, quote-verified candidates for one page. ATANOR keeps the most supported value
        (most excerpts agreeing; ties: first excerpt); the model's own confidence is never used."""
        votes, quotes = {}, {}
        chosen = self.excerpts(p['text'], ext)
        for ex in chosen:
            for c in self.perception.extract(ex, ext):
                k = norm(c['value'])
                if k:
                    votes[k] = votes.get(k, 0) + 1
                    quotes.setdefault(k, (c['value'], c['quote']))
        self.log('perceive', f'read excerpts of {p["url"]} for .{ext}', ext=ext, url=p['url'], excerpts=len(chosen),
                 candidates={quotes[k][0]: v for k, v in votes.items()})
        if not votes:
            return None, None
        k = max(votes, key=lambda x: (votes[x], -list(quotes).index(x)))
        return {'name': quotes[k][0], 'score': float(votes[k])}, quotes[k][1]

    # ---- 3/4. acting ----
'''),
])
print('ok')
