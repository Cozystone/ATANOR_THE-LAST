import pathlib


def patch(rel, pairs):
    p = pathlib.Path(rel)
    s = p.read_text(encoding='utf-8')
    for old, new in pairs:
        assert old in s, f'{rel}: {old[:80]}'
        s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')


patch('atanor_os/agent/reader.py', [
    ("""        f['title_is_ext'] = float(norm_title(title) == ext.lower())
        for w in set(WORD.findall(title.lower())):
            if len(w) >= 3:
                f['tw:' + w] = 1.0
        return f""", """        f['title_is_ext'] = float(norm_title(title) == ext.lower())
        return f"""),
    ("""        self.threshold = 0.0                                # trust logit a page must exceed; calibrated in training
""", """        self.threshold = 0.0                                # trust logit a page must exceed; calibrated in training
        self.host_util = defaultdict(lambda: [1.0, 2.0])    # host -> [useful pages+1, opened+2], learned

    def record_host(self, url, useful):
        u = self.host_util[url.split('/')[2] if '//' in url else url]
        u[0] += int(useful)
        u[1] += 1

    def host_value(self, url):
        u = self.host_util[url.split('/')[2] if '//' in url else url]
        return u[0] / u[1]
"""),
])

patch('atanor_os/agent/autonomy.py', [
    ("""        self.memory = dict(memory or {})                  # ext -> {'name', 'evidence', 'source'}
""", """        self.memory = dict(memory or {})                  # ext -> {'name', 'evidence', 'source'}
        self.failed = {}                                  # ext -> reason: facts already searched for without success
"""),
    ("""        if not self.use_web:
            self.log('stop_fact', f'name of .{ext} unknown and no web in this condition', ext=ext, reason='no_evidence')
            return None, 'no_evidence'
""", """        if ext in self.failed:
            self.log('recall_failure', f'name of .{ext} was already searched for without success', ext=ext, reason=self.failed[ext])
            return None, self.failed[ext]
        if not self.use_web:
            self.log('stop_fact', f'name of .{ext} unknown and no web in this condition', ext=ext, reason='no_evidence')
            return None, 'no_evidence'
"""),
    ("""            queue = list(r.get('results', [])) + queue
            while queue and len(opened) < BUDGET['pages_per_fact'] and not adopted:
                url = queue.pop(0)""", """            queue = list(r.get('results', [])) + queue
            while queue and len(opened) < BUDGET['pages_per_fact'] and not adopted:
                queue.sort(key=lambda u: -self.reader.host_value(u))      # learned: which sites have been useful
                url = queue.pop(0)"""),
    ("""        names = {norm(e['name']) for e in evidence}
        reason = 'contradiction' if len(names) >= 2 else ('single_source' if names else 'no_evidence')""",
     """        names = {norm(e['name']) for e in evidence}
        reason = 'contradiction' if len(names) >= 2 else ('single_source' if names else 'no_evidence')
        self.failed[ext] = reason"""),
])

patch('atanor_os/eval/p6.py', [
    ("""            for t in pages:                                        # teacher feedback on every page it chose to open
                p = web.open(t['url'])
                if p.get('ok'):""", """            for t in pages:                                        # teacher feedback on every page it chose to open
                p = web.open(t['url'])
                agent.reader.record_host(t['url'], bool(t.get('best')) and teacher.feedback_name(snap, ext, t['best']['name']))
                if p.get('ok'):"""),
    ("""            agent.memory.pop(ext, None)
            agent.trace = []""", """            agent.memory.pop(ext, None)
            agent.failed.pop(ext, None)
            agent.trace = []"""),
    ("""                     'examples': rd.examples, 'threshold': rd.threshold},""",
     """                     'examples': rd.examples, 'threshold': rd.threshold, 'host_util': dict(rd.host_util)},"""),
    ("""    rd.threshold = st['reader'].get('threshold', 0.0)
""", """    rd.threshold = st['reader'].get('threshold', 0.0)
    for h, u in st['reader'].get('host_util', {}).items():
        rd.host_util[h] = list(u)
"""),
])
print('ok')
