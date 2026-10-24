"""P6 reading: what ATANOR learns about English goals and about public pages. No LLM, no teacher here:
the teacher only supplies (in training) a label after ATANOR has answered; learning happens in these
counters and weights, and keeps happening without the teacher from ATANOR's own verified evidence.

Provided (BOOTSTRAP_MANIFEST §9): tokenization, the naive-Bayes / perceptron learning rules, the
candidate generator for names (spans of capitalized words, with short connectors, in sentences that
mention the extension) and the feature definitions. Learned: word -> goal-form associations, feature
weights for names, utilities of query forms and search services.
"""
import math
import re
from collections import defaultdict

WORD = re.compile(r"[a-z][a-z'\-]*")
CONNECT = {'of', 'and', 'for', 'the', 'to', 'de', 'in', 'on', '-', '&'}


def words(text):
    return WORD.findall(text.lower())


class Lexicon:
    """English goal -> form, by word/form counts. `unknown` = content words never seen in training."""

    def __init__(self, forms):
        self.forms = list(forms)
        self.c = defaultdict(lambda: defaultdict(float))
        self.n = defaultdict(float)
        self.vocab = set()
        self.learned_from_pages = []                    # self-acquired entries: (word, form weights, url)

    def learn(self, text, form, weight=1.0):
        ws = set(words(text))
        for w in ws:
            self.c[w][form] += weight
        self.n[form] += weight
        self.vocab |= ws

    def scores(self, text):
        ws = set(words(text))
        tot = sum(self.n.values()) or 1.0
        out = {}
        for f in self.forms:
            s = math.log((self.n[f] + 1) / (tot + len(self.forms)))
            for w in ws:
                if w in self.vocab:
                    s += math.log((self.c[w][f] + 0.5) / (self.n[f] + 1.0))
            out[f] = s
        return out

    def function_words(self):
        """Words seen with every form about as often as the form itself: carry no form information."""
        out = set()
        for w, d in self.c.items():
            if all(self.n[f] and d[f] / self.n[f] > 0.6 for f in self.forms):
                out.add(w)
        return out

    def interpret(self, text):
        sc = self.scores(text)
        ranked = sorted(sc, key=sc.get, reverse=True)
        margin = sc[ranked[0]] - sc[ranked[1]] if len(ranked) > 1 else float('inf')
        unknown = [w for w in dict.fromkeys(words(text)) if w not in self.vocab and len(w) > 2]
        return {'form': ranked[0], 'margin': margin, 'scores': sc, 'unknown': unknown}

    def associate(self, word, definition_text, url, weight=0.5):
        """Self-acquired meaning: a new word inherits the form associations of the known words in a page
        that defines it (scaled down). Returns the added weights (logged as evidence)."""
        known = [w for w in set(words(definition_text)) if w in self.vocab and w not in self.function_words()]
        add = {f: 0.0 for f in self.forms}
        for w in known:
            tot = sum(self.c[w].values()) or 1.0
            for f in self.forms:
                add[f] += self.c[w][f] / tot
        s = sum(add.values())
        if s <= 0:
            return None
        for f in self.forms:
            self.c[word][f] += weight * add[f] / s * 3
        self.vocab.add(word)
        self.learned_from_pages.append({'word': word, 'weights': add, 'url': url, 'known_words_used': sorted(known)[:20]})
        return add


def _variants(ext):
    return {ext.lower(), '.' + ext.lower()}


def candidates(text, ext, title=''):
    """(name, features) for capitalized spans in sentences that mention the extension (or its upper case)."""
    out = []
    sentences = re.split(r'(?<=[.!?])\s+|\n', text)
    first = True
    ev = _variants(ext)
    page_mentions = any(t.strip('.') == ext.lower() for t in re.findall(r"[A-Za-z0-9.]+", text.lower()))
    tnorm = re.sub(r'[^0-9a-z]+', '', title.casefold())
    dot_on_page = ('.' + ext.lower()) in text.lower()
    ext_label = bool(re.search(r'extension[^\n]{0,40}\.' + re.escape(ext.lower()) + r'\b', text.lower()))
    lowtext = text.lower()
    for si, sent in enumerate(sentences):
        toks = re.findall(r"[A-Za-z0-9][A-Za-z0-9+'\-]*|[(),&]", sent)
        low = [t.lower() for t in toks]
        mentions = [i for i, t in enumerate(low) if t.strip('.') in {ext.lower()} or t in ev]
        opening = si < 2 and page_mentions
        if not mentions and not opening:
            continue
        mentions = mentions or [0]
        i = 0
        while i < len(toks):
            if toks[i][0].isupper() and toks[i].lower() not in CONNECT:
                j = i
                span = [toks[i]]
                while j + 1 < len(toks) and (toks[j + 1][:1].isupper() or (toks[j + 1].lower() in CONNECT and j + 2 < len(toks) and toks[j + 2][:1].isupper())):
                    j += 1
                    span.append(toks[j])
                name = ' '.join(span)
                content = [t for t in span if t.lower() not in CONNECT]
                single_ok = len(content) == 1 and len(content[0]) >= 3 and not content[0].isdigit()
                if (single_ok or 2 <= len(content) <= 8) and name.lower() != ext.lower():
                    dist = min(abs(m - i) for m in mentions)
                    initials = ''.join(t[0] for t in span if t.lower() not in CONNECT).lower()
                    f = {'bias': 1.0,
                         'paren_ext': float(j + 2 < len(toks) and toks[j + 1] == '(' and toks[j + 2].lower() in ev),
                         'initials_ext': float(initials == ext.lower()),
                         'initials_prefix': float(len(ext) > 1 and initials.startswith(ext.lower()[:2])),
                         'near': 1.0 / (1 + dist), 'first_sentence': float(si == 0 or first),
                         'title_has_ext': float(ext.lower() in title.lower()),
                         'span_len': len(span) / 8.0, 'single_word': float(len(content) == 1),
                         'followed_by_is': float(j + 1 < len(toks) and low[j + 1] in ('is', 'was', 'are')),
                         'in_title': float(name.lower() in title.lower()),
                         'title_match': float(re.sub(r'[^0-9a-z]+', '', name.casefold()) == tnorm),
                         'opening_only': float(opening and not any(t.strip('.') == ext.lower() for t in low)),
                         'freq': math.log1p(lowtext.count(name.lower())) / 3.0,
                         'followed_by_paren': float(j + 1 < len(toks) and toks[j + 1] == '('),
                         'dot_ext_on_page': float(dot_on_page), 'dot_ext_in_sentence': float('.' + ext.lower() in sent.lower()),
                         'opens_page': float(si == 0 and i <= 1), 'page_lists_extension': float(ext_label)}
                    own = {t.lower() for t in span}
                    for w in dict.fromkeys(x for x in low if len(x) >= 3 and x.isalpha() and x not in own):
                        f['w:' + w] = 1.0                          # learned context: what the sentence talks about
                    out.append((name, f))
                i = j + 1
            else:
                i += 1
        first = False
    return out


