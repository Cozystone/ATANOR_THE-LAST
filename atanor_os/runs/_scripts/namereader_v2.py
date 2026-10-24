class NameReader:
    """Two learned stages (provided learning rules, learned weights):
    1. rank: softmax over a page's candidates -> the page's best candidate;
    2. trust: logistic over page-level features -> is this page about the format of this extension?
    best()['score'] is the trust logit (> 0: the page is trusted). Plus learned utilities of
    (service, query form)."""

    PAGE_KEYS = ('title_has_ext', 'page_lists_extension', 'dot_ext_on_page')

    def __init__(self):
        self.w = defaultdict(float)                         # 'r:'-prefixed ranking weights, 't:'-prefixed trust weights
        self.util = defaultdict(lambda: [1.0, 2.0])         # (service, form) -> [hits+1, tries+2]
        self.updates = 0
        self.examples = {'rank': [], 'trust': []}

    # --- stage 1 ---
    def _rank_score(self, f):
        return sum(self.w['r:' + k] * v for k, v in f.items())

    def _ranked(self, cs):
        agg = {}
        for name, f in cs:
            s = self._rank_score(f)
            key = name.lower()
            if key not in agg or s > agg[key][1]:
                agg[key] = (name, s, f)
        return sorted(agg.values(), key=lambda x: (-x[1], x[0]))

    # --- stage 2 ---
    def _trust_features(self, ranked, title, ext):
        top = ranked[0]
        f = {'bias': 1.0, 'margin': max(-5.0, min(5.0, top[1] - (ranked[1][1] if len(ranked) > 1 else top[1] - 5.0))) / 5.0,
             'n_cand': math.log1p(len(ranked)) / 5.0}
        for k in self.PAGE_KEYS:
            f[k] = top[2].get(k, 0.0)
        for k, v in top[2].items():
            if not k.startswith('w:'):
                f['top:' + k] = v
        f['title_is_ext'] = float(norm_title(title) == ext.lower())
        for w in set(WORD.findall(title.lower())):
            if len(w) >= 3:
                f['tw:' + w] = 1.0
        return f

    def _trust(self, f):
        return sum(self.w['t:' + k] * v for k, v in f.items())

    def best(self, text, ext, title=''):
        cs = candidates(text, ext, title)
        if not cs:
            return None
        ranked = self._ranked(cs)
        tf = self._trust_features(ranked, title, ext)
        name, rs, f = ranked[0]
        return {'name': name, 'score': self._trust(tf), 'rank_score': rs, 'features': f, 'n_candidates': len(ranked)}

    def train(self, text, ext, title, is_correct, refit=True):
        """Teacher (training) or own verified outcome on one page."""
        cs = candidates(text, ext, title)
        if not cs:
            return 0
        uniq = {}
        for n, f in cs:
            uniq.setdefault(n.lower(), (n, f))
        names = list(uniq.values())
        good = [i for i, (n, _) in enumerate(names) if is_correct(n)]
        if good:
            self.examples['rank'].append(([f for _, f in names], good))
        ranked = self._ranked(cs)
        self.examples['trust'].append((text, ext, title, bool(good), [n for n, _ in names if is_correct(n)]))
        self.updates += 1
        if refit:
            self.fit()
        return 1

    def fit(self, epochs=6, lr=0.1, l2=1e-4, iters=None):
        import random as _r
        rng = _r.Random(len(self.examples['rank']) + 7 * len(self.examples['trust']))
        w = self.w
        R = list(self.examples['rank'])
        for _ in range(epochs):                              # softmax ranking, correct = any accepted candidate
            rng.shuffle(R)
            for fs, good in R:
                zs = [sum(w['r:' + k] * v for k, v in f.items()) for f in fs]
                m = max(zs)
                ps = [math.exp(z - m) for z in zs]
                tot = sum(ps)
                pg = sum(ps[i] for i in good) or 1e-12
                for i, f in enumerate(fs):
                    g = ps[i] / tot - ((ps[i] / pg) if i in good else 0.0)
                    if g:
                        for k, v in f.items():
                            w['r:' + k] -= lr * (g * v + l2 * w['r:' + k])
        T = []                                               # trust examples depend on the current ranking
        for text, ext, title, has_good, good_names in self.examples['trust']:
            cs = candidates(text, ext, title)
            if not cs:
                continue
            ranked = self._ranked(cs)
            y = 1.0 if ranked[0][0] in good_names else 0.0
            T.append((self._trust_features(ranked, title, ext), y))
        pos = sum(y for _, y in T) or 1
        neg = (len(T) - pos) or 1
        for _ in range(epochs):
            rng.shuffle(T)
            for f, y in T:
                z = sum(w['t:' + k] * v for k, v in f.items())
                p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
                g = (p - y) * (min(5.0, neg / pos) if y else 1.0)
                for k, v in f.items():
                    w['t:' + k] -= lr * (g * v + l2 * w['t:' + k])

    def record_query(self, service, form, useful):
        u = self.util[(service, form)]
        u[0] += int(useful)
        u[1] += 1

    def ranked_queries(self, forms, services):
        return sorted(((s, f) for s in services for f in forms), key=lambda sf: (-self.util[sf][0] / self.util[sf][1], sf))

    def snapshot(self):
        return {'weights': dict(self.w), 'utility': {f'{s}|{f}': u for (s, f), u in self.util.items()}, 'updates': self.updates,
                'examples': {k: len(v) for k, v in self.examples.items()}}


def norm_title(t):
    return re.sub(r'[^0-9a-z]+', '', t.casefold())
