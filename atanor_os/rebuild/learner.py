"""REBUILD_PLAN.md stage 4: the new structure on the existing bodies, inside the baseline core.

Everything the baseline core does stays (concepts, words, lessons, recovery by lab experiments); only the decision of
which objects to act on (`Grounder._decide`) is replaced, and every call is kept as an experience:
  1. what the call will do to this object, predicted from its start (effects.BayesAction, tau)
  2. unknown: a lab-copy test of that very call (budget per command), then predict again
  3. predicted 'blocked' or 'failed': not attempted; counted as avoided by ATANOR (apart from blocks by the body's
     guard). A start that used to work and now fails (an earlier case from the same start was superseded) is
     tried, so the core's lab search for another way starts; an unexpected failure starts it too
  4. predicted no change: left
  5. a change: is it what the person meant? a remembered or predicted answer decides; with the person there and no
     answer, ask "this one too?" (question budget per command); otherwise act as the core would
  6. still unknown after 2: as the baseline would (its G reading alone, the core rule with the person), and the open
     question is kept (open_issues.jsonl)
Switches (ATANOR_LEARNER in agent/learners.py): next, next_nolab, next_noask.
"""
import json
import os
import shutil
from collections import Counter
from pathlib import Path

from ..agent.grounding import QUESTION_BUDGET, Grounder
from .effects import Effects, flat
from .experience import Store, experience
from .goals import Goals
from ..life import metabolism

TAU = 0.99
LAB_TESTS = 6


def _tau():
    m = metabolism.CURRENT
    return m.g['tau'] if m else TAU


def _lab_budget():
    m = metabolism.CURRENT
    return int(m.g['lab_tests']) if m else LAB_TESTS


def _may_pay(cost, unknown):
    """Outside a life everything may be tried; inside one, the metabolism's one rule decides."""
    m = metabolism.CURRENT
    return True if m is None else m.allow(cost, unknown)
_FITTED = {}


def _blank(obs):
    keys = next(iter(obs.values()), {})
    return {k: '-' for k in keys} | {'kind': 'absent'}


def call_experience(body, source, actor, tool, args, caps, res, before, after):
    """One call as an experience; before / after: the arguments' observations (after None: never observed)."""
    return experience(body=body, source=source, actor=actor,
                      action={'tool': tool, 'args': list(args), 'granted': sorted(k for k, v in caps.items() if v)},
                      executed=not res.get('blocked') and res.get('error') != 'invalid',
                      response={'ok': bool(res.get('ok')), 'error': res.get('error'), 'guard': 'blocked' if res.get('blocked') else None},
                      before=before, after=before if res.get('blocked') else after, unobserved=['later'] + (['after'] if after is None else []))


def rebuild(items):
    """The models of these experiences, learned from nothing."""
    eff, goals = Effects(), Goals(TAU)
    for e in items:
        NextGrounder._learn(e, eff, goals)
    return eff, goals


def seed_fitted(mind_dir, eff, goals, n):
    """A process that already rebuilt the models from the disk hands them to its learners (no second refit)."""
    p = Path(mind_dir) / 'experiences.jsonl'
    raw = p.read_bytes() if p.exists() else b''
    _FITTED['last'] = (len(raw), hash(raw), eff, goals, n)


