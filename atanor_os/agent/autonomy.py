"""P6 autonomous task execution: one generic decision procedure, no per-task script, no teacher.

Given an English goal and a workspace, ATANOR (1) interprets the goal with its learned lexicon and,
when the interpretation is not decisive and contains words it has never seen, looks those words up on
the web; (2) for every file whose needed fact (the official name of its format) is not in memory,
chooses a search service and query form by learned utility, opens result pages it chooses, follows
links that mention the extension, extracts the best-scoring name per page and adopts a name only when
`agree` distinct pages give the same one (otherwise reports contradiction / single source / no
evidence and leaves the file alone); (3) rehearses the first file's actions in a sandbox copy and
checks the outcome before acting for real; (4) acts with its learned filesystem rules through the
same journaled loop as P1-P4; (5) stops with a reason. Every information action records its trigger
(what was unknown at that moment) and every adopted fact its evidence (URLs, snippet, page sha256).
Page text is only data: nothing read is executed.
"""
import re
import shutil
import tempfile
import time
import urllib.parse
from pathlib import Path

from ..core.journal import Journal
from ..core.types import Goal, Literal
from .loop import run_episode
from .reader import Lexicon, NameReader, words

FORMS = ('folder', 'rename', 'copy')
QUERY_FORMS = ('{ext} file format', '.{ext} file extension', '{EXT} format', '{ext}')   # provided candidates; utility learned
MARGIN = 1.0                                  # provided: an interpretation is decisive when its log-odds margin >= 1
BUDGET = {'searches_per_fact': 3, 'pages_per_fact': 6, 'follow_per_page': 2, 'lookups_per_goal': 3,
          'actions': 20, 'predictions': 400000, 'nodes': 600, 'depth': 12, 'seconds': 120.0}


def norm(s):
    return re.sub(r'[^0-9a-z]+', '', s.casefold())


def title_of(url):
    return urllib.parse.unquote(url.rstrip('/').rsplit('/', 1)[-1]).replace('_', ' ')


