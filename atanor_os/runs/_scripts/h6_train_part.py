

# ---------------- H6-1 training (teacher on: locations, counterexamples, cue words) ----------------
def train_h6(out, reading_epochs=2, seed=1, label_results=3):
    """Same training formats and web policy as P6; the teacher additionally (a) locates the name on every
    page ATANOR opened (span annotation), (b) marks opened pages and up to `label_results` unopened search
    results as about-this-format or not (counterexamples), (c) annotates cue words in goal sentences."""
    import random
    from ..teach import h6_material, teacher
    from .p6 import FS_EXPERIENCE  # noqa: F401  (same filesystem experience as P6)
    from .p6 import save_state
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    snap = load_snapshot()
    tl0 = json.loads((PKG / 'results' / 'p6-train' / 'train_log.json').read_text(encoding='utf-8'))
    extra = json.loads((PKG / 'results' / 'p6-truth' / 'train_extra.json').read_text(encoding='utf-8'))['formats']
    teacher.EXTRA.update(extra)
    teach_exts = list(tl0['teach_exts'])
    held, dev, _ = transfer_set()
    assert not set(teach_exts) & (set(held) | set(dev) | set(split(snap)['eval']))
    rng = random.Random(f'h6-train-{seed}')
    web = WebSession(out / 'web', min_interval=1.0)
    agent = Agent(fs_model(), web, 'F')
    log = {'teach_exts': teach_exts, 'lexicon_epochs': [], 'reading_epochs': []}
    calls0 = teacher.CALLS['n']
    sents = [(s, f, []) for s, f in teacher.TRAIN_SENTENCES] + list(h6_material.H6_SENTENCES)
    for ep in range(3):
        rng.shuffle(sents)
        right = 0
        for s, _, cues in sents:
            pred = agent.lex.interpret(s)['form']                          # ATANOR answers first
            gold = dict((x[0], x[1]) for x in sents)[s]
            teacher.CALLS['n'] += 1
            right += pred == gold
            agent.lex.learn(s, gold)
            if cues:
                agent.lex.learn_cues(cues, gold)
        log['lexicon_epochs'].append({'epoch': ep, 'accuracy_before_feedback': right / len(sents)})
    opened_by_ext = {}
    for ep in range(reading_epochs):
        rows = []
        for k, ext in enumerate(teach_exts):
            agent.memory.pop(ext, None)
            agent.failed.pop(ext, None)
            agent.trace = []
            name, how = agent.find_name(ext)
            pages = [t for t in agent.trace if t['action'] == 'open' and t.get('ok')]
            opened_by_ext.setdefault(ext, [])
            opened_by_ext[ext] += [t['url'] for t in pages if t['url'] not in opened_by_ext[ext]]
            labelled = set()
            for t in pages:
                p = web.open(t['url'])
                if not p.get('ok'):
                    continue
                located = [n for n in teacher.EXTRA.get(ext, []) or [snap['formats'][ext]['label']] if n.lower() in p['text'].lower()]
                teacher.CALLS['n'] += 1
                relevant = bool(located) and ext.lower() in p['text'].lower()
                if located:
                    agent.reader.spans.learn(p['text'], ext, located)              # (a) where the name is written
                agent.reader.pages.learn(t['url'], ext, relevant)                  # (b) about this format or not
                agent.reader.record_host(t['url'], relevant)
                agent.reader.train(p['text'], ext, t['url'].rstrip('/').rsplit('/', 1)[-1].replace('_', ' '),
                                   lambda n, e=ext: teacher.feedback_name(snap, e, n), refit=False)
                labelled.add(t['url'])
            for t in agent.trace:                                             # (b') unopened results, labelled by the teacher
                if t['action'] == 'search':
                    for u in [u for u in t.get('results', []) if u not in labelled][:label_results]:
                        p = web.open(u)
                        if p.get('ok'):
                            located = [n for n in teacher.EXTRA.get(ext, []) or [snap['formats'][ext]['label']] if n.lower() in p['text'].lower()]
                            teacher.CALLS['n'] += 1
                            agent.reader.pages.learn(u, ext, bool(located) and ext.lower() in p['text'].lower())
                            labelled.add(u)
                    form = next((f for f in ('{ext} file format', '.{ext} file extension', '{EXT} format', '{ext}')
                                 if f.format(ext=ext, EXT=ext.upper()) == t['query']), None)
                    if form:
                        agent.reader.record_query(t['service'], form, any(p.get('best') and teacher.feedback_name(snap, ext, p['best']['name']) for p in pages))
            if k % 6 == 5 or ext == teach_exts[-1]:
                agent.reader.fit()
                agent.reader.pages.fit()
            correct = name is not None and teacher.feedback_name(snap, ext, name)
            if not correct:
                agent.memory[ext] = {'name': teacher.correct_name(snap, ext), 'source': 'teacher', 'evidence': []}
            rows.append({'ext': ext, 'adopted': name, 'how': how, 'correct': correct})
        log['reading_epochs'].append({'epoch': ep, 'adopted_correct': sum(r['correct'] for r in rows), 'n': len(rows),
                                      'adopted_wrong': sum(r['adopted'] is not None and not r['correct'] for r in rows), 'rows': rows})
    agent.reader.fit()
    agent.reader.pages.fit()
    per_ext = []
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
    log['teacher_calls'] = teacher.CALLS['n'] - calls0
    log['web'] = web.stats()
    log['spans'] = {'located_occurrences': agent.reader.spans.ns}
    save_state(out / 'state.json', agent)
    (out / 'train_log.json').write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding='utf-8')
    for f in ('train_sentences.json', 'dev_sentences.json'):
        (out / f).write_text((PKG / 'results' / 'p6-train' / f).read_text(encoding='utf-8'), encoding='utf-8')
    return log