class NextGrounder(Grounder):
    def __init__(self, home, mind_dir, *a, lab=True, ask=True, know=False, **kw):
        super().__init__(home, mind_dir, *a, **kw)
        self.lab, self.ask = lab, ask
        self.store = Store(self.dir / 'experiences.jsonl')
        self.knower = None
        if know:                                           # P_KNOW_LIFE_PLAN.md: the reader, from this body's own experiences
            from ..memory.know import knower
            self.knower = knower(self.store, self.body)
        self.issues = self.dir / 'open_issues.jsonl'
        self.eff, self.goals = self._fitted()
        self.eff.body = self.body                          # a mind may have lived in several bodies; this one is here
        _FITTED['live'] = self                             # the last learner holds the models as learned (life/host.py)

    # ------------------------------------------------------------ experience
    def _fitted(self):
        """The models of this mind's experiences. A process keeps the last fit; when the file only grew since (a course
        appends), only the new experiences are learned, so a new learner per command does not refit from scratch."""
        import copy
        raw = (self.dir / 'experiences.jsonl').read_bytes() if (self.dir / 'experiences.jsonl').exists() else b''
        last = _FITTED.get('last')
        if last and len(raw) >= last[0] and hash(raw[:last[0]]) == last[1]:
            eff, goals = copy.deepcopy(last[2]), copy.deepcopy(last[3])
            done = last[4]
        else:
            eff, goals, done = Effects(), Goals(TAU), 0
        for e in self.store.items[done:]:
            self._learn(e, eff, goals)
        _FITTED['last'] = (len(raw), hash(raw), eff, goals, len(self.store.items))
        return copy.deepcopy(eff), copy.deepcopy(goals)

    @staticmethod
    def _learn(e, eff, goals):
        if e.get('kind') == 'answer':
            goals.add((e.get('body'), e['tool']), e['consts'], e['concept'], e['start'], e['answer'], e['t'])
        elif e.get('action'):
            eff.observe(e)

    def _keep(self, e):
        e = self.store.add({**e, 't': len(self.store.items)})
        self._learn(e, self.eff, self.goals)
        return e

    @staticmethod
    def _obs(home):
        """The world as observed; an object that is not there is 'no value' throughout, as in the course logs."""
        return home.observe(home.existing())

    def _exp(self, actor, tool, args, caps, res, before_st, after_st):
        blank = _blank(before_st or after_st or {})
        b = {x: before_st.get(x, blank) for x in args}
        a = None if after_st is None else {x: after_st.get(x, blank) for x in args}
        self._keep(call_experience(self.body, self.source, actor, tool, args, caps, res, b, a))

    def _intend(self, life, c):
        """Before the world is touched: what this call is predicted to do, and that it is about to be made. On the record
        first, so a kill from here on cannot lose that the action may have happened."""
        blank = _blank(c['before'])
        c['b'] = {x: c['before'].get(x, blank) for x in c['args']}
        p = self.eff.predict(c['tool'], c['args'], [c['b'][x] for x in c['args']], reader=f'BAYES{_tau()}')
        life.append('PREDICTION', body=self.body, tool=c['tool'], args=c['args'], reader=f'BAYES{_tau()}', before=c['b'],
                    outcome=None if p['outcome'] is None else {str(k): v for k, v in p['outcome'].items()}, why=p.get('why'))
        c['intent'] = life.append('ACTION_INTENT', body=self.body, source=self.source, actor='learner', tool=c['tool'], args=c['args'],
                                  caps=c['caps'], before=c['b'])

    def _conclude(self, life, c):
        """The body answered: the result is on the record, then what is seen right after, and only then is it learned."""
        res = c['res']
        life.append('ACTION_RESULT', intent=c['intent'], response={k: res.get(k) for k in ('ok', 'blocked', 'error')})
        after = c['after'] if c['after'] is not None else self._obs(self.home)
        blank = _blank(c['before'] or after)
        a = {x: after.get(x, blank) for x in c['args']}
        life.append('OBSERVATION', intent=c['intent'], body=self.body, after=a)
        self._keep({**call_experience(self.body, self.source, 'learner', c['tool'], c['args'], c['caps'], res, c['b'], a), 'intent': c['intent']})
        c['kept'] = True

    def _call(self, actor, home, tool, args, caps, *a, real=None, **kw):
        """A call on a lab copy: observed right before and right after."""
        before = self._obs(home)
        try:
            res = real(tool, args, caps, *a, **kw)
        except ValueError:
            self._exp(actor, tool, args, caps, {'ok': False, 'error': 'invalid'}, before, before)
            raise
        self._exp(actor, tool, args, caps, res, before, self._obs(home))
        return res

    def apply(self, sel, effect, lesson=None, decided=None):
        """The calls of one command, observed once before and once after (some bodies observe the whole world on every
        call). A call is recorded with the state right before and right after it: when a call touches an object an
        earlier call of this command touched, the world is observed then, which is both that earlier call's 'after' and
        this call's 'before'. Constant arguments (never changed) do not count as touched."""
        real = self.home.execute
        life = Store.autobiography                         # in a life, each call goes on the record as it is made
        snap, buf, consts = self._obs(self.home), [], self.eff.constants()

        def rec(tool, args, caps, *a, **kw):
            nonlocal snap
            mine = {x for x in args if x not in consts}
            if any(mine & c['mine'] for c in buf):
                snap = self._obs(self.home)
                for c in buf:
                    if c['after'] is None and c['mine'] & mine:
                        c['after'] = snap
            row = {'tool': tool, 'args': list(args), 'caps': caps, 'before': snap, 'after': None, 'mine': mine}
            buf.append(row)
            if life is not None:
                self._intend(life, row)
            try:
                row['res'] = real(tool, args, caps, *a, **kw)
            except ValueError:
                row['res'], row['after'] = {'ok': False, 'error': 'invalid'}, snap
                if life is not None:
                    self._conclude(life, row)
                raise
            if life is not None:
                self._conclude(life, row)
            return row['res']
        self.home.execute = rec
        try:
            return super().apply(sel, effect, lesson, decided)
        finally:
            del self.home.execute
            rest = [c for c in buf if not c.get('kept')]
            end = self._obs(self.home) if rest else None
            for c in rest:
                self._exp('learner', c['tool'], c['args'], c['caps'], c['res'], c['before'], c['after'] or end)

    def learn_action(self, lesson):
        before = self.home.observe(self.home.existing())
        claim = super().learn_action(lesson)
        demo = self.mem.events.all()[-1] if self.mem.events.all() and self.mem.events.all()[-1].get('kind') == 'demo' else None
        if demo:
            args = demo['args']
            after = self._obs(self.home)
            blank = _blank(before or after)
            self._keep(experience(body=self.body, source=self.source, actor='person', action={'tool': demo['tool'], 'args': list(args),
                                  'granted': None}, executed=True, response=None,
                                  before={x: before.get(x, blank) for x in args}, after={x: after.get(x, blank) for x in args},
                                  unobserved=['response', 'granted', 'later']))
        return claim

    def obey(self, symbols, task=None):
        import time
        t0 = time.perf_counter()
        res = super().obey(symbols, task)
        self.counts['ms'] = round((time.perf_counter() - t0) * 1000)   # what one command costs
        out = os.environ.get('ATANOR_NEXT_COUNTS')        # evaluators make a new learner per command: keep its counts
        if out:
            with open(out, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'body': self.body, 'person': self.person is not None, 'task': task, 'counts': dict(self.counts)}) + chr(10))
        return res

    # ------------------------------------------------------------ the three judgments
    def _lab_test(self, tool, args):
        root = self.dir / 'lab_next'
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        lab = self.home.lab_copy(root, list(args))       # the call's own arguments only: same result as a copy of the
        if hasattr(self.home, 'drift'):                  # whole world on every body (dev check, 300 calls), 16x faster
            lab.drift = self.home.drift                  # on the file body
        try:
            self._call('learner-lab', lab, tool, args, self.caps, real=lab.execute)
        except ValueError:
            pass
        shutil.rmtree(root, ignore_errors=True)
        self.counts['lab_tests'] += 1

    def _other_way_cached(self, act, o, x, memo):
        key = json.dumps(sorted(x.items(), key=str), default=str)
        if memo.get('yes'):
            return True
        if key not in memo:
            memo[key] = self._other_way(act, o)
            memo['yes'] = memo['yes'] or memo[key] if 'yes' in memo else memo[key]
        return memo[key]

    def _other_way(self, act, o):
        """Does another tool bring this action's change on o, in a lab copy? A check only: nothing is revised (the core's
        own recovery does that after a real failure). Same search as the core's lab experiment, same budget."""
        import itertools
        args = [self._arg(r, o) for r in act['template']]
        tools = getattr(self.home, 'tools', lambda: {})()
        root, tried = self.dir / 'lab_other', 0
        for tool in sorted(t for t, n in tools.items() if n == len(args) and t != act['tool']):
            for order in itertools.permutations(range(len(args))):
                if tried >= self.LAB_BUDGET:
                    return False
                tried += 1
                lab = self.home.lab_copy(root, list(args))
                if hasattr(self.home, 'drift'):
                    lab.drift = self.home.drift
                before = self.feats(lab)
                try:
                    res = lab.execute(tool, tuple(args[i] for i in order), self.caps)
                except ValueError:
                    res = {'ok': False}
                after = self.feats(lab)
                self.counts['lab_tests_other_way'] += 1
                if res.get('ok') and not self._done(act, before, before, o) and self._done(act, before, after, o):
                    shutil.rmtree(root, ignore_errors=True)
                    return True
        shutil.rmtree(root, ignore_errors=True)
        return False

    def _issue(self, **row):
        with open(self.issues, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'t': len(self.store.items), **row}, ensure_ascii=False, default=str) + '\n')

    def _decide(self, sel, act, feats, task, ev):
        ext = self.extension(sel['atoms'], feats)
        base = super()._decide(sel, act, feats, task, ev)    # the baseline's own decision (G alone, the core rule with
        decided, labs, asks = {}, 0, 0                       # the person): used wherever the new parts do not know
        other = {}                                           # another tool brings this change: yes once for the command,
                                                             # no per start (a locked item does not speak for the rest)
        concept = sel.get('concept')
        calls = {o: tuple(self._arg(r, o) for r in act['template']) for o in ext}
        st_all = self._obs(self.home) if calls else {}        # once per command
        for o in ext:
            args = calls[o]
            if len(set(args)) != len(args):
                decided[o] = 'leave'
                continue
            core = base[o] if base is not None and o in base else ('leave' if self._done(act, feats, feats, o) else 'act')
            st = st_all
            blank = _blank(st)
            before = [st.get(x, blank) for x in args]
            p = self.eff.predict(act['tool'], args, before, reader=f'BAYES{_tau()}')
            tested = False
            if p['outcome'] is None and self.knower is not None:
                y = self.knower.predict(act['tool'], list(args), before)
                if y is not None:
                    p = {'outcome': y, 'why': 'reader'}
                    self.counts['known_by_reader'] += 1
            if p['outcome'] is None and self.lab and labs < _lab_budget() and _may_pay(metabolism.PRICES['LAB'], True):
                labs += 1
                tested = True
                self._lab_test(act['tool'], args)
                p = self.eff.predict(act['tool'], args, before, reader=f'BAYES{_tau()}')
            y = p['outcome']
            if y is None:
                decided[o] = core
                self.counts['acted_as_core_unknown' if core == 'act' else 'left_as_core_unknown'] += 1
                self._issue(need='effect', task=task, tool=act['tool'], args=list(args), start=before[0], why=p.get('why'),
                            checks=['lab test' if self.lab else None, 'demonstration by the person'], resume='a case from this start')
                continue
            resp = y.get(('r',))
            changes = any(y.get((i, k), v) != v for i, b in enumerate(before) for k, v in (b or {}).items())
            if resp == 'blocked':
                decided[o] = 'leave'
                self.counts['avoided_predicted_block'] += 1
                self._issue(need='permission', task=task, tool=act['tool'], args=list(args), start=before[0],
                            checks=['ask the person for the permission'], resume='a grant for this call')
                continue
            if resp == 'failed':
                m = self.eff.model(act['tool'], args)
                x = flat(before)
                stopped = m is not None and any(c.x == x and c.y.get(('r',)) == 'ok' for c in m.superseded)
                news = tested and m is not None and any(c.y.get(('r',)) == 'ok' for c in m.cases + m.superseded)                     and self._other_way_cached(act, o, x, other)
                if (stopped or news) and core == 'act':    # this start used to work and no longer does, or a test just
                    decided[o] = 'act'                     # found an action that has worked failing here: likely a
                    self.counts['retried_stopped_way'] += 1   # changed world, and the core's recovery (a failed call
                    continue                               # starts a lab search for another way) is the next step
                decided[o] = 'leave'                       # a start it never worked from is not tried: trying it would
                self.counts['avoided_predicted_fail'] += 1   # only count against the whole action (dev seed 2, desk: one
                self._issue(need='another way', task=task, tool=act['tool'], args=list(args), start=before[0],   # locked
                            checks=['lab search for another tool', 'demonstration by the person'],   # message marked
                            resume='a case where a call changes this start')   # 'shelve' for re-teaching)
                continue
            if resp is not None and not changes:
                decided[o] = 'leave'
                self.counts['left_predicted_no_change'] += core == 'act'
                continue
            consts = [a for i, a in enumerate(args) if i > 0 and isinstance(act['template'][i], list) and act['template'][i][0] == 'K']
            g = self.goals.predict(act['tool'], consts, concept, before[0])
            if g is None and self.person is not None and self.ask and hasattr(self.person, 'prior') and asks < QUESTION_BUDGET \
                    and not self.passive:
                asks += 1
                g = self.person.prior(o, act)
                self.counts['asked_prior'] += 1
                self._keep({'kind': 'answer', 'body': self.body, 'source': self.source, 'actor': 'person', 'tool': act['tool'],
                            'consts': consts, 'concept': concept, 'object': o, 'start': before[0], 'answer': g,
                            'scope': 'this action, this concept, this start', 'unobserved': ['why']})
            if g is None:
                decided[o] = 'act'
                self.counts['acted_goal_unknown'] += 1
                if self.person is None:
                    self._issue(need='goal', task=task, tool=act['tool'], object=o, start=before[0],
                                checks=['ask "this one too?" when the person is back'], resume="the person's answer")
            else:
                decided[o] = 'act' if g == 'yes' else 'leave'
                self.counts[f'goal_{g}'] += 1
        return decided
