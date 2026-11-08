"""Sixth body: a dye works (SIXTH_BODY_DESIGN.md). Bolts of cloth and a few dye vats; one JSON state inside a sandbox
folder; nothing outside it is touched.

Structurally new against the five earlier bodies: the second argument of 'dip' is a stateful object, not a fixed value
(every earlier second argument -- a tray, a mark, a level, a folder, a filter value, a place, a tag, a wing -- never
changes). Dipping changes BOTH arguments: the bolt takes the vat's current dye and gets wet, and the vat's stock goes
down by one (a consumed resource, a counter 8 .. 0). Whether the dip works depends on the second argument's state (a
spent vat, stock 0, cannot dye) and what it produces is read from the second argument's state (the bolt takes the dye
the vat holds now). Between days the outside refills low vats, often with another dye, dries some wet bolts and ships
old bolts (they disappear); every outside change is logged with actor 'outside' and drawn from (seed, tick).
Fixing a bolt (mordant) is irreversible and needs the capability 'fix_bolts'.

Objects: bolt ids (opaque, e.g. 'b3n1') and vat objects 'v.oak', 'v.elm', 'v.yew'. Every object has the same five
attributes: kind, hue, fibre, state, value (a bolt's state is dry/wet, a vat's state is its stock, a vat's value is its
name). Tool preconditions are enforced here and not exported.
"""
from __future__ import annotations

import hashlib
import json
import random
import shutil
import time
from pathlib import Path

DYES = ('indigo', 'madder', 'weld')
HUES = ('ecru',) + DYES                    # ecru: undyed
FIBRES = ('wool', 'silk', 'flax')
VATS = ('oak', 'elm', 'yew')
VALUE_OBJECTS = tuple(f'v.{v}' for v in VATS)
FULL = 8                                   # a vat's stock after a refill; one dip uses one
REFILL_AT = 2                              # the outside refills a vat whose stock is this low or lower
OTHERS_USE = (0, 0, 1, 1, 2, FULL)        # how much of a vat other dyers use in a day (seeded; sometimes all of it)
SHIP_AGE = 4                               # a bolt leaves after this many days (ticks) in the works
TOOLS = {'dip': 2, 'hang': 1, 'bleach': 1, 'fix': 1}
CAPABILITY = {'fix': 'fix_bolts'}
BLANK = {'kind': 'absent', 'hue': '-', 'fibre': '-', 'state': '-', 'value': '-'}


