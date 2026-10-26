"""Interactive grounding tutor (evaluator side; never imported by agent/). It imitates what a person does when teaching
without sentences: POINT at a few of the objects meant, DEMOnstrate the action once, answer a CONTRAST question
("this one too?"), CONFIRM or reject what was done, and only after that NAME things with a symbol. Symbols are
arbitrary syllables drawn per seed, so nothing English can help; English names are given only in a later phase.
Every answer is counted. The tutor knows the target (which objects, which action) because the person has it in mind.
"""
import random
from collections import Counter

from ..world.board_world import TRAYS


def symbols(seed, n=40):
    rng = random.Random(f'symbols-{seed}')
    cons, vows = 'bdfgklmnprstvwz', 'aeiou'
    out = set()
    while len(out) < n:
        out.add(rng.choice(cons) + rng.choice(vows) + rng.choice(cons) + (rng.choice(vows) if rng.random() < 0.5 else ''))
    out = sorted(out)                                   # a set's order differs between processes: sort, then shuffle
    rng.shuffle(out)
    return out


class BoardSpec:
    """What the person knows about the board's actions (to demonstrate them and to judge them)."""
    BODY = 'board'

    @staticmethod
    def steps(act, o, drift):
        t, s = act['tool'], act.get('second')
        if t == 'lodge':
            return ('slot', (s, o)) if 'lodge_retired' in drift else ('lodge', (o, s))
        if t == 'stamp':
            return ('brand', (s, o)) if 'stamp_retired' in drift else ('stamp', (o, s))
        if t == 'lift':
            return ('lift', (o, s))
        return (t, (o,))

    @staticmethod
    def shows(act, a):
        """Does an object (human attributes, or None if gone) show the action's result?"""
        t, s = act['tool'], act.get('second')
        if t == 'scrap':
            return a is None or a['kind'] == 'absent'
        if a is None or a['kind'] == 'absent':
            return False
        if t == 'lodge':
            return a['tray'] == TRAYS[s]
        if t == 'unlodge':
            return a['tray'] == '-'
        if t == 'stamp':
            return a['mark'] == s[2:]
        if t == 'lift':
            return a['level'] == s[2:]
        return False


class Tutor:
    def __init__(self, home, spec, seed):
        self.home, self.spec = home, spec
        self.rng = random.Random(f'tutor-{seed}')
        self.help = Counter()
        self.sel = self.act = None

    def _state(self):
        return self.home.observe(self.home.existing())

    def matches(self, a):
        return a is not None and all(a.get(k) == v for k, v in self.sel.items())

    def start(self, sel, act=None):
        self.sel, self.act = sel, act
        self.before = self._state()
        self.truth = sorted(o for o, a in self.before.items() if self.matches(a))
        self.pointed = set()

    # --- the non-verbal events
    def point(self, k=2):
        self.help['point'] += 1
        cand = [o for o in self.truth if o not in self.pointed]
        pick = self.rng.sample(cand, min(k, len(cand)))
        self.pointed |= set(pick)
        return sorted(pick)

    def contrast(self, obj):
        self.help['contrast'] += 1
        return obj in self.truth

    def demo(self):
        self.help['demo'] += 1
        st = self._state()
        todo = [o for o in self.truth if not self.spec.shows(self.act, st.get(o))]
        o = self.rng.choice(todo or self.truth)
        tool, args = self.spec.steps(self.act, o, getattr(self.home, 'drift', ()))
        self.home.execute(tool, args, {c: True for c in set(getattr(self.home, 'CAPABILITY', {}).values())})
        return {'tool': tool, 'args': list(args), 'object': o}

    def judge(self):
        """Every object meant shows the result; every other object is as it was."""
        now = self._state()
        for o, a in self.before.items():
            cur = now.get(o)
            if o in self.truth:
                if not self.spec.shows(self.act, cur):
                    return False
            elif cur != a and not (cur is None and a['kind'] == 'absent'):
                return False
        return True

    def confirm(self):
        self.help['confirm'] += 1
        return self.judge()
