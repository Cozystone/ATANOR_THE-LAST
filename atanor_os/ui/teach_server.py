"""Interactive Grounding Tutor for a real person (board body), separate from the program tutor.

The person and ATANOR look at the same board in a sandbox (a JSON file in a folder of its own; no user data, no OS
access; the server listens on 127.0.0.1 only). The learner is the same `agent.grounding.Grounder` the regression tutor
uses, but its `person` is a `HumanPerson`: every point / contrast / demo / confirm it asks for is shown on the screen and
waits for the person's answer. Everything it learns is recorded with source 'human' (events, claims, ontology), so
experience from a real person and from the program tutor stay apart.

The session log (log.jsonl in the sandbox) is what the reuse measurement reads: which symbol or phrase was taught in
which session and on which date, and later, whether a command using it worked on cards that did not exist when it was
taught. Failures are only classified here, never patched.

Usage: python -m atanor_os.ui.teach_server [--root DIR] [--port 8765] [--seed 1]
"""
import argparse
import ast
import datetime
import json
import queue
import random
import threading
import time
import traceback
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..agent.learners import make as make_learner
from ..agent.memory import ClaimLedger, Memory
from ..world.board_world import LEVELS, MARKS, TRAYS, BoardWorkspace

PAGE = Path(__file__).with_name('teach.html')
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / 'user-sandbox' / 'board-1'     # outside the repository
ATTR = {'a0': 'kind', 'a1': 'mark', 'a2': 'tray', 'a3': 'level', 'a4': 'value'}       # display names only (the learner never sees them)
CARDS_PER_SESSION = 8


class Cancelled(Exception):
    pass


class HumanPerson:
    """The person on the other side of the screen. A question from ATANOR waits here until the person answers."""

    def __init__(self, home):
        self.home = home
        self.pending = None
        self.answers = queue.Queue()
        self.help = Counter()
        self.n = 0

    def ask(self, kind, **info):
        self.n += 1
        self.pending = {'kind': kind, 'n': self.n, **info}
        ans = self.answers.get()
        self.pending = None
        if isinstance(ans, dict) and ans.get('cancel'):
            raise Cancelled()
        return ans

    def point(self, k=2):
        self.help['point'] += 1
        return sorted(self.ask('point')['objects'])

    def contrast(self, obj):
        self.help['contrast'] += 1
        return bool(self.ask('contrast', object=obj)['yes'])

    def propose(self, effect):
        """ATANOR asks, before acting, whether a word means an action it already knows here."""
        self.help['propose'] += 1
        return bool(self.ask('propose', tool=effect['tool'], note=f"이 낱말은 '{effect['tool']}' 행동을 말하나요?")['yes'])

    def demo(self):
        """The person does the action once on one card; the board executes it as the person's own action."""
        self.help['demo'] += 1
        err = None
        for _ in range(3):                                 # after three actions that do not work, the person gives up
            d = self.ask('demo', error=err)
            args = tuple(a for a in d['args'] if a)
            try:
                res = self.home.execute(d['tool'], args, {c: True for c in set(self.home.CAPABILITY.values())},
                                        **({'actor': 'person'} if getattr(self.home, 'BODY', '') in ('desk', 'clime') else {}))
            except ValueError:
                res = {'ok': False, 'error': 'invalid action'}
            if res['ok']:
                card = d.get('object') or next((a for a in args if self.home.kind(a) in ('card', 'file', 'panel', 'message', 'draft', 'task', 'note', 'bay')), args[0])   # the object acted on
                return {'tool': d['tool'], 'args': list(args), 'object': card}
            err = f"그 행동은 되지 않았습니다 ({res.get('error')}). 다른 카드나 값으로 다시 보여 주세요."
        raise Cancelled()


def classify(row):
    """Failure classes (from the user's directive); a class says where to look, it never selects a patch."""
    o, why = row.get('outcome'), row.get('why')
    if o == 'success':
        return None
    if o == 'held':
        if row.get('unknown') and len(row['unknown']) == len(row.get('words', [])):
            return 'grounding: no word known'
        if why == 'unresolved':
            return 'structure: readings tie' if not row.get('unknown') else 'grounding: unknown word'
        if why == 'ambiguous generalization':
            return 'safety hold: concept undecided here'
        if why == 'needs recheck':
            return 'grounding: contradicted by the person, to be taught again'
        return 'safety hold'
    if o == 'tool_failed':
        return 'tool model: the action did not do what was remembered'
    if o == 'wrong':
        return {'cards': 'grounding: wrong cards', 'result': 'tool model: wrong result'}.get(row.get('reason'), 'grounding')
    if o == 'error':
        return 'evaluator/env'
    return 'planning'


