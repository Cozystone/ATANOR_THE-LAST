"""One life (mandate III, XV): one Self with one mind and one autobiography, living through the bodies in a fixed schedule,
in a new process for every stage and across abrupt kills.

Layout of a Self's folder: self.json (identity, written once), autobiography.jsonl (life/autobiography.py), mind/ (the one
mind), worlds/<body>/ (each body's world and its teacher's own notes; they persist).

A stage is one visit in a body (the teacher's session) or, at the end, one body's practice. Its place in the life is on
the record: a process finds the next stage from the autobiography alone. A stage a kill cut short is closed as
interrupted and the life goes on with the next one: the visit is over, and nothing it was doing is done again.

On every start, before anything else (WorldSession's order, shared_world/runtime.py, but an interruption does not halt
the life):
  1. complete results become experiences if the kill came before that was written (they are on the record, so nothing
     that happened is lost);
  2. an intent with no result is in doubt: the body may or may not have done it. The arguments are looked at again and
     what is found is recorded as an observation; a change found is an outside change of unknown cause (actor 'outside',
     no action), never this action's effect, and the action is never issued again;
  3. the models rebuilt from the experiences of the last checkpoint must have that checkpoint's digest.
"""
import json
import os
import pickle
import shutil
import uuid
from pathlib import Path

from ..agent.learners import after_course, name as learner_name
from ..core.durable import atomic_write, repair_jsonl
from ..rebuild import learner
from ..rebuild.experience import Store, experience
from ..rebuild.learner import call_experience, rebuild, seed_fitted
from ..teach.teacher_policy import Teacher
from .autobiography import Autobiography
from . import metabolism as metab
from .metabolism import GAIN, PRICES, Death, Metabolism

BODIES = ('board', 'fs', 'view', 'desk', 'clime', 'dye')
TEACHER_NOTES = ('named_s', 'named_a', 'en', 'used_pairs', 'last_used', 'said')


def schedule(bodies, sessions):
    """Sessions in turn, one a day (long_course's order), then each body's practice. Fixed before the life starts."""
    return [{'kind': 'session', 'body': b, 'i': i} for i in range(sessions) for b in bodies] + [{'kind': 'practice', 'body': b} for b in bodies]


def open_world(body, world):
    """The body as it is on disk, for looking only (no day starts, nothing arrives)."""
    if body == 'view':
        from ..world.view_world import ViewWorkspace
        return ViewWorkspace(world / 'view', None, create=False)
    if body == 'fs':
        from ..world.fs_world import Workspace
        return Workspace(world / 'home', create=False)
    mod, cls, sub = {'board': ('board_world', 'BoardWorkspace', 'board'), 'desk': ('desk_world', 'DeskWorkspace', 'desk'),
                     'clime': ('clime_world', 'ClimeWorkspace', 'clime'), 'dye': ('dye_world', 'DyeWorkspace', 'dye'),
                     'crumb': ('crumb_world', 'CrumbWorkspace', 'crumb'), 'spoke': ('spoke_world', 'SpokeWorkspace', 'spoke')}[body]
    return getattr(__import__(f'atanor_os.world.{mod}', fromlist=[cls]), cls)(world / sub, create=False)


def _seen(home):
    return home.observe(home.existing())


