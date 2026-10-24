"""H6 development experiment (evaluator side): stage-wise measurement of reading, teacher off.

Not a task evaluation. On formats ATANOR was never taught (transfer set) and on goal sentences written
by an independent agent (kept outside the repository, hash published first), it measures separately:
  1. goal interpretation  — form accuracy on unseen sentences (+ 'goal unclear' rate)
  2. page selection       — with its own search/open policy, did it open >= 1 / >= 2 relevant pages
                            (relevant = the page contains the extension and an accepted name)?
  3. candidate generation — on relevant pages it opened, is an accepted name among its candidates?
  3'. given the right page — the format's own encyclopedia article (from Wikidata sitelinks): is an
                            accepted name a candidate, is it ranked first, is the page trusted?
  4. evidence judgement   — its final decision per format: correct / wrong adoption / abstain.
"""
import json
import sys
import time
import urllib.parse
from pathlib import Path

from ..agent.autonomy import FORMS, Agent, norm
from ..agent.reader import candidates, definitional
from ..world.web_world import WebSession
from .p6 import LLM_HOSTS, PKG, _NoTeacher, fs_model, load_snapshot, load_state, teacher_off
from .web_truth import _query, accepts, split

H6 = PKG / 'results' / 'h6-dev'


def transfer_set(n=40):
    """Formats never taught: training-only extra formats after the first 60 used in training, plus the 4 dev formats."""
    extra = json.loads((PKG / 'results' / 'p6-truth' / 'train_extra.json').read_text(encoding='utf-8'))['formats']
    tl = json.loads((PKG / 'results' / 'p6-train' / 'train_log.json').read_text(encoding='utf-8'))
    taught = set(tl['teach_exts'])
    held = [e for e in sorted(extra) if e not in taught][:n]
    return held, list(tl['dev_exts']), extra


def build_reference(out=H6 / 'reference.json'):
    """Evaluator: accepted names and English-Wikipedia article titles per transfer format (Wikidata, once)."""
    held, dev, extra = transfer_set()
    snap = load_snapshot()
    exts = held + dev
    vals = ' '.join(json.dumps(e) for e in exts) + ' ' + ' '.join(json.dumps('.' + e) for e in exts)
    rows = _query(f'''SELECT ?ext ?title WHERE {{ VALUES ?ext {{ {vals} }} ?item wdt:P1195 ?ext.
      ?art schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>; schema:name ?title. }}''')
    titles = {}
    for b in rows:
        titles.setdefault(b['ext']['value'].lstrip('.').lower(), set()).add(b['title']['value'])
    ref = {}
    for e in exts:
        names = extra[e] if e in extra else [snap['formats'][e]['label']] + snap['formats'][e]['aliases']
        ref[e] = {'names': sorted(set(names)), 'articles': sorted(titles.get(e, [])), 'group': 'dev' if e in dev else 'held_out'}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'built_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'formats': ref}, indent=1, ensure_ascii=False), encoding='utf-8')
    return ref


def _ok(ref, ext, name):
    return norm(name) in {norm(n) for n in ref[ext]['names']}


