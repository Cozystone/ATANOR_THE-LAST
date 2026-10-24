import pathlib


def patch(rel, pairs):
    p = pathlib.Path(rel)
    s = p.read_text(encoding='utf-8')
    for old, new in pairs:
        assert old in s, f'{rel}: {old[:90]}'
        s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')


patch('atanor_os/agent/reader.py', [
    ("from collections import defaultdict\n", "from collections import defaultdict\n\nfrom .span_reader import PageModel, SpanModel\n"),
    ("        self.host_util = defaultdict(lambda: [1.0, 2.0])    # host -> [useful pages+1, opened+2], learned\n",
     "        self.host_util = defaultdict(lambda: [1.0, 2.0])    # host -> [useful pages+1, opened+2], learned\n"
     "        self.spans = SpanModel()                            # H6-1: where names are written (teacher-located spans)\n"
     "        self.pages = PageModel()                            # H6-1: which results are about the format\n"),
    ("    def best(self, text, ext, title=''):\n        cs = candidates(text, ext, title) + definitional(text, ext, title)\n",
     "    def all_candidates(self, text, ext, title=''):\n"
     "        \"\"\"Provided generators plus the learned span proposals, merged by name (features united).\"\"\"\n"
     "        merged = {}\n"
     "        for name, f in candidates(text, ext, title) + definitional(text, ext, title) + self.spans.propose(text, ext):\n"
     "            k = name.lower()\n"
     "            if k in merged:\n"
     "                merged[k] = (merged[k][0], {**merged[k][1], **f})\n"
     "            else:\n"
     "                merged[k] = (name, dict(f))\n"
     "        return list(merged.values())\n\n"
     "    def best(self, text, ext, title=''):\n        cs = self.all_candidates(text, ext, title)\n"),
    ("        cs = candidates(text, ext, title) + definitional(text, ext, title)\n        if not cs:\n            return 0\n",
     "        cs = self.all_candidates(text, ext, title)\n        if not cs:\n            return 0\n"),
])

patch('atanor_os/agent/reader.py', [
    ("    def associate(self, word, definition_text, url, weight=0.5):",
     "    def learn_cues(self, cues, form, weight=2.0):\n"
     "        \"\"\"Teacher annotation (training): the words of a sentence that carry its form get extra weight.\"\"\"\n"
     "        for w in cues:\n"
     "            self.c[w.lower()][form] += weight\n"
     "            self.vocab.add(w.lower())\n\n"
     "    def associate(self, word, definition_text, url, weight=0.5):"),
])

patch('atanor_os/agent/autonomy.py', [
    ("                queue.sort(key=lambda u: -self.reader.host_value(u))      # learned: which sites have been useful",
     "                queue.sort(key=lambda u: -(self.reader.pages.score(u, ext) + self.reader.host_value(u)))   # learned relevance"),
])

patch('atanor_os/eval/p6.py', [
    ("                     'examples': rd.examples, 'threshold': rd.threshold, 'host_util': dict(rd.host_util)},",
     "                     'examples': rd.examples, 'threshold': rd.threshold, 'host_util': dict(rd.host_util),\n"
     "                     'spans': rd.spans.state(), 'pages': rd.pages.state()},"),
    ("    for h, u in st['reader'].get('host_util', {}).items():\n        rd.host_util[h] = list(u)\n",
     "    for h, u in st['reader'].get('host_util', {}).items():\n        rd.host_util[h] = list(u)\n"
     "    rd.spans.load(st['reader'].get('spans', {}))\n    rd.pages.load(st['reader'].get('pages', {}))\n"),
])
print('ok')