DEF_SUBJECT = re.compile(r"^(?:(?:a|an|the)\s+)?([A-Za-z0-9][A-Za-z0-9+'\- ]{1,70}?)\s*(?:\(|,|\s+(?:is|was|are)\s+(?:a|an|the)\b)")


def definitional(text, ext, title=''):
    """Second provided generator: the subject phrase of a definitional sentence ("X is a ...", "X (...)"), in the
    page's first two sentences or in sentences that mention the extension. Catches sentence-case names."""
    out = []
    page_mentions = ('.' + ext.lower()) in text.lower() or re.search(r'\b' + re.escape(ext.lower()) + r'\b', text.lower())
    if not page_mentions:
        return out
    for si, sent in enumerate(re.split(r'(?<=[.!?])\s+|\n', text)[:400]):
        low = sent.lower()
        if si >= 2 and ext.lower() not in low:
            continue
        m = DEF_SUBJECT.match(sent.strip())
        if not m:
            continue
        name = m.group(1).strip()
        nw = len(name.split())
        if 1 <= nw <= 8 and name.lower() != ext.lower():
            out.append((name, {'definitional': 1.0, 'def_first_sentence': float(si == 0), 'def_len': nw / 8.0,
                               'def_title_match': float(re.sub(r'[^0-9a-z]+', '', name.casefold()) == re.sub(r'[^0-9a-z]+', '', title.casefold())),
                               'def_mentions_ext': float(ext.lower() in low), 'bias_def': 1.0}))
    return out


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
        self.threshold = 0.0                                # trust logit a page must exceed; calibrated in training
        self.host_util = defaultdict(lambda: [1.0, 2.0])    # host -> [useful pages+1, opened+2], learned

    def record_host(self, url, useful):
        u = self.host_util[url.split('/')[2] if '//' in url else url]
        u[0] += int(useful)
        u[1] += 1

    def host_value(self, url):
        u = self.host_util[url.split('/')[2] if '//' in url else url]
        return u[0] / u[1]

    def calibrate(self, per_ext, cost_wrong=2.0):
        """Provided rule: choose the threshold that maximizes (correct - cost_wrong * wrong) adoptions under the
        two-page agreement rule, on (ext, [(url, name, score, is_correct)]) gathered in training."""
        grid = sorted({round(s, 3) for _, rows in per_ext for _, _, s, _ in rows} | {0.0})
        best = (None, 0.0)
        for th in grid:
            util = 0.0
            for _, rows in per_ext:
                groups = {}
                for u, n, s, ok in rows:
                    if s > th:
                        groups.setdefault(norm_title(n), []).append((u, ok))
                agreed = [g for g in groups.values() if len({u for u, _ in g}) >= 2]
                if agreed:
                    g = max(agreed, key=len)
                    util += 1.0 if g[0][1] else -cost_wrong
            if best[0] is None or util > best[0] or (util == best[0] and th > best[1]):
                best = (util, th)
        self.threshold = best[1]
        return {'threshold': best[1], 'utility': best[0], 'grid': len(grid)}

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
        return f

    def _trust(self, f):
        return sum(self.w['t:' + k] * v for k, v in f.items())

    def best(self, text, ext, title=''):
        cs = candidates(text, ext, title) + definitional(text, ext, title)
        if not cs:
            return None
        ranked = self._ranked(cs)
        tf = self._trust_features(ranked, title, ext)
        name, rs, f = ranked[0]
        return {'name': name, 'score': self._trust(tf), 'rank_score': rs, 'features': f, 'n_candidates': len(ranked)}

    def train(self, text, ext, title, is_correct, refit=True):
        """Teacher (training) or own verified outcome on one page."""
        cs = candidates(text, ext, title) + definitional(text, ext, title)
        if not cs:
            return 0
        uniq = {}
        for n, f in cs:
            uniq.setdefault(n.lower(), (n, f))
        names = list(uniq.values())
        good = [i for i, (n, _) in enumerate(names) if is_correct(n)]
        if good:
            self.examples['rank'].append(([f for _, f in names], good))
        keep = sorted(names, key=lambda nf: -self._rank_score(nf[1]))[:15]   # stored as candidates, not page text
        keep += [names[i] for i in good if names[i] not in keep]
        self.examples['trust'].append((keep, ext, title, [n for n, _ in names if is_correct(n)]))
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
        for cs, ext, title, good_names in self.examples['trust']:
            if not cs:
                continue
            ranked = self._ranked([tuple(c) for c in cs])
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