class Agent:
    def __init__(self, fs_model, web=None, condition='F', memory=None, lexicon=None, reader=None):
        cfg = {'F': (True, 2), 'S': (True, 1), 'M': (False, 2), 'N': (False, 2)}[condition]
        self.use_web, self.agree = cfg
        self.condition, self.web, self.fs_model = condition, web, fs_model
        self.memory = dict(memory or {})                  # ext -> {'name', 'evidence', 'source'}
        self.failed = {}                                  # ext -> reason: facts already searched for without success
        self.lex = lexicon or Lexicon(FORMS)
        self.reader = reader or NameReader()
        self.trace = []
        self.t0 = time.time()

    def log(self, action, trigger, **detail):
        self.trace.append({'t': round(time.time() - self.t0, 3), 'action': action, 'trigger': trigger, **detail})

    # ---- 1. goal interpretation ----
    def interpret(self, goal_text):
        it = self.lex.interpret(goal_text)
        self.log('interpret', 'new goal', form=it['form'], margin=round(it['margin'], 2), unknown=it['unknown'])
        looked = 0
        while it['margin'] < MARGIN and it['unknown'] and self.use_web and looked < BUDGET['lookups_per_goal']:
            w = it['unknown'][0]
            looked += 1
            r = self.web.search('wikipedia', w)
            self.log('search', f'goal word "{w}" never seen and interpretation not decisive', service='wikipedia', query=w,
                     results=r.get('results', [])[:3], ok=r.get('ok'))
            added = None
            for url in r.get('results', [])[:1]:
                p = self.web.open(url)
                self.log('open', f'definition of "{w}"', url=url, ok=p.get('ok'), sha256=p.get('sha256'))
                if p.get('ok'):
                    added = self.lex.associate(w, p['text'][:1500], url)
            self.log('learn_word', f'definition page read for "{w}"', word=w, added=added)
            it = self.lex.interpret(goal_text)
            if w in it['unknown']:
                it['unknown'].remove(w)
            self.log('interpret', 'after lookup', form=it['form'], margin=round(it['margin'], 2), unknown=it['unknown'])
        return it

    # ---- 2. facts from the web ----
    def find_name(self, ext):
        if ext in self.memory:
            self.log('recall', f'name of .{ext} already known', ext=ext, name=self.memory[ext]['name'])
            return self.memory[ext]['name'], 'memory'
        if ext in self.failed:
            self.log('recall_failure', f'name of .{ext} was already searched for without success', ext=ext, reason=self.failed[ext])
            return None, self.failed[ext]
        if not self.use_web:
            self.log('stop_fact', f'name of .{ext} unknown and no web in this condition', ext=ext, reason='no_evidence')
            return None, 'no_evidence'
        evidence, opened, searches = [], set(), 0
        tried = []
        queue = []
        adopted = None
        for service, form in self.reader.ranked_queries(QUERY_FORMS, ('wikipedia', 'wiby')):
            if searches >= BUDGET['searches_per_fact'] or adopted or len(opened) >= BUDGET['pages_per_fact']:
                break
            q = form.format(ext=ext, EXT=ext.upper())
            r = self.web.search(service, q)
            searches += 1
            tried.append((service, form, len(evidence)))
            self.log('search', f'name of .{ext} unknown', ext=ext, service=service, query=q, ok=r.get('ok'),
                     results=r.get('results', [])[:6], error=r.get('error'))
            queue = list(r.get('results', [])) + queue
            while queue and len(opened) < BUDGET['pages_per_fact'] and not adopted:
                queue.sort(key=lambda u: -self.reader.host_value(u))      # learned: which sites have been useful
                url = queue.pop(0)
                if url in opened:
                    continue
                opened.add(url)
                p = self.web.open(url)
                if not p.get('ok'):
                    self.log('open', f'candidate source for .{ext}', ext=ext, url=url, ok=False, error=p.get('error'))
                    continue
                b = self.reader.best(p['text'], ext, title_of(p['url']))
                snippet = None
                if b:
                    i = p['text'].find(b['name'])
                    snippet = p['text'][max(0, i - 80): i + len(b['name']) + 80] if i >= 0 else None
                self.log('open', f'candidate source for .{ext}', ext=ext, url=p['url'], ok=True, sha256=p.get('sha256'),
                         best=None if not b else {'name': b['name'], 'score': round(b['score'], 3)}, snippet=snippet)
                if b and b['score'] > self.reader.threshold:
                    evidence.append({'url': p['url'], 'name': b['name'], 'score': b['score'], 'sha256': p.get('sha256'),
                                     'snippet': snippet, 'text': p['text'], 'title': title_of(p['url'])})
                    groups = {}
                    for e in evidence:
                        groups.setdefault(norm(e['name']), []).append(e)
                    for g in groups.values():
                        if len({e['url'] for e in g}) >= self.agree:
                            adopted = max(g, key=lambda e: e['score'])['name']
                            self.log('compare', f'{len(g)} source(s) agree on the name of .{ext}', ext=ext, name=adopted,
                                     sources=[e['url'] for e in g], disagreeing=[(e['url'], e['name']) for e in evidence if norm(e['name']) != norm(adopted)])
                            break
                ext_l = ext.lower()
                follow = [u for u, a in p.get('links', []) if (ext_l in a.lower().split() or f'.{ext_l}' in a.lower() or
                                                               f'/{ext_l}' in u.lower()) and u not in opened][:BUDGET['follow_per_page']]
                if follow:
                    self.log('follow', f'links on {p["url"]} mention .{ext}', ext=ext, links=follow)
                    queue = follow + queue
        for service, form, before in tried:
            self.reader.record_query(service, form, useful=adopted is not None and any(norm(e['name']) == norm(adopted) for e in evidence[before:]))
        if adopted:
            for e in evidence:                                       # learn from own agreeing evidence (no teacher)
                if norm(e['name']) == norm(adopted):
                    self.reader.train(e['text'], ext, e['title'], lambda n: norm(n) == norm(adopted), refit=False)
            self.reader.fit(epochs=1)
            self.memory[ext] = {'name': adopted, 'source': 'web', 'evidence': [(e['url'], e['sha256'], e['snippet']) for e in evidence
                                                                               if norm(e['name']) == norm(adopted)]}
            return adopted, 'adopted'
        names = {norm(e['name']) for e in evidence}
        reason = 'contradiction' if len(names) >= 2 else ('single_source' if names else 'no_evidence')
        self.failed[ext] = reason
        self.log('stop_fact', f'no agreeing sources for .{ext}', ext=ext, reason=reason,
                 seen=[(e['url'], e['name']) for e in evidence], pages=len(opened), searches=searches)
        return None, reason

    # ---- 3/4. acting ----
    def _goal_for(self, form, src, name, ext, state, others):
        base = src.rsplit('/', 1)[-1]
        h = state[src]['hash']
        if form == 'rename':
            dst = f'{name}.{ext}'
            must = [Literal('kind', (dst,), 'file'), Literal('hash', (dst,), h), Literal('kind', (src,), 'absent')]
            uni = [src, dst]
        else:
            dst = f'{name}/{base}'
            must = [Literal('kind', (name,), 'dir'), Literal('kind', (dst,), 'file'), Literal('hash', (dst,), h)]
            must += [Literal('kind', (src,), 'absent')] if form == 'folder' else []
            uni = [src, name, dst]
        keep = [l for o in others for l in (Literal('kind', (o,), state[o]['kind']), Literal('hash', (o,), state[o]['hash']))]
        if form == 'copy':
            keep += [Literal('kind', (src,), 'file'), Literal('hash', (src,), h)]
        return Goal(f'p6:{form}:{src}', must, keep, {}, {k: BUDGET[k] for k in ('actions', 'predictions', 'nodes', 'depth', 'seconds')},
                    uni + others), dst

    def act_file(self, ws, form, src, name, ext, journal, rehearse):
        if not re.fullmatch(r'[^/\:*?"<>|]+', name) or name != name.strip() or name.endswith('.'):
            self.log('stop_file', 'adopted name cannot be used as a file or folder name', src=src, name=name, reason='name_not_usable')
            return False, 'name_not_usable'
        state = ws.observe([])
        others = [p for p, o in state.items() if p != src and o['kind'] == 'file']
        goal, dst = self._goal_for(form, src, name, ext, state, others)
        if rehearse:                                                # small experiment: same plan on a sandbox copy
            tmp = Path(tempfile.mkdtemp(prefix='atanor_rehearse_'))
            try:
                shutil.copytree(ws.root, tmp / 'w')
                from ..world.fs_world import Workspace
                sw = Workspace(tmp / 'w', create=False)
                sj = Journal(tmp / 'j.sqlite')
                rec = run_episode(sw, goal, self.fs_model, sj, f'rehearse:{src}')
                ok = goal.satisfied(sw.observe(goal.universe))
                sj.close()
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            self.log('experiment', 'verify the plan in a sandbox copy before the first real action', src=src, form=form,
                     outcome_ok=ok, actions=rec['actions'], noops=rec['noops'])
            if not ok:
                self.log('stop_file', 'rehearsal did not reach the interpreted goal', src=src, reason='rehearsal_failed')
                return False, 'rehearsal_failed'
        rec = run_episode(ws, goal, self.fs_model, journal, f'p6:{src}')
        ok = goal.satisfied(ws.observe(goal.universe))
        self.log('act', f'name of .{ext} adopted; goal form {form}', src=src, dst=dst, ok=ok, actions=rec['actions'], noops=rec['noops'])
        return ok, ('done' if ok else 'action_failed')

    # ---- whole task ----
    def run(self, goal_text, ws, journal):
        t0 = time.time()
        it = self.interpret(goal_text)
        result = {'form': it['form'], 'margin': it['margin'], 'files': {}, 'stopped': None}
        if it['margin'] < MARGIN:
            self.log('stop', 'goal interpretation not decisive', reason='goal_unclear', scores=it['scores'])
            result['stopped'] = 'goal_unclear'
            result['seconds'] = time.time() - t0
            return result
        files = sorted(p for p, o in ws.observe([]).items() if o['kind'] == 'file' and '/' not in p and '.' in p)
        first = True
        for src in files:
            ext = src.rsplit('.', 1)[1].lower()
            name, how = self.find_name(ext)
            if name is None:
                result['files'][src] = {'status': how}
                continue
            ok, st = self.act_file(ws, it['form'], src, name, ext, journal, rehearse=first)
            first = False
            result['files'][src] = {'status': st, 'name': name, 'fact': how}
        self.log('stop', 'every file handled or left with a reason', reason='done',
                 left=[f for f, v in result['files'].items() if v['status'] != 'done'])
        result['stopped'] = 'done'
        result['seconds'] = time.time() - t0
        return result