class DyeWorkspace:
    BODY = 'dye'
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
    drift = frozenset()            # changed world rules: {'hang_retired', 'bleach_retired'}

    def __init__(self, root, create=True, seed=0):
        self.root = Path(root).absolute()
        self.path = self.root / 'dye.json'
        if create:
            self.root.mkdir(parents=True, exist_ok=False)
            rng = random.Random(f'dye-{seed}-vats')
            vats = {v: {'hue': rng.choice(DYES), 'stock': FULL} for v in VATS}
            self._write({'bolts': {}, 'vats': vats, 'seed': seed, 'tick': 0})

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
    def add_bolts(self, bolts):
        """New bolts: {id: {'hue': ..., 'fibre': ..., 'state': 'dry' | 'wet'}}."""
        spec = self._read()
        for bid, b in bolts.items():
            spec['bolts'][bid] = {'hue': b['hue'], 'fibre': b['fibre'], 'state': b.get('state', 'dry'), 'fixed': False, 'age': 0}
        self._write(spec)
        self._log(event='arrive', actor='outside', items={b: self.attrs_of(spec, b) for b in sorted(bolts)}, after=self.fingerprint())

    def tick(self):
        """A day passes: every bolt ages and the oldest leave (shipped), some wet bolts dry; every vat whose stock was
        low is refilled to full with a dye drawn from (seed, tick) (often another one), and then other dyers use some of
        every vat's stock (a vat may be left spent until the next day). Logged as the outside's doing."""
        spec = self._read()
        seen_before = {o: self.attrs_of(spec, o) for o in list(spec['bolts']) + list(VALUE_OBJECTS)}
        spec['tick'] += 1
        rng = random.Random(f"dye-{spec['seed']}-tick-{spec['tick']}")
        changes = []
        for bid in sorted(spec['bolts']):
            b = spec['bolts'][bid]
            b['age'] += 1
            if b['age'] > SHIP_AGE:
                del spec['bolts'][bid]
                changes.append((bid, 'shipped', True))
                continue
            if b['state'] == 'wet' and not b['fixed'] and rng.random() < 0.5:
                b['state'] = 'dry'
                changes.append((bid, 'state', 'dry'))
        for v in VATS:
            vat = spec['vats'][v]
            if vat['stock'] <= REFILL_AT:
                vat['stock'], vat['hue'] = FULL, rng.choice(DYES)
                changes.append((f'v.{v}', 'refill', vat['hue']))
            used = min(vat['stock'], rng.choice(OTHERS_USE))
            if used:
                vat['stock'] -= used
                changes.append((f'v.{v}', 'used', used))
        self._write(spec)
        moved = sorted({c[0] for c in changes})
        self._log(event='tick', actor='outside', tick=spec['tick'], changes=changes, after=self.fingerprint(),
                  obs_before={o: seen_before[o] for o in moved}, obs_after={o: self.attrs_of(spec, o) for o in moved})
        return changes

    # ------------------------------------------------------------ observation
    @staticmethod
    def attrs_of(spec, obj):
        if obj.startswith('v.') and obj[2:] in VATS:
            vat = spec['vats'][obj[2:]]
            return {'kind': 'vat', 'hue': vat['hue'], 'fibre': '-', 'state': str(vat['stock']), 'value': obj[2:]}
        b = spec['bolts'].get(obj)
        if b is None:
            return dict(BLANK)
        return {'kind': 'bolt', 'hue': b['hue'], 'fibre': b['fibre'], 'state': b['state'], 'value': 'fixed' if b['fixed'] else '-'}

    def tools(self):
        t = dict(TOOLS)
        if 'hang_retired' in self.drift:
            t['peg'] = 1
        if 'bleach_retired' in self.drift:
            t['scour'] = 1
        return t

    def existing(self):
        return sorted(set(self._read()['bolts']) | set(VALUE_OBJECTS))

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
        lab = DyeWorkspace(root, create=True)
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
        obs_before = {o: self.attrs_of(spec, o) for o in args}   # what was observed before and after: both arguments
        ok = getattr(self, '_tool_' + tool)(spec, *args)
        if ok:
            self._write(spec)
        obs_after = {o: self.attrs_of(spec, o) for o in args}
        self._log(event='act', actor=actor, tool=tool, args=list(args), ok=bool(ok), before=before, after=self.fingerprint(),
                  obs_before=obs_before, obs_after=obs_after)
        return {'ok': bool(ok), 'blocked': False, 'error': '' if ok else 'precondition', 'ms': (time.perf_counter() - t0) * 1000}

    @staticmethod
    def _bolt(spec, x):
        b = spec['bolts'].get(x)
        return None if b is None or b['fixed'] else b       # a fixed bolt never changes again

    @staticmethod
    def _vat(spec, v):
        return spec['vats'].get(v[2:]) if v.startswith('v.') else None

    def _tool_dip(self, spec, x, v):
        """The bolt takes the dye the vat holds now and gets wet; the vat's stock goes down by one. A wet bolt does not
        take dye, and a spent vat (stock 0) dyes nothing."""
        b, vat = self._bolt(spec, x), self._vat(spec, v)
        if b is None or vat is None or b['state'] != 'dry' or vat['stock'] <= 0:
            return False
        b['hue'], b['state'] = vat['hue'], 'wet'
        vat['stock'] -= 1
        return True

    def _dry(self, spec, x):
        b = self._bolt(spec, x)
        if b is None or b['state'] != 'wet':
            return False
        b['state'] = 'dry'
        return True

    def _tool_hang(self, spec, x):
        return 'hang_retired' not in self.drift and self._dry(spec, x)

    def _tool_peg(self, spec, x):
        return 'hang_retired' in self.drift and self._dry(spec, x)

    def _strip(self, spec, x):
        """Back to undyed; silk does not take the bleach."""
        b = self._bolt(spec, x)
        if b is None or b['fibre'] == 'silk' or b['hue'] == 'ecru':
            return False
        b['hue'] = 'ecru'
        return True

    def _tool_bleach(self, spec, x):
        return 'bleach_retired' not in self.drift and self._strip(spec, x)

    def _tool_scour(self, spec, x):
        return 'bleach_retired' in self.drift and self._strip(spec, x)

    def _tool_fix(self, spec, x):
        b = self._bolt(spec, x)
        if b is None:
            return False
        b['fixed'] = True                                  # irreversible
        return True
