"""Seventh body: a bakery oven line (built body-side by a separate agent). Loaves of dough and a few ovens; one JSON
state inside a sandbox folder; nothing outside it is touched.

Loaves are proved (slack -> risen), knocked back (risen -> slack), baked in an oven and boxed. Baking moves the crust
along an ordered scale (doughy < blond < golden < brown < charred) and how far it moves is read from the oven's dial
at that moment (gentle: one step, fierce: two steps; an unlit oven bakes nothing). The oven is not changed by baking.
Between days the outside turns the ovens' dials (other bakers), some slack dough rises on its own, and old loaves are
sold (they disappear); every outside change is logged with actor 'outside' and drawn from (seed, tick). Boxing a loaf is
irreversible and needs the capability 'box_loaves'; a boxed loaf never changes again.

Objects: loaf ids (opaque, e.g. 'q3z1') and oven objects 'o.brick', 'o.stone', 'o.clay'. Every object has the same five
attributes: kind, crust, grain, proof, value (a loaf's proof is slack/risen, an oven's proof is its dial; a loaf's value
is 'boxed' or '-', an oven's value is its name). Tool preconditions are enforced here and not exported.
"""
from __future__ import annotations

import hashlib
import json
import random
import shutil
import time
from pathlib import Path

CRUSTS = ('doughy', 'blond', 'golden', 'brown', 'charred')     # ordered; charred is spoiled
GRAINS = ('rye', 'spelt', 'barley')
DIALS = ('unlit', 'gentle', 'fierce')
STEP = {'unlit': 0, 'gentle': 1, 'fierce': 2}                   # crust steps one bake moves, read from the oven's dial
DIAL_DRAW = ('gentle', 'gentle', 'fierce', 'fierce', 'unlit')   # how other bakers leave a dial each day (seeded)
OVENS = ('brick', 'stone', 'clay')
VALUE_OBJECTS = tuple(f'o.{v}' for v in OVENS)
RISE_P = 0.35                                                   # slack dough rises on its own over a day
SELL_AGE = 4                                                    # a loaf leaves after this many days (ticks) on the line
TOOLS = {'bake': 2, 'prove': 1, 'knock': 1, 'box': 1}
CAPABILITY = {'box': 'box_loaves'}
BLANK = {'kind': 'absent', 'crust': '-', 'grain': '-', 'proof': '-', 'value': '-'}


