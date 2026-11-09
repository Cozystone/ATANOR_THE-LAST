"""G_SURVIVAL_PLAN.md: energy, death, and the one decision rule (expected free energy) for anything that costs.

A Self's energy is a function of its autobiography: every record of a kind that costs takes its price, a command the
teacher scores 'success' gives, 'wrong' harms, and each stage has a base cost (time passes whether or not it acts). The
balance is replayed from the record on every start, so a kill changes nothing. When it reaches zero the Self is dead: a
HOST 'death' record and a '.dead' mark, and no process opens that life again.

What a person gives is one preference: energy in [E_low, E_high]. Whether to pay for something that may teach (a lab
test, a practice trial, a question) is decided by
    G = risk(E - cost) - w_epi * information_gain,   do it when G < 0,
    risk(e) = ((E_low - e) / e)^2 below E_low (infinite at e <= 0), else 0;   information_gain = 1 when the prediction is unknown, else 0.
Nothing else in the code says when to explore. The genome holds only the six numbers listed in GENOME.
"""
import json
from pathlib import Path

GENOME = ('tau', 'lab_tests', 'per_action', 'E_low', 'E_high', 'w_epi')
DEFAULT_GENOME = {'tau': 0.99, 'lab_tests': 6, 'per_action': 10, 'E_low': 30.0, 'E_high': 90.0, 'w_epi': 1.0}
E0 = 100.0
PRICES = {'PREDICTION': 0.02, 'ACTION_INTENT': 0.5, 'SELF_TRIAL': 0.3, 'LAB': 0.3, 'QUESTION': 1.0, 'STAGE': 8.0}
GAIN = {'success': 3.0, 'partial': 1.5, 'wrong': -5.0, 'held': 0.0}
TEACHER_GIVES = (None, 'point', 'contrast', 'demo', 'confirm', 'name', 'recall')   # the teacher's events at the interface: free

CURRENT = None                                         # the metabolism of the Self this process is living (life/host.py)


class Death(Exception):
    """Energy reached zero. The life is over; nothing is undone and nothing continues."""


class Metabolism:
    def __init__(self, genome=None, e0=E0, enabled=True):
        self.enabled = enabled                             # a life made before G (no genome in self.json) has no metabolism
        self.g = {**DEFAULT_GENOME, **(genome or {})}
        self.e0 = e0
        self.E = e0
        self.ledger = []                                   # (why, delta) since the last replay, for the record
        self.dead = False
        self.evaluations = []                              # (E, cost, ig, G, chosen): S3's evidence

    # ------------------------------------------------------------ the balance from the record
    def replay(self, rows):
        """E as the autobiography has it: the last INTEROCEPTION record, or e0."""
        self.E = self.e0
        for r in rows:
            if r['kind'] == 'INTEROCEPTION':
                self.E = r['data']['E']
            if r['kind'] == 'HOST' and r['data'].get('event') == 'death':
                self.dead = True
        return self.E

    def price_of(self, kind, data):
        """What a record of this kind costs. Interoception, host bookkeeping and what is seen or told cost nothing."""
        if not self.enabled:
            return 0.0
        if kind in ('PREDICTION', 'ACTION_INTENT', 'SELF_TRIAL'):
            if kind == 'ACTION_INTENT' and data.get('actor') == 'learner-lab':
                return PRICES['LAB']
            return PRICES[kind]
        if kind == 'TESTIMONY' and data.get('question') not in TEACHER_GIVES:   # only what the Self itself asks costs
            return PRICES['QUESTION']
        return 0.0

    def charge(self, why, delta):
        if not self.enabled:
            return
        self.E += delta
        self.ledger.append((why, delta))
        if self.E <= 0 and not self.dead:
            self.dead = True
            raise Death(f'energy {self.E:.2f} after {why}')

    def outcome(self, outcome):
        self.charge(f'outcome:{outcome}', GAIN.get(outcome, 0.0))

    def stage(self):
        self.charge('stage', -PRICES['STAGE'])

    # ------------------------------------------------------------ the one rule for paying to learn
    def risk(self, e):
        """Below the preferred floor, the shortfall against what would be left (so it diverges at death)."""
        low = self.g['E_low']
        if e <= 0:
            return float('inf')
        return ((low - e) / e) ** 2 if e < low else 0.0

    def allow(self, cost, unknown):
        """-> True when paying `cost` for something whose prediction is `unknown` lowers expected free energy."""
        if not self.enabled:
            return True
        ig = 1.0 if unknown else 0.0
        G = self.risk(self.E - cost) - self.g['w_epi'] * ig
        ok = G < 0
        self.evaluations.append((round(self.E, 3), cost, ig, round(G, 4), ok))
        return ok

    def state(self):
        return {'E': round(self.E, 4), 'dead': self.dead, 'genome': self.g}


def genome_of(self_dir):
    p = Path(self_dir) / 'self.json'
    if p.exists():
        return json.loads(p.read_text(encoding='utf-8')).get('genome') or dict(DEFAULT_GENOME)
    return dict(DEFAULT_GENOME)
