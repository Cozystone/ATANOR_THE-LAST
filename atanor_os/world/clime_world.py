"""Generation 2 body: climate bays (NEW_BODY_DESIGN.md). A small facility of bays, each with a heat level and air; a
sky object shows the weather. One JSON state inside a sandbox folder; nothing outside it is touched.

Structurally new against the four earlier bodies: an action's effect is relative (heat raises the level one step, so
the same action ends in different values on different bays), a legal action can harm (heating a hot bay scorches it,
chilling a frosty one ices it), and the attribute selections are made of drifts with the weather between commands.
The weather is always observable (the sky object), and every outside change is logged with actor 'outside', drawn
from (seed, tick) so a run replays. Sealing a bay is irreversible and needs the capability 'seal_bays'.

Objects: bay ids (opaque, e.g. 'c3k1'), the sky 'sky', wing objects 'w.north' ... Every object has the same five
attributes: kind, heat, air, wing, value. Tool preconditions are enforced here and not exported.
"""
from __future__ import annotations

import hashlib
import json
import random
import shutil
import time
from pathlib import Path

LEVELS = ('ice', 'frost', 'chill', 'mild', 'warm', 'hot', 'scorch')     # ice and scorch are harm
WINGS = ('north', 'south', 'east')
WEATHER = ('cold', 'fair', 'hot')
VALUE_OBJECTS = tuple(f'w.{w}' for w in WINGS)
TOOLS = {'heat': 1, 'chill': 1, 'vent': 1, 'route': 2, 'seal': 1}
CAPABILITY = {'seal': 'seal_bays'}
BLANK = {'kind': 'absent', 'heat': '-', 'air': '-', 'wing': '-', 'value': '-'}


class ClimeWorkspace:
    BODY = 'clime'
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
    drift = frozenset()            # changed world rules: {'heat_retired', 'vent_retired'}

    def __init__(self, root, create=True, seed=0):
        self.root = Path(root).absolute()
        self.path = self.root / 'clime.json'
        if create:
            self.root.mkdir(parents=True, exist_ok=False)
            self._write({'bays': {}, 'weather': 'fair', 'seed': seed, 'tick': 0})

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
    def add_bays(self, bays):
        """New bays: {id: {'heat': ..., 'air': ..., 'wing': ...}}."""
        spec = self._read()
        for bid, b in bays.items():
            spec['bays'][bid] = {'heat': b['heat'], 'air': b['air'], 'wing': b['wing'], 'sealed': False}
        self._write(spec)
        self._log(event='arrive', actor='outside', bays={b: spec['bays'][b] for b in sorted(bays)}, after=self.fingerprint())

    def tick(self):
        """Time passes: the weather changes, every unsealed bay is pulled one step toward it (never into harm), and some
        bays' air goes stale. Drawn from (seed, tick), so it replays; logged as the outside's doing."""
        spec = self._read()
        spec['tick'] += 1
        rng = random.Random(f"clime-{spec['seed']}-tick-{spec['tick']}")
        spec['weather'] = spec['weather'] if rng.random() < 0.4 else rng.choice(WEATHER)
        changes = []
        for bid in sorted(spec['bays']):
            b = spec['bays'][bid]
            if b['sealed'] or b['heat'] in ('ice', 'scorch'):
                continue
            i = LEVELS.index(b['heat'])
            if spec['weather'] == 'cold' and i > LEVELS.index('frost'):
                b['heat'] = LEVELS[i - 1]
                changes.append((bid, 'heat', b['heat']))
            elif spec['weather'] == 'hot' and i < LEVELS.index('hot'):
                b['heat'] = LEVELS[i + 1]
                changes.append((bid, 'heat', b['heat']))
            if b['air'] == 'fresh' and rng.random() < 0.25:
                b['air'] = 'stale'
                changes.append((bid, 'air', 'stale'))
        self._write(spec)
        self._log(event='tick', actor='outside', tick=spec['tick'], weather=spec['weather'], changes=changes, after=self.fingerprint())
        return changes

    # ------------------------------------------------------------ observation
    @staticmethod
    def attrs_of(spec, obj):
        if obj == 'sky':
            return {'kind': 'sky', 'heat': spec['weather'], 'air': '-', 'wing': '-', 'value': '-'}
        if obj.startswith('w.') and obj[2:] in WINGS:
            return {'kind': 'wing', 'heat': '-', 'air': '-', 'wing': '-', 'value': obj[2:]}
        b = spec['bays'].get(obj)
        if b is None:
            return dict(BLANK)
        return {'kind': 'bay', 'heat': b['heat'], 'air': b['air'], 'wing': b['wing'], 'value': 'sealed' if b['sealed'] else '-'}

    def tools(self):
        t = dict(TOOLS)
        if 'heat_retired' in self.drift:
            t['stoke'] = 1
        if 'vent_retired' in self.drift:
            t['flush'] = 1
        return t

    def existing(self):
        return sorted(set(self._read()['bays']) | set(VALUE_OBJECTS) | {'sky'})

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
        lab = ClimeWorkspace(root, create=True)
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
        ok = getattr(self, '_tool_' + tool)(spec, *args)
        if ok:
            self._write(spec)
        self._log(event='act', actor=actor, tool=tool, args=list(args), ok=bool(ok), before=before, after=self.fingerprint())
        return {'ok': bool(ok), 'blocked': False, 'error': '' if ok else 'precondition', 'ms': (time.perf_counter() - t0) * 1000}

    @staticmethod
    def _bay(spec, x):
        b = spec['bays'].get(x)
        return None if b is None or b['sealed'] else b

    def _step(self, spec, x, d):
        b = self._bay(spec, x)
        if b is None:
            return False
        i = LEVELS.index(b['heat']) + d
        if i < 0 or i >= len(LEVELS):
            return False
        b['heat'] = LEVELS[i]                              # one step; past hot is scorch, past frost is ice (harm)
        return True

    def _tool_heat(self, spec, x):
        return 'heat_retired' not in self.drift and self._step(spec, x, +1)

    def _tool_stoke(self, spec, x):
        return 'heat_retired' in self.drift and self._step(spec, x, +1)

    def _tool_chill(self, spec, x):
        return self._step(spec, x, -1)

    def _air(self, spec, x):
        b = self._bay(spec, x)
        if b is None or b['air'] != 'stale':
            return False
        b['air'] = 'fresh'
        return True

    def _tool_vent(self, spec, x):
        return 'vent_retired' not in self.drift and self._air(spec, x)

    def _tool_flush(self, spec, x):
        return 'vent_retired' in self.drift and self._air(spec, x)

    def _tool_route(self, spec, x, w):
        b = self._bay(spec, x)
        if b is None or not w.startswith('w.') or w[2:] not in WINGS or b['wing'] == w[2:]:
            return False
        b['wing'] = w[2:]
        return True

    def _tool_seal(self, spec, x):
        b = self._bay(spec, x)
        if b is None:
            return False
        b['sealed'] = True                                 # irreversible
        return True
