"""What the person of each of the island's five places (reef, moor, tarn, glen, crag) knows about the place's actions,
to demonstrate them and to judge them, and the names the person gives there (evaluator side; never imported by
agent/). The objects meant are urns. Every action is relative: what it gives is read from the urn (and the stele) as
they were before, so whether an urn shows the result is known only against the state before. A person does not
expect an urn the place refuses to act on to change; such urns must stay as they were.
"""
import random

from ..eval.isle_targets import PLACES, workspace
from ..world.isle_world import result

ENDS = {'reef': 'h', 'moor': 'j', 'tarn': 'q', 'glen': 'w', 'crag': 'y'}


def symbols_isle(body, seed, n=40):
    """The island's names: consonant, vowel, consonant, vowel and a last letter that is the place's own. Five letters,
    so no name can repeat an earlier body's (three or four letters), and no two places share a name."""
    rng = random.Random(f'symbols-{body}-{seed}')
    cons, vows = 'bdfgkmnprstvz', 'aeiou'
    out = set()
    while len(out) < n:
        out.add(rng.choice(cons) + rng.choice(vows) + rng.choice(cons) + rng.choice(vows) + ENDS[body])
    out = sorted(out)
    rng.shuffle(out)
    return out


def _spec(body):
    ws = workspace(body)

    class Spec:
        BODY = body
        RELATIVE = True
        KEEP_IMPOSSIBLE = True

        @staticmethod
        def member(o, a, sel):
            return a is not None and '.' not in o and all(a.get(k) == v for k, v in sel.items() if k != 'at')

        @staticmethod
        def steps(act, o, drift):
            t = act['tool']
            if f'{t}_retired' in drift and t in ws.RETIRE:
                t = ws.RETIRE[t]
            return (t, (o, act['second'])) if act.get('second') else (t, (o,))

        @staticmethod
        def given(act, o, state):
            """The urn's attributes the action gives on this state, or None if the place refuses."""
            return result(ws.TABLE[act['tool']], state.get(o), state.get(act.get('second')))

        @staticmethod
        def shows(act, o, state, before=None):
            if before is None or o not in before:
                return False                               # a relative change shows only against the state before
            want = Spec.given(act, o, before)
            return want is not None and state.get(o) == want

        @staticmethod
        def possible(act, o, state):
            return Spec.given(act, o, state) is not None

        @staticmethod
        def may_change(act, o, truth):
            return False

    Spec.__name__ = Spec.__qualname__ = f'{body.capitalize()}Spec'
    return Spec


SPECS = {b: _spec(b) for b in PLACES}
ReefSpec, MoorSpec, TarnSpec, GlenSpec, CragSpec = (SPECS[b] for b in PLACES)