class CrumbWorkspace:
    BODY = 'crumb'
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
    drift = frozenset()            # changed world rules: {'prove_retired', 'knock_retired'}

    def __init__(self, root, create=True, seed=0):
        self.root = Path(root).absolute()
        self.path = self.root / 'crumb.json'
        if create:
            self.root.mkdir(parents=True, exist_ok=False)
            rng = random.Random(f'crumb-{seed}-ovens')
            ovens = {v: {'dial': rng.choice(DIAL_DRAW[:4])} for v in OVENS}
            self._write({'loaves': {}, 'ovens': ovens, 'seed': seed, 'tick': 0})

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
    def add_loaves(self, loaves):
        """New loaves: {id: {'crust': ..., 'grain': ..., 'proof': 'slack' | 'risen'}}."""
        spec = self._read()
        for lid, b in loaves.items():
            spec['loaves'][lid] = {'crust': b['crust'], 'grain': b['grain'], 'proof': b.get('proof', 'slack'), 'boxed': False, 'age': 0}
        self._write(spec)
        self._log(event='arrive', actor='outside', items={b: self.attrs_of(spec, b) for b in sorted(loaves)}, after=self.fingerprint())

    def tick(self):
        """A day passes: every loaf ages and the oldest leave (sold), some slack dough rises on its own, and other bakers
        leave every oven's dial at a setting drawn from (seed, tick). Logged as the outside's doing."""
        spec = self._read()
        seen_before = {o: self.attrs_of(spec, o) for o in list(spec['loaves']) + list(VALUE_OBJECTS)}
        spec['tick'] += 1
        rng = random.Random(f"crumb-{spec['seed']}-tick-{spec['tick']}")
        changes = []
        for lid in sorted(spec['loaves']):
            b = spec['loaves'][lid]
            b['age'] += 1
            if b['age'] > SELL_AGE:
                del spec['loaves'][lid]
                changes.append((lid, 'sold', True))
                continue
            if b['proof'] == 'slack' and b['crust'] == 'doughy' and not b['boxed'] and rng.random() < RISE_P:
                b['proof'] = 'risen'
                changes.append((lid, 'proof', 'risen'))
        for v in OVENS:
            dial = rng.choice(DIAL_DRAW)
            if dial != spec['ovens'][v]['dial']:
                spec['ovens'][v]['dial'] = dial
                changes.append((f'o.{v}', 'dial', dial))
        self._write(spec)
        moved = sorted({c[0] for c in changes})
        self._log(event='tick', actor='outside', tick=spec['tick'], changes=changes, after=self.fingerprint(),
                  obs_before={o: seen_before[o] for o in moved}, obs_after={o: self.attrs_of(spec, o) for o in moved})
        return changes

    # ------------------------------------------------------------ observation
    @staticmethod
    def attrs_of(spec, obj):
        if obj.startswith('o.') and obj[2:] in OVENS:
            return {'kind': 'oven', 'crust': '-', 'grain': '-', 'proof': spec['ovens'][obj[2:]]['dial'], 'value': obj[2:]}
        b = spec['loaves'].get(obj)
        if b is None:
            return dict(BLANK)
        return {'kind': 'loaf', 'crust': b['crust'], 'grain': b['grain'], 'proof': b['proof'], 'value': 'boxed' if b['boxed'] else '-'}

    def tools(self):
        t = dict(TOOLS)
        if 'prove_retired' in self.drift:
            t['leaven'] = 1
        if 'knock_retired' in self.drift:
            t['punch'] = 1
        return t

    def existing(self):
        return sorted(set(self._read()['loaves']) | set(VALUE_OBJECTS))

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
        lab = CrumbWorkspace(root, create=True)
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
    def _loaf(spec, x):
        b = spec['loaves'].get(x)
        return None if b is None or b['boxed'] else b      # a boxed loaf never changes again

    @staticmethod
    def _oven(spec, v):
        return spec['ovens'].get(v[2:]) if v.startswith('o.') else None

    def _tool_bake(self, spec, x, v):
        """The crust moves up the scale by the oven's dial now (gentle one step, fierce two; it stops at charred). Slack
        dough, a charred loaf and an unlit oven bake nothing; the oven is unchanged."""
        b, oven = self._loaf(spec, x), self._oven(spec, v)
        if b is None or oven is None or b['proof'] != 'risen' or b['crust'] == CRUSTS[-1] or STEP[oven['dial']] == 0:
            return False
        b['crust'] = CRUSTS[min(CRUSTS.index(b['crust']) + STEP[oven['dial']], len(CRUSTS) - 1)]
        return True

    def _rise(self, spec, x):
        """Slack dough rises; baked bread and risen dough do not."""
        b = self._loaf(spec, x)
        if b is None or b['proof'] != 'slack' or b['crust'] != 'doughy':
            return False
        b['proof'] = 'risen'
        return True

    def _tool_prove(self, spec, x):
        return 'prove_retired' not in self.drift and self._rise(spec, x)

    def _tool_leaven(self, spec, x):
        return 'prove_retired' in self.drift and self._rise(spec, x)

    def _deflate(self, spec, x):
        """Risen dough goes slack again; baked bread cannot be knocked back."""
        b = self._loaf(spec, x)
        if b is None or b['proof'] != 'risen' or b['crust'] != 'doughy':
            return False
        b['proof'] = 'slack'
        return True

    def _tool_knock(self, spec, x):
        return 'knock_retired' not in self.drift and self._deflate(spec, x)

    def _tool_punch(self, spec, x):
        return 'knock_retired' in self.drift and self._deflate(spec, x)

    def _tool_box(self, spec, x):
        b = self._loaf(spec, x)
        if b is None:
            return False
        b['boxed'] = True                                  # irreversible
        return True
