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

GENOME = ('tau', 'lab_tests', 'per_action', 'E_low', 'E_high', 'w_epi', 'guide')
# guide (0/1): in practice, try first the starts that put a never-met value on a role that this mind's OTHER bodies (lived or
# read) found decisive for that kind of outcome (life/role_space_probe.py). A cross-body carrier for selection to keep or drop.
DEFAULT_GENOME = {'tau': 0.99, 'lab_tests': 6, 'per_action': 10, 'E_low': 30.0, 'E_high': 90.0, 'w_epi': 1.0, 'guide': 0}
E0 = 100.0
# Environment, second setting (G_SURVIVAL_PLAN.md): under the first (stage 8, success 3) every Self of every condition starved
# before its third body (18/18, dev seed 1), so there was nothing to select. The teacher gives 2-3 commands a session.
# Third setting: under the second (stage 7) all 54 Selves of three generations lived with energy to spare (ending 70-144 of 100),
# so death never selected. Stage 9: a Self that succeeds at nearly every command just lives; one at GOOD ~0.7 does not.
# Fourth setting: under the third (stage 9) still 120/120 lived (ending 34-91). Stage 11.
PRICES = {'PREDICTION': 0.02, 'ACTION_INTENT': 0.3, 'SELF_TRIAL': 0.3, 'LAB': 0.3, 'QUESTION': 1.0, 'STAGE': 11.0}
if __import__('os').environ.get('ATANOR_STAGE_PRICE'):     # ISLAND_ENERGY_PLAN.md: the island needs its own setting (dev)
    PRICES['STAGE'] = float(__import__('os').environ['ATANOR_STAGE_PRICE'])
GAIN = {'success': 10.0, 'partial': 5.0, 'wrong': -5.0, 'held': 0.0}
TEACHER_GIVES = (None, 'point', 'contrast', 'demo', 'confirm', 'name', 'recall', 'judge')   # the teacher's events at the interface: free

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