def readable_atom(a):
    try:
        t = ast.literal_eval(a)
    except (ValueError, SyntaxError):
        return a
    if isinstance(t, tuple) and len(t) == 4 and t[0] == 'U':
        return f"{ATTR.get(t[2], t[2])}={t[3]}"
    return a


class Session:
    def __init__(self, root, seed=1, source='human', clock=None, body='board', mind=None, transfer=True):
        self.transfer = transfer                          # TRANSFER_PROTOCOL.md (PASS, narrow)
        self.mind = Path(mind) if mind else Path(root) / 'mind'   # one mind may live in several bodies' sandboxes
        self.body = body                                  # 'board' (with a screen) or 'fs' (a sandbox folder; no screen yet)
        self.root = Path(root)
        self.source = source                              # 'human' for a real person; a scripted pilot uses 'pilot'
        self.clock = clock or datetime.datetime.now       # a pilot may simulate days passing
        self.root.mkdir(parents=True, exist_ok=True)
        self.sp = self.root / 'state.json'
        self.state = json.loads(self.sp.read_text(encoding='utf-8')) if self.sp.exists() else {'session': 0, 'seed': seed, 'taught': {}, 'k': 0}
        if body == 'board':
            self.home = BoardWorkspace(self.root / 'board', create=not (self.root / 'board').exists())
        elif body == 'view':
            from ..eval.tutor_life import make_home
            self.home = make_home('view', self.root, seed, 100 + self.state['session'])
        elif body == 'desk':
            from ..world.desk_world import DeskWorkspace
            self.home = DeskWorkspace(self.root / 'desk', create=not (self.root / 'desk').exists(), seed=seed)
        elif body == 'clime':
            from ..world.clime_world import ClimeWorkspace
            self.home = ClimeWorkspace(self.root / 'clime', create=not (self.root / 'clime').exists(), seed=seed)
        else:
            from ..eval.tutor_life import FS_FOLDERS
            from ..world.fs_world import Workspace
            new = not (self.root / 'home').exists()
            self.home = Workspace(self.root / 'home', create=new)
            if new:
                for d in FS_FOLDERS:
                    (self.home.root / d).mkdir()
        self.home.drift = frozenset()
        self.person = HumanPerson(self.home)
        self.job = None
        self.messages = []
        self.lock = threading.Lock()
        if self.state['session'] == 0:
            self.new_session()

    # ------------------------------------------------------------ bookkeeping
    def save(self):
        self.sp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding='utf-8')

    def log(self, **row):
        row = {'at': self.clock().isoformat(timespec='seconds'), 'session': self.state['session'], 'source': self.source, **row}
        with open(self.root / 'log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + '\n')
        return row

    def say(self, text):
        self.messages.append({'at': time.strftime('%H:%M:%S'), 'text': text})
        self.messages = self.messages[-40:]

    @property
    def grants(self):
        """The session's capabilities: given by the one who gives the commands (here, all the body lists)."""
        return {c: True for c in set(getattr(self.home, 'CAPABILITY', {}).values())}

    def grounder(self, with_person=True):
        return make_learner(self.home, self.mind, person=self.person if with_person else None, source=self.source, transfer=self.transfer,
                        caps=self.grants)   # the one giving the commands grants the body's capabilities

    def new_session(self):
        """A new day: new cards arrive (some already in trays); what was taught stays only in ATANOR's memory."""
        self.state['session'] += 1
        n = self.state['session']
        before = set(self.home.existing())
        if self.body == 'board':
            rng = random.Random(f"user-board-{self.state['seed']}-{n}")
            self.home.add_cards({f's{n}c{k}': {'mark': rng.choice(MARKS), **({'tray': rng.choice(sorted(TRAYS))} if rng.random() < 0.5 else {})}
                                 for k in range(CARDS_PER_SESSION)})
        elif self.body == 'clime':                         # new bays arrive; the weather moves (outside changes)
            from ..eval.tutor_life import clime_inflow
            self.home.add_bays(clime_inflow(self.state['seed'], 100 + n))
            self.home.tick()
        elif self.body == 'desk':                          # new items arrive; time passes (outside changes, sent drafts)
            from ..eval.tutor_life import desk_inflow
            self.home.add_items(desk_inflow(self.state['seed'], 100 + n))
            self.home.tick()
        elif self.body == 'view':                          # the screen is set up again each day (others changed it)
            from ..eval.tutor_life import make_home
            drift = self.home.drift
            self.home = make_home('view', self.root, self.state['seed'], 100 + n)
            self.home.drift = drift
            self.person.home = self.home
        else:
            from ..eval.life_gen import inflow as file_inflow
            file_inflow(self.home, 100 + n, self.state['seed'])
        new = sorted(set(self.home.existing()) - before)
        born = self.state.setdefault('born', {})
        for o in new:
            born[o] = n                                    # when each object first appeared (for reuse on new objects)
        self.save()
        self.log(event='session', new_cards=new)
        self.say(f'{n}번째 세션입니다. 새 대상 {len(new)}개가 들어왔습니다.')

    def setup_scene(self, scene, reason=''):
        """The teacher lays out the materials (like a person arranging cards before a lesson): the body's own scene
        setup, not a tool action and not a write to ATANOR. Recorded as teacher_scene_setup in the session log only."""
        if self.body != 'view':
            raise ValueError('scene setup is provided for the screen body')
        from ..world.view_world import ViewWorkspace
        import shutil
        drift = self.home.drift
        data = self.home.data
        shutil.rmtree(self.root / 'view')
        self.home = ViewWorkspace(self.root / 'view', data, spec=scene)
        self.home.drift = drift
        self.person.home = self.home
        self.log(event='teacher_scene_setup', scene=scene, reason=reason)

    def lesson_id(self):
        self.state['k'] += 1
        self.save()
        return f"H{self.state['session']}.{self.state['k']}"

    # ------------------------------------------------------------ jobs (each runs in its own thread)
    def start(self, kind, **kw):
        with self.lock:
            if self.job and self.job.is_alive():
                return False
            self.job = threading.Thread(target=self._run, args=(kind, kw), daemon=True)
            self.job.start()
            return True

    def _run(self, kind, kw):
        try:
            getattr(self, 'job_' + kind)(**kw)
        except Cancelled:
            self.say('취소했습니다.')
            self.log(event='cancelled', job=kind)
        except Exception as e:                                    # recorded as an evaluator/environment failure
            self.say(f'오류: {e}')
            self.log(event=kind, outcome='error', error=traceback.format_exc()[-800:], failure_class='evaluator/env')

    def job_teach(self):
        lid = self.lesson_id()
        h0 = Counter(self.person.help)
        g = self.grounder()
        self.say('가르칠 카드를 몇 장 가리켜 주세요(카드를 눌러 고른 뒤 "다 가리켰어요").')
        sc = g.learn_selection(lid)
        if not sc:
            self.say('가리킨 카드들에 공통점이 없어 기준을 세우지 못했습니다.')
            self.log(event='lesson', lesson=lid, outcome='no criterion', failure_class='grounding: no shared criterion')
            return
        self.say('이제 그 카드들에 할 행동을 한 장에만 직접 보여 주세요.')
        ac = g.learn_action(lid)
        acted, failed = g.apply(sc['content'], ac['content'], lid)
        verdict = self.person.ask('confirm', acted=[o for o, _ in acted], failed=[o for o, _ in failed],
                                  note='ATANOR가 나머지 카드에 같은 행동을 했습니다. 맞나요?')
        ok = bool(verdict['ok'])
        g.reply(ok, used=[sc['id'], ac['id']], reason=verdict.get('reason'))
        row = {'event': 'lesson', 'lesson': lid, 'concept': sc['content']['concept'], 'action': ac['content']['action'],
               'criterion': [readable_atom(a) for a in sc['content']['atoms']], 'alternatives': len(sc['content'].get('alternatives', [])),
               'acted': [o for o, _ in acted], 'failed': [o for o, _ in failed], 'confirmed': ok,
               'help': dict(Counter(self.person.help) - h0)}
        if not ok:
            row.update(reason=verdict.get('reason'), outcome='wrong', failure_class=classify({'outcome': 'wrong', 'reason': verdict.get('reason')}))
            self.say('틀렸다고 기록했습니다. 이 수업의 기준과 행동은 근거 없는 채로 남지 않고, 다음 수업에서 다시 배울 수 있습니다.')
            self.log(**row)
            return
        names = self.person.ask('name', concept=sc['content']['concept'], action=ac['content']['action'],
                                note='원하면 이 선택과 이 행동에 이름(아무 기호나)을 붙여 주세요. 비워 두어도 됩니다.')
        for part, node in (('selection', sc['content']['concept']), ('action', ac['content']['action'])):
            sym = (names.get(part) or '').strip()
            if sym:
                g.bind(sym, node, lid, replace=True)
                self.state['taught'][sym] = {'session': self.state['session'], 'date': self.clock().date().isoformat(), 'part': part,
                                             'node': node, 'lesson': lid}
                row.setdefault('named', {})[part] = sym
        self.save()
        row['outcome'] = 'success'
        self.log(**row)
        self.say('배운 것을 기억에 넣었습니다(오른쪽 "기억"에서 근거와 함께 볼 수 있습니다).')

    def job_name(self, part, phrase):
        """An English (or any) phrase for something already shared: point / show while saying it."""
        words = phrase.lower().split()
        if not words:
            return
        lid = self.lesson_id()
        g = self.grounder()
        if part == 'selection':
            self.say(f'"{phrase}"가 가리키는 카드를 몇 장 가리켜 주세요.')
            sc = g.known_concept(lid, words) or g.learn_selection(lid)
            if not sc:
                self.say('기준을 세우지 못했습니다.')
                self.log(event='name', lesson=lid, phrase=words, outcome='no criterion', failure_class='grounding: no shared criterion')
                return
            node, known = sc['content']['concept'], sc['content'].get('lesson') != lid
            picks = g.extension(sc['content']['atoms'], g.feats())
            seen = self.person.ask('show', objects=picks, note=f'"{phrase}"는 이 카드들을 말하는 건가요?')
            ev = g.reply(bool(seen['ok']), used=[sc['id']], reason='cards')
            if not seen['ok']:                             # a name is attached only to what the person agrees it means
                self.say('붙이지 않았습니다. 그 기준은 다시 확인이 필요한 것으로 남겼습니다.')
                self.log(event='name', lesson=lid, phrase=words, node=node, known_concept=known, outcome='wrong',
                         reason='cards', failure_class='grounding: wrong cards')
                return
        else:
            self.say(f'"{phrase}"라고 말하며 한 장에 그 행동을 보여 주세요.')
            ac = g.learn_action(lid)
            node, known = ac['content']['action'], ac.get('v', 1) > 1
        g.name_phrase(words, node, lid)
        self.state['taught'][' '.join(words)] = {'session': self.state['session'], 'date': self.clock().date().isoformat(),
                                                 'part': part, 'node': node, 'lesson': lid, 'phrase': True}
        self.save()
        self.log(event='name', lesson=lid, part=part, phrase=words, node=node, known_concept=known, outcome='success')
        self.say(f'"{phrase}"를 {"이미 배운" if known else "새로 배운"} {node}에 붙였습니다.')

    def job_command(self, text, alone, recalled=None):
        words = text.lower().split()
        if not words:
            return
        h0 = Counter(self.person.help)
        g = self.grounder(with_person=not alone)
        res = g.obey(words, task=f"C{self.state['session']}.{self.state['k']}")
        if recalled:
            g.drop_pending(words)
        row = {'event': 'command', 'words': words, 'alone': alone, 'recalled': recalled, 'why': res.get('why'), 'unknown': res.get('unknown', []),
               'acted': res.get('acted', []), 'failed': res.get('failed', []), 'used': res.get('used'), 'retrieved_as': res.get('retrieved_as')}
        if not res.get('ok') and not res.get('acted') and not res.get('failed'):
            row['outcome'] = 'held'
            self.say('지난번에 틀렸다고 하신 것이라, 다시 가르쳐 주실 때까지 하지 않았습니다.' if res.get('why') == 'needs recheck'
                     else '확실하지 않아 하지 않았습니다(보류).')
        elif res.get('failed'):
            row['outcome'] = 'tool_failed'
            self.say('기억한 행동이 이번에는 되지 않았습니다.')
        else:
            verdict = self.person.ask('judge', acted=row['acted'], note='이 명령을 이렇게 했습니다. 맞나요?')
            row['outcome'] = 'success' if verdict['ok'] else 'wrong'
            row['reason'] = verdict.get('reason')
            g.reply(bool(verdict['ok']), used=res.get('used') or (), reason=verdict.get('reason'))
        taught = {w: self.state['taught'][w] for w in self.state['taught'] if all(x in words for x in w.split())}
        row['taught_words'] = {w: {'session': t['session'], 'date': t['date']} for w, t in taught.items()}
        first = min((t['session'] for t in taught.values()), default=None)
        born = self.state.get('born', {})
        row['acted_new_cards'] = [o for o in row['acted'] if first is not None and born.get(o, 0) > first]
        row['failure_class'] = classify(row)
        row['help'] = dict(Counter(self.person.help) - h0)
        self.log(**row)

    def job_recall(self, index=0):
        """The person is back: ATANOR asks about a command it held while alone; if still wanted, it does it now, with
        the person there to answer its questions."""
        g = self.grounder()
        items = g.pending()
        if index >= len(items):
            return
        item = items[index]
        ans = self.person.ask('recall', words=item['words'], why=item['why'], note=f"혼자일 때 하지 못한 일입니다: \"{' '.join(item['words'])}\". 아직 원하시나요?")
        if not ans.get('yes'):
            g.drop_pending(item['words'])
            self.log(event='recall', words=item['words'], held_why=item['why'], outcome='no longer wanted')
            return
        self.job_command(' '.join(item['words']), alone=False, recalled=item['why'])

    # ------------------------------------------------------------ views
    def memory_view(self):
        mem = Memory(self.mind, events_readable=True)
        ev = {e['id']: e for e in mem.events.all()}
        names = {}
        for c in mem.claims.claims('denotes'):
            names.setdefault(c['content']['refers'], []).append(c['content']['symbol'])
        phrases = {}
        for c in mem.claims.claims('phrase'):
            phrases.setdefault(c['content']['refers'], []).append(' '.join(c['content']['words']))
        out = []
        for c in mem.claims.claims():
            if c['kind'] not in ('selects', 'effect'):
                continue
            k = c['content']
            node = k.get('concept') or k.get('action')
            kinds = Counter(ev[e]['kind'] for e in c['support'] if e in ev)
            contrasts = [f"{ev[e]['object']}:{'예' if ev[e]['answer'] else '아니오'}" for e in c['support'] if e in ev and ev[e]['kind'] == 'contrast']
            item = {'id': c['id'], 'v': c['v'], 'kind': c['kind'], 'node': node, 'status': c['status'], 'origin': c['origin'],
                    'source': (c.get('scope') or {}).get('source'), 'confidence': round(ClaimLedger.confidence(c), 2),
                    'support': dict(kinds), 'contrasts': contrasts, 'counter': len(c['counter']),
                    'names': sorted(set(names.get(node, []))), 'phrases': sorted(set(phrases.get(node, []))), 'lesson': k.get('lesson')}
            if c['kind'] == 'selects':
                item['criterion'] = [readable_atom(a) for a in k['atoms']]
                item['alternatives'] = [[readable_atom(a) for a in alt] for alt in k.get('alternatives', [])][:4]
            else:
                item['tool'] = k['tool']
                item['template'] = k['template']
                item['gained'] = [readable_atom(a) for a in k['gained']]
            out.append(item)
        return out

    def view(self):
        for _ in range(5):
            try:
                cards = self.home._read()['cards'] if self.body == 'board' else {}
                break
            except (OSError, ValueError):
                time.sleep(0.05)
        else:
            cards = {}
        try:
            memory = self.memory_view()
        except (OSError, ValueError):
            memory = []
        return {'session': self.state['session'], 'cards': cards, 'trays': TRAYS, 'marks': MARKS, 'levels': LEVELS,
                'tools': self.home.tools(), 'pending': self.person.pending, 'busy': bool(self.job and self.job.is_alive()),
                'messages': self.messages, 'memory': memory, 'taught': self.state['taught'],
                'unfinished': len(json.loads((self.mind / 'pending.json').read_text(encoding='utf-8'))) if (self.mind / 'pending.json').exists() else 0}


def make_handler(sess):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype='application/json; charset=utf-8'):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ('/', '/index.html'):
                return self._send(200, PAGE.read_bytes(), 'text/html; charset=utf-8')
            if self.path == '/api/state':
                return self._send(200, sess.view())
            self._send(404, {'error': 'not found'})

        def do_POST(self):
            n = int(self.headers.get('Content-Length') or 0)
            body = json.loads(self.rfile.read(n) or b'{}')
            if self.path == '/api/answer':
                if sess.person.pending is None:
                    return self._send(409, {'error': 'no question pending'})
                sess.person.answers.put(body)
                return self._send(200, {'ok': True})
            if self.path == '/api/cancel':
                if sess.person.pending is not None:
                    sess.person.answers.put({'cancel': True})
                return self._send(200, {'ok': True})
            if self.path == '/api/start':
                kind = body.pop('job', None)
                if kind == 'session':
                    if sess.job and sess.job.is_alive():
                        return self._send(409, {'error': 'busy'})
                    sess.new_session()
                    return self._send(200, {'ok': True})
                if kind not in ('teach', 'name', 'command', 'recall'):
                    return self._send(400, {'error': 'unknown job'})
                return self._send(200 if sess.start(kind, **body) else 409, {'ok': True})
            self._send(404, {'error': 'not found'})
    return H


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=str(DEFAULT_ROOT))
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--seed', type=int, default=1)
    a = ap.parse_args(argv)
    sess = Session(a.root, a.seed)
    srv = ThreadingHTTPServer(('127.0.0.1', a.port), make_handler(sess))
    print(f'ATANOR board tutor on http://127.0.0.1:{a.port}  sandbox: {a.root}', flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
