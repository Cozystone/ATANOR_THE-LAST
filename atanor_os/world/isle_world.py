"""One connected world of five bodies (built body-side by a separate agent): an island with five places. Every place is
its own body with its own tools and its own JSON state inside a sandbox folder (nothing outside it is touched), but
the places are parts of one world: the same two kinds of object (urns and standing steles), the same attributes with
the same values, and the same hidden laws. This module holds what the places share; each place's module
(reef_world, moor_world, tarn_world, glen_world, crag_world) only says which of its tools follows which laws.

Objects: urn ids (opaque) and stele objects 'k.flint', 'k.basalt', 'k.shale'. Every object has the same six
attributes: kind, depth (0..4), spin (0..3), coat, tide, value (an urn's value is 'bound' or '-', a stele's value is
its name). A call's answer and effect are a function of its arguments' attributes before the call and nothing else;
a stele is never changed by a call. Between days the outside redraws every stele, moves the tide of some urns one
step on, and takes old urns away; every outside change is logged with actor 'outside' and drawn from (seed, tick).
One tool of each place is irreversible and needs a capability. Tool preconditions are enforced here and not exported.
"""
from __future__ import annotations

import hashlib
import json
import random
import shutil
import time
from pathlib import Path

DEPTHS = (0, 1, 2, 3, 4)
SPINS = (0, 1, 2, 3)
COATS = ('ashen', 'ochre', 'umber')
TIDES = ('ebb', 'neap', 'flood')                               # a cycle: ebb -> neap -> flood -> ebb
STELES = ('flint', 'basalt', 'shale')
VALUE_OBJECTS = tuple(f'k.{v}' for v in STELES)
ATTRS = ('kind', 'depth', 'spin', 'coat', 'tide', 'value')
BLANK = {'kind': 'absent', 'depth': '-', 'spin': '-', 'coat': '-', 'tide': '-', 'value': '-'}
SPIN_DRAW = (0, 1, 1, 2, 2, 3)                                 # how the outside leaves a stele's spin each day (seeded)
TURN_P = 0.3                                                   # an urn's tide moves one step on over a day
LEAVE_AGE = 4                                                  # an urn is taken away after this many days (ticks)

# ------------------------------------------------------------ the world's laws
# An effect law: (x, s) -> the urn's changed attributes, read from the urn x and the stele s as they were before the
# call (s is None for a law that reads no stele). A tool that follows two laws applies both to the state before.
EFFECT = {
    'E1': lambda x, s: {'depth': min(x['depth'] + s['spin'], DEPTHS[-1])},
    'E2': lambda x, s: {'depth': max(x['depth'] - 1, 0)},
    'E3': lambda x, s: {'coat': s['coat']},
    'E4': lambda x, s: {'tide': TIDES[(TIDES.index(x['tide']) + 1) % len(TIDES)]},
    'E5': lambda x, s: {'spin': min(max(x['spin'] + (1 if x['coat'] == s['coat'] else -1), 0), SPINS[-1])},
    'E6': lambda x, s: {'depth': x['spin'], 'spin': min(x['depth'], SPINS[-1])},
    'E7': lambda x, s: {'spin': min(abs(x['depth'] - s['depth']), SPINS[-1])},
    'E8': lambda x, s: {'coat': COATS[x['spin'] % len(COATS)]},
    'E9': lambda x, s: {'spin': 0},
    'E10': lambda x, s: {'tide': s['tide']},
    'E11': lambda x, s: {'value': 'bound'},
}
READS_STELE = frozenset({'E1', 'E3', 'E5', 'E7', 'E10'})
# A refusal condition: (x, s) -> True when the call is refused. Two more hold for every tool of every place: a bound
# urn never changes again (R1), and a call that would change nothing is refused (R2).
REFUSE = {
    'R3': lambda x, s: x['tide'] == 'ebb',
    'R4': lambda x, s: s['spin'] == 0,
    'R5': lambda x, s: x['coat'] != s['coat'],
    'R6': lambda x, s: x['depth'] > s['depth'],
}
NEEDS_STELE = frozenset({'R4', 'R5', 'R6'})


