import pathlib
p = pathlib.Path('atanor_os/agent/autonomy.py'); s = p.read_text(encoding='utf-8')
assert "                if b and b['score'] > 0:" in s
s = s.replace("                if b and b['score'] > 0:", "                if b and b['score'] > self.reader.threshold:", 1)
p.write_text(s, encoding='utf-8')

p = pathlib.Path('atanor_os/eval/p6.py'); s = p.read_text(encoding='utf-8')
old = "    log['teacher_calls'] = teacher.CALLS['n']\n"
new = """    agent.reader.fit()
    per_ext = []                                                   # calibration data: pages ATANOR chose, final weights
    for ext, urls in opened_by_ext.items():
        rows_c = []
        for u in urls:
            p = web.open(u)
            if p.get('ok'):
                b = agent.reader.best(p['text'], ext, u.rstrip('/').rsplit('/', 1)[-1].replace('_', ' '))
                if b:
                    rows_c.append((u, b['name'], b['score'], teacher.feedback_name(snap, ext, b['name'])))
        per_ext.append((ext, rows_c))
    log['calibration'] = agent.reader.calibrate(per_ext)
    log['teacher_calls'] = teacher.CALLS['n']
"""
assert old in s; s = s.replace(old, new, 1)
old = "            pages = [t for t in agent.trace if t['action'] == 'open' and t.get('ok')]\n"
new = old + "            opened_by_ext.setdefault(ext, [])\n            opened_by_ext[ext] += [t['url'] for t in pages if t['url'] not in opened_by_ext[ext]]\n"
assert old in s; s = s.replace(old, new, 1)
old = "    log = {'dev_exts': dev_exts, 'teach_exts': teach_exts, 'lexicon_epochs': [], 'reading_epochs': []}\n"
assert old in s; s = s.replace(old, old + "    opened_by_ext = {}\n", 1)
s = s.replace("          'reader': {'w': dict(rd.w), 'util': {f'{s}|{f}': u for (s, f), u in rd.util.items()}, 'updates': rd.updates,\n                     'examples': rd.examples},",
              "          'reader': {'w': dict(rd.w), 'util': {f'{s}|{f}': u for (s, f), u in rd.util.items()}, 'updates': rd.updates,\n                     'examples': rd.examples, 'threshold': rd.threshold},")
s = s.replace("    rd.updates = st['reader']['updates']\n", "    rd.updates = st['reader']['updates']\n    rd.threshold = st['reader'].get('threshold', 0.0)\n")
p.write_text(s, encoding='utf-8')
print('ok')
