"""Eighth body: a bike repair shop (built body-side by a separate agent). Bikes in for repair and a few air pumps; one
JSON state inside a sandbox folder; nothing outside it is touched.

Bikes are inflated at a pump, have air released, have their brakes bled and are delivered. Inflating moves the tyre
pressure along an ordered scale (limp < soft < firm < taut < burst) and how far it moves is read from the pump's gauge at
that moment (trickle: one step, gust: two steps; a shut pump inflates nothing); the pump is not changed by inflating.
Releasing air moves the pressure one step down (a limp or burst tyre gives nothing). Bleeding turns spongy brakes sharp;
a steel frame has rim brakes and cannot be bled. Between days the outside turns the pumps' gauges (other mechanics), some
firm or taut tyres leak one step, and old bikes are collected (they disappear); every outside change is logged with
actor 'outside' and drawn from (seed, tick). Delivering a bike is irreversible and needs the capability
'deliver_bikes'; a delivered bike never changes again.

Objects: bike ids (opaque, e.g. 'k3y1') and pump objects 'p.track', 'p.foot', 'p.mini'. Every object has the same five
attributes: kind, pressure, frame, brake, value (a bike's pressure is its tyres', a pump's pressure is its gauge; a
bike's value is 'delivered' or '-', a pump's value is its name). Tool preconditions are enforced here and not exported.
"""
from __future__ import annotations

import hashlib
import json
import random
import shutil
import time
from pathlib import Path

PRESSURES = ('limp', 'soft', 'firm', 'taut', 'burst')         # ordered; burst is spoiled
FRAMES = ('steel', 'alloy', 'bamboo')
BRAKES = ('spongy', 'sharp')
GAUGES = ('shut', 'trickle', 'gust')
STEP = {'shut': 0, 'trickle': 1, 'gust': 2}                    # pressure steps one inflate moves, read from the pump's gauge
GAUGE_DRAW = ('trickle', 'trickle', 'gust', 'gust', 'shut')    # how other mechanics leave a gauge each day (seeded)
PUMPS = ('track', 'foot', 'mini')
VALUE_OBJECTS = tuple(f'p.{v}' for v in PUMPS)
LEAK_P = 0.3                                                   # a firm or taut tyre loses one step over a day
COLLECT_AGE = 4                                                # a bike leaves after this many days (ticks) in the shop
TOOLS = {'inflate': 2, 'release': 1, 'bleed': 1, 'deliver': 1}
CAPABILITY = {'deliver': 'deliver_bikes'}
BLANK = {'kind': 'absent', 'pressure': '-', 'frame': '-', 'brake': '-', 'value': '-'}