def tool(*laws, cap=None):
    """A place's tool: the effect laws (1-2) and refusal conditions it follows; its arity follows from them."""
    eff = tuple(l for l in laws if l in EFFECT)
    ref = tuple(l for l in laws if l in REFUSE)
    assert eff and len(eff) + len(ref) == len(laws)
    return {'effects': eff, 'refuse': ref, 'arity': 2 if (set(eff) & READS_STELE or set(ref) & NEEDS_STELE) else 1, 'cap': cap}


def result(spec, x, s=None):
    """What a call of this tool gives: the urn's attributes after it, or None when the call is refused. x and s are the
    observed attributes of the arguments before the call."""
    if not x or x.get('kind') != 'urn' or x.get('value') == 'bound':
        return None
    if spec['arity'] == 2 and (not s or s.get('kind') != 'stele'):
        return None
    if any(REFUSE[r](x, s) for r in spec['refuse']):
        return None
    new = dict(x)
    for e in spec['effects']:
        new.update(EFFECT[e](x, s))
    return None if new == x else new


class IsleWorkspace:
    """One place. A subclass gives BODY, TABLE (tool name -> tool(...)) and RETIRE (tool name -> the name that does its
    work once '<tool>_retired' is in the drift)."""
    BODY = ''
    TABLE = {}
    RETIRE = {}
    TOOLS = {}
    CAPABILITY = {}
    drift = frozenset()

    def __init__(self, root, create=True, seed=0):
        self.root = Path(root).absolute()
        self.path = self.root / f'{self.BODY}.json'
        if create:
            self.root.mkdir(parents=True, exist_ok=False)
            rng = random.Random(f'{self.BODY}-{seed}-steles')
            self._write({'urns': {}, 'steles': {v: self._draw(rng) for v in STELES}, 'seed': seed, 'tick': 0})

    @staticmethod
    def _draw(rng):
        return {'depth': rng.choice(DEPTHS), 'spin': rng.choice(SPIN_DRAW), 'coat': rng.choice(COATS), 'tide': rng.choice(TIDES)}

    def _read(self):
        return json.loads(self.path.read_text(encoding='utf-8'))

    def _write(self, spec):
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(spec, indent=1, sort_keys=True), encoding='utf-8')
        tmp.replace(self.path)

    def _log(self, **row):
        with open(self.root / 'world_log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(row, sort_keys=True) + '\n')

    def fingerprint(self):
        return hashlib.sha256(self.path.read_bytes()).hexdigest()[:12]

    # ------------------------------------------------------------ the world on its own
    def add_urns(self, urns):
        """New urns: {id: {'depth': ..., 'spin': ..., 'coat': ..., 'tide': ...}}."""
        spec = self._read()
        for uid, u in urns.items():
            spec['urns'][uid] = {'depth': u['depth'], 'spin': u['spin'], 'coat': u['coat'], 'tide': u['tide'], 'bound': False, 'age': 0}
        self._write(spec)
        self._log(event='arrive', actor='outside', items={u: self.attrs_of(spec, u) for u in sorted(urns)}, after=self.fingerprint())

    def tick(self):
        """A day passes: every urn ages and the oldest are taken away, the tide of some urns moves one step on, and
        every stele is left as drawn from (seed, tick). Logged as the outside's doing."""
        spec = self._read()
        seen_before = {o: self.attrs_of(spec, o) for o in list(spec['urns']) + list(VALUE_OBJECTS)}
        spec['tick'] += 1
        rng = random.Random(f"{self.BODY}-{spec['seed']}-tick-{spec['tick']}")
        changes = []
        for uid in sorted(spec['urns']):
            u = spec['urns'][uid]
            u['age'] += 1
            if u['age'] > LEAVE_AGE:
                del spec['urns'][uid]
                changes.append((uid, 'taken', True))
                continue
            if not u['bound'] and rng.random() < TURN_P:
                u['tide'] = TIDES[(TIDES.index(u['tide']) + 1) % len(TIDES)]
                changes.append((uid, 'tide', u['tide']))
        for v in STELES:
            new = self._draw(rng)
            for k in sorted(new):
                if new[k] != spec['steles'][v][k]:
                    changes.append((f'k.{v}', k, new[k]))
            spec['steles'][v] = new
        self._write(spec)
        moved = sorted({c[0] for c in changes})
        self._log(event='tick', actor='outside', tick=spec['tick'], changes=changes, after=self.fingerprint(),
                  obs_before={o: seen_before[o] for o in moved}, obs_after={o: self.attrs_of(spec, o) for o in moved})
        return changes

    # ------------------------------------------------------------ observation
    @staticmethod
    def attrs_of(spec, obj):
        if obj.startswith('k.') and obj[2:] in STELES:
            s = spec['steles'][obj[2:]]
            return {'kind': 'stele', 'depth': s['depth'], 'spin': s['spin'], 'coat': s['coat'], 'tide': s['tide'], 'value': obj[2:]}
        u = spec['urns'].get(obj)
        if u is None:
            return dict(BLANK)
        return {'kind': 'urn', 'depth': u['depth'], 'spin': u['spin'], 'coat': u['coat'], 'tide': u['tide'],
                'value': 'bound' if u['bound'] else '-'}

    def _names(self):
        """Tool name now -> the table's tool it does the work of (a retired name stays callable and does nothing)."""
        gone = {t for t in self.RETIRE if f'{t}_retired' in self.drift}
        return {t: (None if t in gone else t) for t in self.TABLE} | {self.RETIRE[t]: t for t in gone}

    def tools(self):
        return {n: self.TABLE[t or n]['arity'] for n, t in self._names().items()}

    def existing(self):
        return sorted(set(self._read()['urns']) | set(VALUE_OBJECTS))

    def universe(self, paths=()):
        return sorted(set(self.existing()) | set(paths))

    def observe(self, paths=()):
        spec = self._read()
        return {o: self.attrs_of(spec, o) for o in self.universe(paths)}

    def kind(self, obj):
        return self.attrs_of(self._read(), obj)['kind']

    def lab_copy(self, root, objs=(), seen=None):
        """A fresh copy with the same state; the lab never ticks and logs to its own folder."""
        root = Path(root)
        if root.exists():
            shutil.rmtree(root)
        lab = type(self)(root, create=True)
        lab._write(self._read())
        lab.drift = self.drift
        return lab

    def actions(self, universe):
        out = []
        for name, ar in self.tools().items():
            out += [(name, (a,)) for a in universe] if ar == 1 else [(name, (a, b)) for a in universe for b in universe if a != b]
        return out

    # ------------------------------------------------------------ action
    def execute(self, tool, args, capabilities, actor='learner'):
        """actor is for the log only: 'learner' (default), 'teacher', 'person', 'evaluator'."""
        t0 = time.perf_counter()
        tools, names = self.tools(), self._names()
        before = self.fingerprint()
        if tool not in tools or len(args) != tools[tool] or len(set(args)) != len(args):
            self._log(event='invalid', actor=actor, tool=tool, args=list(args), before=before)
            raise ValueError('invalid action')
        cap = self.CAPABILITY.get(tool)
        if cap and not capabilities.get(cap):
            self._log(event='act', actor=actor, tool=tool, args=list(args), ok=False, error='blocked', before=before, after=before)
            return {'ok': False, 'blocked': True, 'error': f'capability {cap} not granted', 'ms': 0.0}
        spec = self._read()
        obs_before = {o: self.attrs_of(spec, o) for o in args}   # what was observed before and after: every argument
        new = result(self.TABLE[names[tool]], *[obs_before[o] for o in args]) if names[tool] else None
        ok = new is not None
        if ok:
            u = spec['urns'][args[0]]
            u.update({k: new[k] for k in ('depth', 'spin', 'coat', 'tide')})
            u['bound'] = new['value'] == 'bound'
            self._write(spec)
        obs_after = {o: self.attrs_of(spec, o) for o in args}
        self._log(event='act', actor=actor, tool=tool, args=list(args), ok=bool(ok), before=before, after=self.fingerprint(),
                  obs_before=obs_before, obs_after=obs_after)
        return {'ok': bool(ok), 'blocked': False, 'error': '' if ok else 'precondition', 'ms': (time.perf_counter() - t0) * 1000}
