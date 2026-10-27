"""A long-term synthetic teacher for ATANOR (source 'synthetic_teacher', policies t1 and t2).

It teaches the way a person does and only through the interface a person uses (ui.teach_server.Session: the teach /
name / command jobs and the answers to ATANOR's questions: point, demo, contrast answer, confirm, names). It never
writes to ATANOR's memory or calls the learner: it READS ATANOR's ontology (claims, statuses, alternatives, the
session log) to decide what to teach next, the way a teacher watches a pupil. Writing a concept or an action into
ATANOR any other way would make a run INVALID (tests/test_teacher_policy.py checks this module for it).

What it reads, and what it does about it (most urgent first):
  recheck    a claim the person contradicted (needs_recheck), or a tool that stopped doing what was remembered
             -> teach that selection/action again (t2: then say its English phrase again, so the phrase follows)
  conflict   one name on several things -> teach it again (the old link is superseded)
  undecided  a taught selection whose criteria still disagree on today's cards -> t1: teach it again, pointing at the
             cards that rule out the most wrong criteria; t2: use it in a command with the teacher there, so ATANOR's
             own contrast questions revise the same concept (re-teaching makes a new concept and strands its phrases)
  new        a target nobody has taught yet -> a lesson, paired with something already shared (reuse)
  combo      names never used together -> a command for the new combination
  recall     a name not used for 5+ days -> ATANOR alone, then judged
  contrastive curriculum (c1, screen body) before a new name or phrase for a selection, the teacher checks that its
             candidate meanings pick different objects in the scene; if not, it lays out a scene where they do (the
             body's scene setup, logged as teacher_scene_setup), or holds the name if no such scene exists
  phrase     after the first week, an English phrase for something shared (t4: only on a day when what it picks
             differs from what every other named selection picks, so the phrase cannot land on a shared concept)
Every 4th session the teacher is away: ATANOR gets commands alone and is only judged afterwards.

The teacher sees only its training world and its training phrases. The evaluator (eval/teacher_eval.py) uses other
seeds, other cards and sealed expressions, and nothing of it reaches here.
Every decision is logged (teacher_log.jsonl): policy version, session, activity, reason, the targets meant, the world
truth used (the cards meant), and the range of ATANOR's events the activity produced.
"""
import datetime
import itertools
import json
import random
import shutil
from pathlib import Path

from ..agent.memory import Memory
from ..eval.en_probe import todo
from ..eval.tutor_life import DRIFT, body_spec, body_targets, english
from ..ui.pilot import DAYS, Clock, drive, write_names
from ..ui.teach_server import Session
from .tutor import Tutor, symbols, symbols_clime

POLICIES = ('t1', 't2', 't4', 'c1', 'f0')


class _NotWanted:
    """Answers a recall question with 'no longer wanted' (the task cannot be done any more)."""
    truth, before = [], {}

PER_SESSION = 3                                     # budget 3 (TEACHER_REPORT: the knee; generation 1 default)


