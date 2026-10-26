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
    def member(o, a, sel):
        return a is not None and all(a.get(k) == v for k, v in sel.items())

    @staticmethod
    def shows(act, o, state):
        """Does the object show the action's result on this state?"""
        a = state.get(o)
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


BoardSpec.may_change = staticmethod(lambda act, o, truth: False)


class FsSpec:
    """The file body: the objects meant are top-level files; copy and move put them into an existing folder."""
    BODY = 'fs'

    @staticmethod
    def member(o, a, sel):
        return a is not None and '/' not in o and all(a.get(k) == v for k, v in sel.items())

    @staticmethod
    def steps(act, o, drift):
        t, d = act['tool'], act.get('second')
        if t == 'copy':
            return ('replicate', (f'{d}/{o}', o)) if 'copy_retired' in drift else ('copy', (o, f'{d}/{o}'))
        if t == 'move':
            return ('shove', (f'{d}/{o}', o)) if 'move_retired' in drift else ('move', (o, f'{d}/{o}'))
        return ('zap', (o,)) if 'delete_retired' in drift else ('delete', (o,))

    @staticmethod
    def shows(act, o, state):
        t, d = act['tool'], act.get('second')
        a, c = state.get(o), state.get(f'{d}/{o}') if d else None
        gone = a is None or a['kind'] == 'absent'
        made = c is not None and c['kind'] == 'file'
        return gone if t == 'delete' else (made and not gone if t == 'copy' else made and gone)

    @staticmethod
    def possible(act, o, state):
        """A person does not expect a copy or move onto a file that is already there."""
        d = act.get('second')
        return act['tool'] == 'delete' or state.get(f'{d}/{o}', {'kind': 'absent'})['kind'] == 'absent'

    @staticmethod
    def may_change(act, o, truth):
        """The folder's new children and the folder itself may change."""
        d = act.get('second')
        return bool(d) and (o == d or o.startswith(d + '/'))


class ViewSpec:
    """The screen body: the objects meant are panels; tools set a panel's filter, sort or group, or close it."""
    BODY = 'view'
    ATTR = {'filter': 'filter', 'sort': 'sort', 'group': 'group'}

    @staticmethod
    def member(o, a, sel):
        return a is not None and ':' not in o and all(a.get(k) == v for k, v in sel.items())

    @staticmethod
    def steps(act, o, drift):
        t, v = act['tool'], act.get('second')
        if t == 'filter' and 'filter_retired' in drift:
            return ('sift', (v, o))
        if t == 'sort' and 'sort_retired' in drift:
            return ('rank', (v, o))
        return (t, (o, v)) if v else (t, (o,))

    @staticmethod
    def shows(act, o, state):
        a = state.get(o)
        t, v = act['tool'], act.get('second')
        if t == 'close':
            return a is None or a['kind'] == 'absent'
        return a is not None and a['kind'] == 'panel' and a[ViewSpec.ATTR[t]] == v.split(':', 1)[1]

    @staticmethod
    def may_change(act, o, truth):
        return False


class Tutor:
    def __init__(self, home, spec, seed):
        self.home, self.spec = home, spec
        self.rng = random.Random(f'tutor-{seed}')
        self.help = Counter()
        self.sel = self.act = None

    def _state(self):
        return self.home.observe(self.home.existing())

    def matches(self, o, a):
        return self.spec.member(o, a, self.sel)

    def start(self, sel, act=None):
        self.sel, self.act = sel, act
        self.before = self._state()
        self.truth = sorted(o for o, a in self.before.items() if self.matches(o, a))
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
        todo = [o for o in self.truth if not self.spec.shows(self.act, o, st)]
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
                possible = getattr(self.spec, 'possible', lambda act, o, st: True)(self.act, o, self.before)
                if possible and not self.spec.shows(self.act, o, now):
                    return False
            elif cur != a and not (cur is None and a['kind'] == 'absent') and not self.spec.may_change(self.act, o, self.truth):
                return False
        return True

    def confirm(self):
        self.help['confirm'] += 1
        return self.judge()
