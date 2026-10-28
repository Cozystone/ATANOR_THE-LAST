"""REBUILD_PLAN.md stage 4: the new structure on the existing bodies, inside the baseline core.

Everything the baseline core does stays (concepts, words, lessons, recovery by lab experiments); only the decision of
which objects to act on (`Grounder._decide`) is replaced, and every call is kept as an experience:
  1. what the call will do to this object, predicted from its start (effects.BayesAction, tau)
  2. unknown: a lab-copy test of that very call (budget per command), then predict again
  3. predicted 'blocked': not attempted; counted as avoided by ATANOR (apart from blocks by the body's guard)
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
from .effects import Effects
from .experience import Store, experience
from .goals import Goals

TAU = 0.99
LAB_TESTS = 6
_FITTED = {}


def _blank(obs):
    keys = next(iter(obs.values()), {})
    return {k: '-' for k in keys} | {'kind': 'absent'}


class NextGrounder(Grounder):
    def __init__(self, home, mind_dir, *a, lab=True, ask=True, **kw):
        super().__init__(home, mind_dir, *a, **kw)
        self.lab, self.ask = lab, ask
        self.store = Store(self.dir / 'experiences.jsonl')
        self.issues = self.dir / 'open_issues.jsonl'
        self.eff, self.goals = self._fitted()

    # ------------------------------------------------------------ experience
    def _fitted(self):
        raw = (self.dir / 'experiences.jsonl').read_bytes() if (self.dir / 'experiences.jsonl').exists() else b''
        key = (len(raw), hash(raw))
        if key not in _FITTED:
            eff, goals = Effects(), Goals(TAU)
            for e in self.store.items:
                self._learn(e, eff, goals)
            _FITTED.clear()
            _FITTED[key] = (eff, goals)
        import copy
        return copy.deepcopy(_FITTED[key])

    @staticmethod
    def _learn(e, eff, goals):
        if e.get('kind') == 'answer':
            goals.add(e['tool'], e['consts'], e['concept'], e['start'], e['answer'], e['t'])
        elif e.get('action'):
            eff.observe(e)

    def _keep(self, e):
        e = self.store.add({**e, 't': len(self.store.items)})
        self._learn(e, self.eff, self.goals)
        return e

    def _call(self, actor, home, tool, args, caps, *a, real=None, **kw):
        before = home.observe(list(args))
        try:
            res = real(tool, args, caps, *a, **kw)
        except ValueError:
            self._keep(experience(body=self.body, source=self.source, actor=actor, action={'tool': tool, 'args': list(args),
                       'granted': sorted(k for k, v in caps.items() if v)}, executed=False, response={'ok': False, 'error': 'invalid'},
                       before=before, after=before, unobserved=['later']))
            raise
        after = home.observe(list(args))
        blank = _blank(before or after)
        self._keep(experience(body=self.body, source=self.source, actor=actor,
                              action={'tool': tool, 'args': list(args), 'granted': sorted(k for k, v in caps.items() if v)},
                              executed=not res.get('blocked'), response={'ok': bool(res.get('ok')), 'error': res.get('error'),
                              'guard': 'blocked' if res.get('blocked') else None},
                              before={x: before.get(x, blank) for x in args}, after={x: after.get(x, blank) for x in args},
                              unobserved=['later']))
        return res

    def apply(self, sel, effect, lesson=None, decided=None):
        real = self.home.execute
        self.home.execute = lambda tool, args, caps, *a, **kw: self._call('learner', self.home, tool, args, caps, *a, real=real, **kw)
        try:
            return super().apply(sel, effect, lesson, decided)
        finally:
            del self.home.execute

    def learn_action(self, lesson):
        before = self.home.observe(self.home.existing())
        claim = super().learn_action(lesson)
        demo = self.mem.events.all()[-1] if self.mem.events.all() and self.mem.events.all()[-1].get('kind') == 'demo' else None
        if demo:
            args = demo['args']
            after = self.home.observe(list(args))
            blank = _blank(before or after)
            self._keep(experience(body=self.body, source=self.source, actor='person', action={'tool': demo['tool'], 'args': list(args),
                                  'granted': None}, executed=True, response=None,
                                  before={x: before.get(x, blank) for x in args}, after={x: after.get(x, blank) for x in args},
                                  unobserved=['response', 'granted', 'later']))
        return claim

    def obey(self, symbols, task=None):
        res = super().obey(symbols, task)
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
        lab = self.home.lab_copy(root, self.home.existing())
        if hasattr(self.home, 'drift'):
            lab.drift = self.home.drift
        try:
            self._call('learner-lab', lab, tool, args, self.caps, real=lab.execute)
        except ValueError:
            pass
        shutil.rmtree(root, ignore_errors=True)
        self.counts['lab_tests'] += 1

    def _issue(self, **row):
        with open(self.issues, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'t': len(self.store.items), **row}, ensure_ascii=False, default=str) + '\n')

    def _decide(self, sel, act, feats, task, ev):
        ext = self.extension(sel['atoms'], feats)
        base = super()._decide(sel, act, feats, task, ev)    # the baseline's own decision (G alone, the core rule with
        decided, labs, asks = {}, 0, 0                       # the person): used wherever the new parts do not know
        concept = sel.get('concept')
        for o in ext:
            args = tuple(self._arg(r, o) for r in act['template'])
            if len(set(args)) != len(args):
                decided[o] = 'leave'
                continue
            core = base[o] if base is not None and o in base else ('leave' if self._done(act, feats, feats, o) else 'act')
            st = self.home.observe(list(args))
            blank = _blank(st)
            before = [st.get(x, blank) for x in args]
            p = self.eff.predict(act['tool'], args, before, reader=f'BAYES{TAU}')
            if p['outcome'] is None and self.lab and labs < LAB_TESTS:
                labs += 1
                self._lab_test(act['tool'], args)
                p = self.eff.predict(act['tool'], args, before, reader=f'BAYES{TAU}')
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
                decided[o] = core                          # keep the core's recovery path (a failed call starts a lab search)
                self.counts['predicted_fail'] += 1
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