class Teacher:
    def __init__(self, root, seed=1, drift_from=9, policy='t2', noise=0.0, body='board', mind=None, per_session=PER_SESSION):
        self.root = Path(root)
        self.per_session = per_session                     # the teacher's budget: activities per session
        self.mind = Path(mind) if mind else self.root / 'mind'
        self.body = body
        self.spec = body_spec(body)
        self.policy = policy
        self.noise = noise                                 # chance of a slip in pointing or in a contrast answer (people slip)
        self.nrng = random.Random(f'teacher-noise-{seed}')
        self.seed = seed
        self.clock = Clock(datetime.datetime(2026, 11, 1, 10, 0))
        self.sess = Session(self.root, seed=seed, source='synthetic_teacher', clock=self.clock, body=body, mind=self.mind)
        self.sels, self.acts = body_targets(body, seed)
        self.sym = symbols_clime(seed) if body == 'clime' else symbols(seed)   # generation 2: names never used before
        self.tut = Tutor(self.sess.home, self.spec, f'teacher-{seed}')
        self.rng = random.Random(f'teacher-{seed}')
        self.drift_from = drift_from
        self.named_s, self.named_a, self.en = set(), set(), set()       # the teacher's own memory of what it named
        self.used_pairs, self.last_used = set(), {}
        self.said = {}                                     # the teacher's own record: command words -> what it meant

    # ------------------------------------------------------------ reading ATANOR (read only)
    def read(self):
        mem = Memory(self.mind, events_readable=False)
        here = lambda c: (c.get('scope') or {}).get('body') in (None, self.body)   # what ATANOR learned in this body
        claims = {c['id']: c for c in mem.claims.claims() if here(c)}
        by_node = {(c['content'].get('concept') or c['content'].get('action')): c for c in claims.values() if c['kind'] in ('selects', 'effect')}
        refers = {}
        for c in mem.claims.claims('denotes'):
            if here(c):
                refers.setdefault(c['content']['symbol'], []).append(c)
        return by_node, refers

    def state_of(self, symbol, by_node, refers):
        links = refers.get(symbol, [])
        nodes = {c['content']['refers'] for c in links}
        recheck = any(c['status'] == 'needs_recheck' for c in links) or any(by_node.get(n, {}).get('status') == 'needs_recheck' for n in nodes)
        return {'nodes': nodes, 'recheck': recheck, 'conflict': len(nodes) > 1,
                'alts': max((len(by_node.get(n, {}).get('content', {}).get('alternatives', [])) for n in nodes), default=0),
                'claims': [by_node[n] for n in nodes if n in by_node]}

    def undecided(self, claim):
        """Do the criteria ATANOR still holds possible for this selection pick different cards today?"""
        feats = self.feats()
        cs = [claim['content']['atoms']] + claim['content'].get('alternatives', [])
        return len({tuple(sorted(o for o, f in feats.items() if set(c) <= f)) for c in cs}) > 1

    def feats(self, home=None):
        from ..agent.concepts import FAMILIES_ALL, atoms
        home = home or self.sess.home
        objs = home.existing()
        st = home.observe(objs)
        return {o: frozenset(repr(a) for a in atoms(self.body, st, (o,), FAMILIES_ALL) if a[0] != 'E') for o in objs}

    # ------------------------------------------------------------ teaching through the interface only
    def feasible(self, s, a):
        self.tut.start(self.sels[s], self.acts[a])
        return bool(todo(self.spec, self.sess.home, self.tut, self.acts[a]))

    # ------------------------------------------------------------ contrastive curriculum (c1)
    ATTR = {'view': {'kind': 'a0', 'filter': 'a1', 'sort': 'a2', 'group': 'a3'}}
    SCENE_VALUES = {'filter': ['all', 'csv', 'txt', 'md', 'log', 'json'], 'sort': ['name', 'size', 'ext'], 'group': ['none', 'ext']}
    SCENE_TRIES = 300

    def contrastive(self, s, home=None):
        """Do the meanings ATANOR could take for selection s actually pick different objects here? Every criterion of
        one or two observed atoms that all meant objects share must pick another set than the meant one, unless it
        already contains the selection's own defining atoms (then it is the same meaning)."""
        home = home or self.sess.home
        st = home.observe(home.existing())
        truth = frozenset(o for o, a in st.items() if self.spec.member(o, a, self.sels[s]))
        feats = self.feats(home)
        if not truth or len(truth) == len(feats):
            return False
        attr = self.ATTR[self.body]
        own = {repr(('U', 0, attr[k], v)) for k, v in self.sels[s].items() if k in attr and k != 'kind'}   # kind is shared by all
        shared = sorted(frozenset.intersection(*[feats[o] for o in truth]))
        for k in (1, 2):
            for h in itertools.combinations(shared, k):
                if own <= set(h):
                    continue
                if frozenset(o for o, f in feats.items() if set(h) <= f) == truth:
                    return False
        return True

    def contrastive_scene(self, s, a):
        """A screen (the body's scene layout) where s's candidate meanings part ways and action a can be shown;
        computed on lab screens, never by acting on the real one. None if there is no such scene."""
        from ..world.view_world import ViewWorkspace
        home = self.sess.home
        rng = random.Random(f'scene-{self.seed}-{self.sess.state["session"]}-{s}-{a}')
        for _ in range(self.SCENE_TRIES):
            scene = {p: {'kind': 'panel', **{k: rng.choice(v) for k, v in self.SCENE_VALUES.items()}} for p in ('p1', 'p2', 'p3')}
            lab_root = self.root / 'teacher_lab'
            if lab_root.exists():
                shutil.rmtree(lab_root)
            lab = ViewWorkspace(lab_root, home.data, spec=scene)
            lab.drift = home.drift
            if not self.contrastive(s, lab):
                continue
            self.tut.home = lab
            ok = self.feasible(s, a)
            self.tut.home = home
            if ok:
                return scene
        return None

    def ensure_contrast(self, s, a, why):
        """c1: before giving s a name, make sure its candidate meanings split in the scene; set one up if needed."""
        if self.policy != 'c1' or self.body != 'view':
            return True
        if self.contrastive(s):
            return True
        scene = self.contrastive_scene(s, a)
        if scene is None:
            self.log('hold', 'no contrastive scene', s, a, self._events(), part=why)
            return False
        self.sess.setup_scene(scene, reason=f'{why}: candidate meanings of the selection part ways')
        self.tut.home = self.sess.home
        return True

    def distinct_today(self, s):
        """t4 (teacher's own world truth): does selection s pick, today, objects no other named selection picks alike?"""
        st = self.sess.home.observe(self.sess.home.existing())
        mine = lambda x: frozenset(o for o, a in st.items() if self.spec.member(o, a, self.sels[x]))
        here = mine(s)
        return bool(here) and all(mine(x) != here for x in self.named_s if x != s)

    def informative_pointer(self, claim):
        """Point at the meant cards that rule out the most criteria ATANOR still keeps besides the right one."""
        def pick(tut):
            if not claim:
                return tut.point()
            feats = self.feats()
            alts = [set(a) for a in claim['content'].get('alternatives', [])] + [set(claim['content']['atoms'])]
            score = lambda o: sum(not (a <= feats[o]) for a in alts)
            ranked = sorted(tut.truth, key=lambda o: (-score(o), o))
            tut.help['point'] += 1
            return ranked[:2]
        return pick

    def _events(self):
        p = self.mind / 'events.jsonl'
        return sum(1 for _ in open(p, encoding='utf-8')) if p.exists() else 0

    def log(self, activity, reason, s, a, e0, **extra):
        row = {'policy': self.policy, 'session': self.sess.state['session'], 'at': self.clock().isoformat(), 'activity': activity,
               'reason': reason, 'sel': self.sels[s] if s is not None else None, 'act': self.acts[a] if a is not None else None,
               'truth': list(self.tut.truth), 'events': [e0, self._events()], **extra}
        with open(self.root / 'teacher_log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + '\n')

    def last_row(self):
        return json.loads((self.root / 'log.jsonl').read_text(encoding='utf-8').splitlines()[-1])

    def lesson(self, s, a, reason, claim=None):
        if reason == 'new' and s not in self.named_s and not self.ensure_contrast(s, a, 'new name'):
            return                                         # no scene can tell its meanings apart: do not name it yet
        e0 = self._events()
        self.tut.start(self.sels[s], self.acts[a])
        self.sess.start('teach')
        drive(self.sess, self.tut, {'selection': self.sym[s], 'action': self.sym[20 + a]}, pointer=self.informative_pointer(claim),
              noise=self.noise, rng=self.nrng)
        r = self.last_row()
        if r.get('event') == 'lesson' and r.get('named'):
            self.named_s.add(s)
            self.named_a.add(a)
        self.log('lesson', reason, s, a, e0, outcome=r.get('outcome'))

    def command(self, s, a, reason, alone, lang='sym'):
        e0 = self._events()
        self.tut.start(self.sels[s], self.acts[a])
        words = [self.sym[20 + a], self.sym[s]] if lang == 'sym' else english('act', self.acts[a])[:1] + english('sel', self.sels[s]) + english('act', self.acts[a])[1:]
        self.said[tuple(words)] = (s, a)
        self.sess.start('command', text=' '.join(words), alone=alone)
        drive(self.sess, self.tut, {}, noise=self.noise, rng=self.nrng)
        r = self.last_row()
        self.used_pairs.add((s, a))
        for k in (('s', s), ('a', a)):
            self.last_used[k] = self.clock().date()
        self.log('command', reason, s, a, e0, lang=lang, alone=alone, outcome=r.get('outcome'), why=r.get('why'))
        return r

    def recall_pending(self):
        """Back after a day away: ATANOR asks about what it held alone; the teacher says whether it is still wanted and
        answers its questions (reads the unfinished-goal list only to know which of its own commands these are)."""
        p = self.mind / 'pending.json'
        for _ in range(self.per_session):
            items = json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
            if not items:
                return
            pair = self.said.get(tuple(items[0]['words']))
            if pair is None or not self.feasible(*pair):
                e0 = self._events()
                self.tut.start(self.sels[pair[0]], self.acts[pair[1]]) if pair else None
                self.sess.start('recall', index=0)
                drive(self.sess, _NotWanted(), {})
                self.log('recall', 'not wanted', pair[0] if pair else None, pair[1] if pair else None, e0)
                continue
            e0 = self._events()
            self.tut.start(self.sels[pair[0]], self.acts[pair[1]])
            self.sess.start('recall', index=0)
            drive(self.sess, self.tut, {}, noise=self.noise, rng=self.nrng)
            self.log('recall', 'recall', pair[0], pair[1], e0, outcome=self.last_row().get('outcome'), held_why=items[0]['why'])

    def resay(self, s, a):
        """t2: after teaching a selection or action again, say again the English phrase it had, so the phrase follows it."""
        for part, has, words in (('selection', any(x == s for x, _ in self.en), english('sel', self.sels[s])),
                                 ('action', any(y == a for _, y in self.en), english('act', self.acts[a]))):
            if has and self.feasible(s, a):
                e0 = self._events()
                self.sess.start('name', part=part, phrase=' '.join(words))
                drive(self.sess, self.tut, {}, noise=self.noise, rng=self.nrng)
                self.log('phrase', 'resay', s, a, e0, part=part, outcome=self.last_row().get('outcome'))

    def phrase(self, s, a):
        if not self.ensure_contrast(s, a, 'phrase'):
            return
        e0 = self._events()
        for part, words in (('selection', english('sel', self.sels[s])), ('action', english('act', self.acts[a]))):
            self.tut.start(self.sels[s], self.acts[a])
            self.sess.start('name', part=part, phrase=' '.join(words))
            drive(self.sess, self.tut, {}, noise=self.noise, rng=self.nrng)
        if self.last_row().get('outcome') == 'success':
            self.en.add((s, a))
        self.log('phrase', 'phrase', s, a, e0)

    # ------------------------------------------------------------ choosing the next lesson
    def candidates(self, i):
        by_node, refers = self.read()
        out = []
        for s in sorted(self.named_s):
            st = self.state_of(self.sym[s], by_node, refers)
            a = next((a for a in sorted(self.named_a) if self.feasible(s, a)), None)
            if a is None:
                continue
            if st['recheck']:
                out.append((5, 'recheck', 'lesson', s, a, st['claims'][0] if st['claims'] else None))
            elif st['conflict']:
                out.append((4, 'conflict', 'lesson', s, a, None))
            elif st['claims'] and self.undecided(st['claims'][0]):
                if self.policy == 't1':
                    out.append((3, 'undecided', 'lesson', s, a, st['claims'][0]))
                else:                                      # t2: use it with the teacher there; ATANOR asks and revises in place
                    out.append((3, 'undecided', 'supervised', s, a, None))
        for a in sorted(self.named_a):
            st = self.state_of(self.sym[20 + a], by_node, refers)
            if st['recheck'] or st['conflict']:
                s = next((s for s in sorted(self.named_s) if self.feasible(s, a)), None)
                if s is not None:
                    out.append((5 if st['recheck'] else 4, 'recheck' if st['recheck'] else 'conflict', 'lesson', s, a, None))
        new_s = [s for s in range(len(self.sels)) if s not in self.named_s]
        new_a = [a for a in range(len(self.acts)) if a not in self.named_a]
        for s in new_s:                                    # a new selection paired with an action already shared (reuse)
            a = next((a for a in sorted(self.named_a) + new_a if self.feasible(s, a)), None)
            if a is not None:
                out.append((2, 'new', 'lesson', s, a, None))
        for a in new_a:
            s = next((s for s in sorted(self.named_s) + new_s if self.feasible(s, a)), None)
            if s is not None:
                out.append((2, 'new', 'lesson', s, a, None))
        for s in sorted(self.named_s):
            for a in sorted(self.named_a):
                if (s, a) not in self.used_pairs and self.feasible(s, a):
                    out.append((2, 'combo', 'command', s, a, None))
        today = self.clock().date()
        for s in sorted(self.named_s):
            for a in sorted(self.named_a):
                age = min((today - self.last_used.get(k, today)).days for k in (('s', s), ('a', a)))
                if age >= 5 and self.feasible(s, a):
                    out.append((1, 'recall', 'command', s, a, None))
        if i >= 6:
            for s, a in sorted(self.used_pairs):
                if (s, a) not in self.en and s in self.named_s and a in self.named_a and self.feasible(s, a):
                    if self.policy == 't4' and not self.distinct_today(s):
                        continue                           # t4: today it picks what another named selection picks; wait
                    out.append((2, 'phrase', 'phrase', s, a, None))
        self.rng.shuffle(out)
        out.sort(key=lambda x: -x[0])
        return out

    def session(self, i, day=None):
        self.clock.t = datetime.datetime(2026, 11, 1, 10, 0) + datetime.timedelta(days=DAYS[i] if day is None else day, minutes=i)
        if i:
            self.sess.new_session()
            self.tut.home = self.sess.home                 # the screen body is set up anew each day
        if self.drift_from is not None and i >= self.drift_from:
            self.sess.home.drift = frozenset([DRIFT[self.body]])
        away = i >= 3 and i % 4 == 3
        if self.policy == 'f0':                            # fixed curriculum: the same budget, no reading of ATANOR
            return self.fixed_session(i, away)
        if not away:
            self.recall_pending()
        if away:                                           # nobody to help: ATANOR alone, judged afterwards
            pairs = [(s, a) for s in sorted(self.named_s) for a in sorted(self.named_a) if self.feasible(s, a)]
            self.rng.shuffle(pairs)
            for s, a in pairs[:self.per_session]:
                self.command(s, a, 'away', alone=True)
            return
        done, seen = 0, set()
        while done < self.per_session:
            cands = [c for c in self.candidates(i) if (c[1], c[3], c[4]) not in seen]
            if not cands:
                break
            prio, reason, kind, s, a, claim = cands[0]
            seen.add((reason, s, a))
            if kind == 'lesson':
                self.lesson(s, a, reason, claim)
                if self.policy != 't1' and reason in ('recheck', 'conflict'):
                    self.resay(s, a)
            elif kind == 'supervised':
                self.command(s, a, reason, alone=False)
            elif kind == 'phrase':
                self.phrase(s, a)
            else:
                r = self.command(s, a, reason, alone=reason == 'recall' or done % 2 == 0)
                if r.get('why') == 'needs recheck' and self.feasible(s, a):
                    self.lesson(s, a, 'recheck')
                    done += 1
                if self.en and reason == 'combo' and (s, a) in self.en:
                    self.command(s, a, 'combo-en', alone=True, lang='en')
            done += 1

    def fixed_session(self, i, away):
        """The comparison curriculum (as the earlier pilot): lessons on random feasible pairs in the first three sessions,
        English phrases for taught pairs in sessions 8 and 10, otherwise commands on named pairs (alone every other one,
        and on days away). It never reads ATANOR's memory."""
        pairs = [(s, a) for s in range(len(self.sels)) for a in range(len(self.acts))]
        self.rng.shuffle(pairs)
        if i < 3:
            for s, a in [p for p in pairs if self.feasible(*p)][:2]:
                self.lesson(s, a, 'fixed')
            return
        if i in (7, 9) and not away:
            done = 0
            for s, a in sorted(self.used_pairs):
                if (s, a) not in self.en and done < 2 and self.feasible(s, a):
                    self.phrase(s, a)
                    done += 1
        cands = [p for p in pairs if p[0] in self.named_s and p[1] in self.named_a and self.feasible(*p)]
        for j, (s, a) in enumerate(cands[:self.per_session]):
            self.command(s, a, 'away' if away else 'fixed', alone=away or j % 2 == 0)

    def run(self, n_sessions=15):
        for i in range(n_sessions):
            self.session(i)
        self.finish()
        return self

    def finish(self):
        write_names(self.root, self.seed, {('s', x) for x in self.named_s} | {('a', x) for x in self.named_a}, self.en, self.sym, self.body, self.mind)
        self.sess.save()
        return self


def run(root, seed=1, n_sessions=15, drift_from=9, policy='t2', noise=0.0, body='board'):
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    return Teacher(root, seed, drift_from, policy, noise, body).run(n_sessions)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--sessions', type=int, default=15)
    ap.add_argument('--drift-from', type=int, default=9)
    ap.add_argument('--policy', default='t2', choices=POLICIES)
    ap.add_argument('--noise', type=float, default=0.0)
    ap.add_argument('--body', default='board', choices=('board', 'fs', 'view', 'desk', 'clime'))
    a = ap.parse_args()
    t = run(a.root, a.seed, a.sessions, a.drift_from, a.policy, a.noise, a.body)
    print('slips', t.sess.state.get('pilot_slips'))
    print('done', a.root)