class Life:
    def __init__(self, root, seed, bodies=BODIES, sessions=15, genome=None):
        if learner_name() != 'next_explore':
            raise ValueError('a life is lived by the default learner (next_explore)')
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        if (self.root / '.dead').exists():
            raise Death('this life is over')
        self.lock_file = self._lock()
        self.identity = self._identity(seed, list(bodies), sessions, genome)
        self.metab = Metabolism(self.identity.get('genome'), enabled='genome' in self.identity)   # G: only a life born with a genome eats and dies
        metab.CURRENT = self.metab
        self.seed, self.bodies, self.sessions = seed, bodies, sessions
        self.stages = schedule(bodies, sessions)
        self.mind = self.root / 'mind'
        self.mind.mkdir(exist_ok=True)
        self.journal = Autobiography(self.root / 'autobiography.jsonl')
        self._raw_append = self.journal.append
        self.journal.append = self._append                 # every record that costs is paid for as it is written
        Store.autobiography = self.journal
        self._repair_files()
        self.rows = self.journal.rows()
        self.metab.replay(self.rows)
        if self.metab.dead:
            (self.root / '.dead').touch()
            raise Death('this life is over')
        self.journal.append('HOST', event='process_start', self_id=self.identity['id'], pid=os.getpid(), records=len(self.rows))
        self._restore_experiences()
        self._reconcile()
        self._restart_check()
        self.next = self._place()

    # ------------------------------------------------------------ who this is
    def _lock(self):
        """One process lives this life at a time (the lock goes when the process dies, however it dies)."""
        f = open(self.root / 'life.lock', 'a+b')
        if os.name == 'nt':
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f

    def _identity(self, seed, bodies, sessions, genome=None):
        p = self.root / 'self.json'
        if not p.exists():
            if (self.root / 'autobiography.jsonl').exists():
                raise ValueError('an autobiography with no self.json: a new identity is never made for an old life')
            atomic_write(p, json.dumps({'id': uuid.uuid4().hex, 'seed': seed, 'bodies': bodies, 'sessions': sessions,
                                        **({'genome': genome} if genome is not None else {})}))
        me = json.loads(p.read_text(encoding='utf-8'))
        if (me['seed'], me['bodies'], me['sessions']) != (seed, bodies, sessions):
            raise ValueError(f'this life was set up as {me}; its schedule does not change')
        return me

    def _repair_files(self):
        """What a kill can leave: a torn last line in the logs, and half-made lab folders (never part of the world)."""
        for p in self.root.rglob('*.jsonl'):
            if p.name != 'autobiography.jsonl':
                repair_jsonl(p)
        for pat in ('lab_*', 'practice-*'):
            for d in self.mind.glob(pat):
                shutil.rmtree(d, ignore_errors=True)
        for d in (self.root / 'worlds').glob('*/teacher_lab'):
            shutil.rmtree(d, ignore_errors=True)

    # ------------------------------------------------------------ energy (G_SURVIVAL_PLAN.md)
    def _append(self, kind, **data):
        seq = self._raw_append(kind, **data)
        price = self.metab.price_of(kind, data)
        if price:
            self._charge(kind, -price)
        return seq

    def _charge(self, why, delta):
        """The balance moves and is on the record; at zero the life ends here, on the record, for good."""
        if not self.metab.enabled:
            return
        try:
            self.metab.charge(why, delta)
        except Death:
            self._raw_append('INTEROCEPTION', E=round(self.metab.E, 4), why=why, delta=delta)
            self._raw_append('HOST', event='death', E=round(self.metab.E, 4), why=why, records=self.journal.seq)
            (self.root / '.dead').write_text(json.dumps({'E': self.metab.E, 'why': why}), encoding='utf-8')
            raise
        self._raw_append('INTEROCEPTION', E=round(self.metab.E, 4), why=why, delta=delta)

    # ------------------------------------------------------------ after a kill
    def _store(self):
        return Store(self.mind / 'experiences.jsonl')

    def _restore_experiences(self):
        """Anything on the record whose experience never reached the store (order: as on the record)."""
        store = self._store()
        have = {e.get(k) for e in store.items for k in ('intent', 'jseq') if e.get(k) is not None}
        intents = {r['seq']: r['data'] for r in self.rows if r['kind'] == 'ACTION_INTENT'}
        after = {r['data']['intent']: r['data']['after'] for r in self.rows if r['kind'] == 'OBSERVATION' and 'intent' in r['data']}
        for r in self.rows:
            d = r['data']
            if 'experience' in d and r['seq'] not in have:
                store.add({**d['experience'], 'jseq': r['seq']})
            elif r['kind'] == 'ACTION_RESULT' and d['intent'] not in have:
                i = intents[d['intent']]
                e = call_experience(i['body'], i['source'], i['actor'], i['tool'], i['args'], i['caps'], d['response'], i['before'], after.get(d['intent']))
                store.add({**e, 't': len(store.items), 'intent': d['intent']})

    def _reconcile(self):
        """Every intent with no result: look again, record what is found, and leave it there."""
        done = {r['data']['intent'] for r in self.rows if r['kind'] == 'ACTION_RESULT'}
        done |= {r['data']['reconciles'] for r in self.rows if 'reconciles' in r['data']}
        store = None
        for r in self.rows:
            if r['kind'] != 'ACTION_INTENT' or r['seq'] in done:
                continue
            i = r['data']
            try:
                st = _seen(open_world(i['body'], self.root / 'worlds' / i['body']))
                blank = learner._blank(st or i['before'])
                found = {x: st.get(x, blank) for x in i['args']}
            except Exception as ex:                        # the world could not be read; nothing is assumed
                self.journal.append('OBSERVATION', reconciles=r['seq'], body=i['body'], found=None, changed=None, error=repr(ex))
                continue
            changed = found != i['before']
            store = store or self._store()
            e = None
            if changed:                                    # something is different; what did it is not known
                e = experience(t=len(store.items), body=i['body'], source='re-observation', actor='outside', action=None, executed=None,
                               response=None, before=i['before'], after=found, external=[{'event': 'found changed after an interruption'}],
                               unobserved=['action', 'response', 'cause'])
            kw = {'experience': e} if e else {}
            seq = self.journal.append('OBSERVATION', reconciles=r['seq'], body=i['body'], found=found, changed=changed, **kw)
            if e:
                store.add({**e, 'jseq': seq})

    def _checkpoints(self):
        return [r['data'] for r in self.rows if r['kind'] == 'HOST' and r['data'].get('event') == 'checkpoint']

    def _restart_check(self):
        """The models rebuilt from the disk are the models that were live at the last checkpoint."""
        items = self._store().items
        cp = self._checkpoints()
        n = cp[-1]['experiences'] if cp else 0
        eff, goals = rebuild(items[:n])
        if cp and (eff.digest(), goals.digest()) != (cp[-1]['effects'], cp[-1]['goals']):
            raise RuntimeError(f"models rebuilt from the disk differ from checkpoint {cp[-1]['stage']}")
        for e in items[n:]:
            learner.NextGrounder._learn(e, eff, goals)
        seed_fitted(self.mind, eff, goals, len(items))
        self.journal.append('HOST', event='restart_check', checkpoint=cp[-1]['stage'] if cp else None, experiences=n, same=True)

    def _place(self):
        """The next stage, from the record: one past the last stage begun; a stage begun and not checkpointed is closed."""
        begun = [r['data']['stage'] for r in self.rows if r['kind'] == 'HOST' and r['data'].get('event') == 'stage_begin']
        closed = {r['data']['stage'] for r in self.rows if r['kind'] == 'HOST' and r['data'].get('event') in ('checkpoint', 'stage_interrupted')}
        if begun and begun[-1] not in closed:
            self.journal.append('HOST', event='stage_interrupted', stage=begun[-1])
        return begun[-1] + 1 if begun else 0

    # ------------------------------------------------------------ the teacher's side (its own notes, in the world's folder)
    def _teacher(self, body):
        world = self.root / 'worlds' / body
        if world.exists() and not (world / '.born').exists():
            shutil.rmtree(world)                           # a kill while the world was first being made: no action was ever taken in it
        new = not world.exists()
        t = Teacher(world, seed=self.seed, body=body, mind=self.mind)
        (world / '.born').touch()
        notes = world / 'teacher_state.pkl'
        if notes.exists():
            n = pickle.loads(notes.read_bytes())
            for k in TEACHER_NOTES:
                setattr(t, k, n[k])
            t.rng.setstate(n['rng']), t.nrng.setstate(n['nrng']), t.tut.rng.setstate(n['tut_rng'])
            t.tut.help = n['tut_help']
        if new:
            self.journal.append('EXTERNAL_EVENT', event='body_born', body=body, objects=sorted(t.sess.home.existing()))
        self._attach(t, body, notes)
        return t

    def _attach(self, t, body, notes):
        """Listening at the person's interface: what is said and what happens from outside goes on the record. Nothing here
        reaches the learner."""
        ask, log, tlog = t.sess.person.ask, t.sess.log, t.log

        def said(kind, **info):
            ans = ask(kind, **info)
            self.journal.append('TESTIMONY', body=body, question=kind, info=info, answer=ans)
            return ans

        def logged(**row):
            if row.get('event') in ('session', 'teacher_scene_setup'):
                self.journal.append('EXTERNAL_EVENT', body=body, **row)
            return log(**row)

        def activity(*a, **kw):
            tlog(*a, **kw)
            self._save_teacher(t, notes)
            if a and a[0] == 'command' and GAIN.get(kw.get('outcome'), 0.0):   # what the person's scoring is worth to the body
                self._charge(f"outcome:{kw['outcome']}", GAIN[kw['outcome']])
        t.sess.person.ask, t.sess.log, t.log = said, logged, activity

    @staticmethod
    def _save_teacher(t, notes):
        atomic_write(notes, pickle.dumps({**{k: getattr(t, k) for k in TEACHER_NOTES}, 'rng': t.rng.getstate(), 'nrng': t.nrng.getstate(),
                                          'tut_rng': t.tut.rng.getstate(), 'tut_help': t.tut.help}))

    # ------------------------------------------------------------ living
    def _look(self, body, home, stage, when):
        """What the body looks like now, and what is different from when it was last looked at (no cause assumed)."""
        st = _seen(home)
        last = next((r['data']['state'] for r in reversed(self.rows) if r['kind'] == 'OBSERVATION' and r['data'].get('body') == body and 'state' in r['data']), None)
        changed = [] if last is None else sorted(k for k in set(last) | set(st) if last.get(k) != st.get(k))
        self.journal.append('OBSERVATION', body=body, stage=stage, when=when, state=st, changed_since_last_look=changed)

    def run_stage(self):
        """One stage. -> the stage's number, or None when the life is over."""
        n = self.next
        if n >= len(self.stages):
            return None
        s = self.stages[n]
        self.journal.append('HOST', event='stage_begin', stage=n, stage_kind=s['kind'], body=s['body'], session=s.get('i'))
        self._charge('stage', -PRICES['STAGE'])            # time passes whether or not it acts
        live = None
        if s['kind'] == 'session':
            t = self._teacher(s['body'])
            self._look(s['body'], t.sess.home, n, 'before the visit')
            self.rows = self.journal.rows()
            t.session(s['i'], day=n)                       # one calendar for the whole life
            t.finish()
            self._save_teacher(t, self.root / 'worlds' / s['body'] / 'teacher_state.pkl')
            self._look(s['body'], t.sess.home, n, 'after the visit')
            g = learner._FITTED.get('live')
            live = (g.eff, g.goals) if g is not None else None
        else:
            world = self.root / 'worlds' / s['body']
            if (world / 'names.json').exists():            # a body whose whole course was cut short has nothing to practise
                trials = after_course(world, self.mind, s['body'], self.seed)
                from ..rebuild.practice import practice
                self.journal.append('HOST', event='practice_done', stage=n, body=s['body'], trials=trials)
                live = (practice.live, None)
        items = self._store().items
        eff, goals = rebuild(items)
        d = {'effects': eff.digest(), 'goals': goals.digest()}
        if live is not None and (live[0].digest() != d['effects'] or (live[1] is not None and live[1].digest() != d['goals'])):
            raise RuntimeError(f'stage {n}: the models learned live differ from the models rebuilt from the disk')
        self.journal.append('HOST', event='checkpoint', stage=n, experiences=len(items), live_compared=live is not None, **d)
        self.next = n + 1
        return n

    def close(self):
        Store.autobiography = None
        metab.CURRENT = None
        self.journal.close()
        self.lock_file.close()