class SpokeWorkspace:
    BODY = 'spoke'
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
    drift = frozenset()            # changed world rules: {'bleed_retired', 'release_retired'}

    def __init__(self, root, create=True, seed=0):
        self.root = Path(root).absolute()
        self.path = self.root / 'spoke.json'
        if create:
            self.root.mkdir(parents=True, exist_ok=False)
            rng = random.Random(f'spoke-{seed}-pumps')
            pumps = {v: {'gauge': rng.choice(GAUGE_DRAW[:4])} for v in PUMPS}
            self._write({'bikes': {}, 'pumps': pumps, 'seed': seed, 'tick': 0})

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
    def add_bikes(self, bikes):
        """New bikes: {id: {'pressure': ..., 'frame': ..., 'brake': 'spongy' | 'sharp'}}."""
        spec = self._read()
        for bid, b in bikes.items():
            spec['bikes'][bid] = {'pressure': b['pressure'], 'frame': b['frame'], 'brake': b.get('brake', 'spongy'),
                                  'delivered': False, 'age': 0}
        self._write(spec)
        self._log(event='arrive', actor='outside', items={b: self.attrs_of(spec, b) for b in sorted(bikes)}, after=self.fingerprint())

    def tick(self):
        """A day passes: every bike ages and the oldest leave (collected), some firm or taut tyres leak one step, and
        other mechanics leave every pump's gauge at a setting drawn from (seed, tick). Logged as the outside's doing."""
        spec = self._read()
        seen_before = {o: self.attrs_of(spec, o) for o in list(spec['bikes']) + list(VALUE_OBJECTS)}
        spec['tick'] += 1
        rng = random.Random(f"spoke-{spec['seed']}-tick-{spec['tick']}")
        changes = []
        for bid in sorted(spec['bikes']):
            b = spec['bikes'][bid]
            b['age'] += 1
            if b['age'] > COLLECT_AGE:
                del spec['bikes'][bid]
                changes.append((bid, 'collected', True))
                continue
            if b['pressure'] in ('firm', 'taut') and not b['delivered'] and rng.random() < LEAK_P:
                b['pressure'] = PRESSURES[PRESSURES.index(b['pressure']) - 1]
                changes.append((bid, 'pressure', b['pressure']))
        for v in PUMPS:
            gauge = rng.choice(GAUGE_DRAW)
            if gauge != spec['pumps'][v]['gauge']:
                spec['pumps'][v]['gauge'] = gauge
                changes.append((f'p.{v}', 'gauge', gauge))
        self._write(spec)
        moved = sorted({c[0] for c in changes})
        self._log(event='tick', actor='outside', tick=spec['tick'], changes=changes, after=self.fingerprint(),
                  obs_before={o: seen_before[o] for o in moved}, obs_after={o: self.attrs_of(spec, o) for o in moved})
        return changes

    # ------------------------------------------------------------ observation
    @staticmethod
    def attrs_of(spec, obj):
        if obj.startswith('p.') and obj[2:] in PUMPS:
            return {'kind': 'pump', 'pressure': spec['pumps'][obj[2:]]['gauge'], 'frame': '-', 'brake': '-', 'value': obj[2:]}
        b = spec['bikes'].get(obj)
        if b is None:
            return dict(BLANK)
        return {'kind': 'bike', 'pressure': b['pressure'], 'frame': b['frame'], 'brake': b['brake'],
                'value': 'delivered' if b['delivered'] else '-'}

    def tools(self):
        t = dict(TOOLS)
        if 'bleed_retired' in self.drift:
            t['prime'] = 1
        if 'release_retired' in self.drift:
            t['drop'] = 1
        return t

    def existing(self):
        return sorted(set(self._read()['bikes']) | set(VALUE_OBJECTS))

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
        lab = SpokeWorkspace(root, create=True)
        lab._write(self._read())
        lab.drift = self.drift
        return lab

    def actions(self_or_universe, universe=None):
        tools = self_or_universe.tools() if universe is not None else TOOLS
        universe = self_or_universe if universe is None else universe
        out = []
        for tool, ar in tools.items():
            out += [(tool, (a,)) for a in universe] if ar == 1 else [(tool, (a, b)) for a in universe for b in universe if a != b]
        return out

    # ------------------------------------------------------------ action
    def execute(self, tool, args, capabilities, actor='learner'):
        """actor is for the log only: 'learner' (default), 'teacher', 'person', 'evaluator'."""
        t0 = time.perf_counter()
        tools = self.tools()
        before = self.fingerprint()
        if tool not in tools or len(args) != tools[tool] or len(set(args)) != len(args):
            self._log(event='invalid', actor=actor, tool=tool, args=list(args), before=before)
            raise ValueError('invalid action')
        cap = CAPABILITY.get(tool)
        if cap and not capabilities.get(cap):
            self._log(event='act', actor=actor, tool=tool, args=list(args), ok=False, error='blocked', before=before, after=before)
            return {'ok': False, 'blocked': True, 'error': f'capability {cap} not granted', 'ms': 0.0}
        spec = self._read()
        obs_before = {o: self.attrs_of(spec, o) for o in args}   # what was observed before and after: every argument
        ok = getattr(self, '_tool_' + tool)(spec, *args)
        if ok:
            self._write(spec)
        obs_after = {o: self.attrs_of(spec, o) for o in args}
        self._log(event='act', actor=actor, tool=tool, args=list(args), ok=bool(ok), before=before, after=self.fingerprint(),
                  obs_before=obs_before, obs_after=obs_after)
        return {'ok': bool(ok), 'blocked': False, 'error': '' if ok else 'precondition', 'ms': (time.perf_counter() - t0) * 1000}

    @staticmethod
    def _bike(spec, x):
        b = spec['bikes'].get(x)
        return None if b is None or b['delivered'] else b   # a delivered bike never changes again

    @staticmethod
    def _pump(spec, v):
        return spec['pumps'].get(v[2:]) if v.startswith('p.') else None

    def _tool_inflate(self, spec, x, v):
        """The pressure moves up the scale by the pump's gauge now (trickle one step, gust two; it stops at burst). A
        burst tyre and a shut pump inflate nothing; the pump is unchanged."""
        b, pump = self._bike(spec, x), self._pump(spec, v)
        if b is None or pump is None or b['pressure'] == PRESSURES[-1] or STEP[pump['gauge']] == 0:
            return False
        b['pressure'] = PRESSURES[min(PRESSURES.index(b['pressure']) + STEP[pump['gauge']], len(PRESSURES) - 1)]
        return True

    def _let_out(self, spec, x):
        """One step of air out; a limp or burst tyre gives nothing."""
        b = self._bike(spec, x)
        if b is None or b['pressure'] in (PRESSURES[0], PRESSURES[-1]):
            return False
        b['pressure'] = PRESSURES[PRESSURES.index(b['pressure']) - 1]
        return True

    def _tool_release(self, spec, x):
        return 'release_retired' not in self.drift and self._let_out(spec, x)

    def _tool_drop(self, spec, x):
        return 'release_retired' in self.drift and self._let_out(spec, x)

    def _sharpen(self, spec, x):
        """Spongy brakes go sharp; a steel frame's rim brakes cannot be bled."""
        b = self._bike(spec, x)
        if b is None or b['frame'] == 'steel' or b['brake'] != 'spongy':
            return False
        b['brake'] = 'sharp'
        return True

    def _tool_bleed(self, spec, x):
        return 'bleed_retired' not in self.drift and self._sharpen(spec, x)

    def _tool_prime(self, spec, x):
        return 'bleed_retired' in self.drift and self._sharpen(spec, x)

    def _tool_deliver(self, spec, x):
        b = self._bike(spec, x)
        if b is None:
            return False
        b['delivered'] = True                              # irreversible
        return True