def measure(state_path, sentences_path, out, tag):
    """Teacher off, live web. Writes stage-wise measures to out/<tag>.json."""
    teacher_off()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ref = json.loads((H6 / 'reference.json').read_text(encoding='utf-8'))['formats']
    lex, rd, mem = load_state(state_path)
    res = {'tag': tag, 'state': str(state_path)}
    # 1. interpretation
    sents = json.loads(Path(sentences_path).read_text(encoding='utf-8'))['sentences']
    web = WebSession(out / f'web_{tag}', min_interval=1.0, blocked_hosts=LLM_HOSTS)
    agent = Agent(fs_model(), web, 'F', {}, lex, rd)
    rows = []
    for x in sents:
        it = agent.interpret(x['sentence'])
        rows.append({'form': x['form'], 'read': it['form'], 'margin': round(it['margin'], 2), 'unclear': it['margin'] < 1.0})
    res['interpretation'] = {'n': len(rows), 'accuracy': sum(r['form'] == r['read'] and not r['unclear'] for r in rows) / len(rows),
                             'unclear': sum(r['unclear'] for r in rows),
                             'by_form': {f: sum(r['form'] == f and r['read'] == f and not r['unclear'] for r in rows) for f in FORMS},
                             'confusions': {f'{a}->{b}': sum(r['form'] == a and r['read'] == b for r in rows) for a in FORMS for b in FORMS if a != b}}
    # 2-4. reading, with its own choices
    per = {}
    for ext in sorted(ref):
        agent.trace, agent.memory, agent.failed = [], {}, {}
        name, how = agent.find_name(ext)
        opened = [t for t in agent.trace if t['action'] == 'open' and t.get('ok')]
        relevant, cand_hit = 0, 0
        for t in opened:
            p = web.open(t['url'])
            if not p.get('ok'):
                continue
            text = p['text']
            rel = ext.lower() in text.lower() and any(n.lower() in text.lower() for n in ref[ext]['names'])
            relevant += rel
            if rel:
                title = t['url'].rstrip('/').rsplit('/', 1)[-1].replace('_', ' ')
                cs = candidates(text, ext, title) + definitional(text, ext, title)
                cand_hit += any(_ok(ref, ext, n) for n, _ in cs)
        per[ext] = {'group': ref[ext]['group'], 'opened': len(opened), 'relevant_opened': relevant, 'candidate_hit_on_relevant': cand_hit,
                    'decision': 'correct' if name and _ok(ref, ext, name) else ('wrong' if name else 'abstain'), 'name': name, 'how': how}
        # 3'. the right page given
        arts = ref[ext]['articles']
        if arts:
            url = 'https://en.wikipedia.org/wiki/' + urllib.parse.quote(arts[0].replace(' ', '_'))
            p = web.open(url)
            if p.get('ok'):
                cs = candidates(p['text'], ext, arts[0]) + definitional(p['text'], ext, arts[0])
                b = rd.best(p['text'], ext, arts[0])
                per[ext]['given_page'] = {'url': url, 'candidate_present': any(_ok(ref, ext, n) for n, _ in cs),
                                          'ranked_first': bool(b) and _ok(ref, ext, b['name']), 'top': None if not b else b['name'],
                                          'trusted': bool(b) and b['score'] > rd.threshold}
    n = len(per)
    gp = [v['given_page'] for v in per.values() if 'given_page' in v]
    dec = [v['decision'] for v in per.values()]
    res['page_selection'] = {'n': n, 'opened_any_relevant': sum(v['relevant_opened'] >= 1 for v in per.values()),
                             'opened_two_relevant': sum(v['relevant_opened'] >= 2 for v in per.values())}
    rel_pages = sum(v['relevant_opened'] for v in per.values())
    res['candidate_generation'] = {'relevant_pages_opened': rel_pages, 'accepted_name_among_candidates': sum(v['candidate_hit_on_relevant'] for v in per.values())}
    res['given_right_page'] = {'n': len(gp), 'candidate_present': sum(g['candidate_present'] for g in gp), 'ranked_first': sum(g['ranked_first'] for g in gp),
                               'trusted': sum(g['trusted'] for g in gp), 'trusted_and_first': sum(g['trusted'] and g['ranked_first'] for g in gp),
                               'trusted_but_wrong': sum(g['trusted'] and not g['ranked_first'] for g in gp)}
    res['evidence_judgement'] = {'n': n, 'correct': dec.count('correct'), 'wrong': dec.count('wrong'), 'abstain': dec.count('abstain'),
                                 'precision': dec.count('correct') / max(1, dec.count('correct') + dec.count('wrong')), 'recall': dec.count('correct') / n}
    res['web'] = web.stats()
    res['teacher_import_attempts'] = list(_NoTeacher.attempts)
    res['teacher_module_loaded'] = any(m.startswith('atanor_os.teach') for m in sys.modules)
    (out / f'{tag}.json').write_text(json.dumps({'result': res, 'per_format': per, 'interpretation_rows': rows}, indent=1, ensure_ascii=False, default=str),
                                     encoding='utf-8')
    return res


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
