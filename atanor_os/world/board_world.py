"""Third body: a small task board. Cards carry a mark, sit in a tray (or none) and have a level; trays are fixed
objects with a hue; marks and levels are value objects that tools take as second arguments. The state is
`board.json` inside a real directory (written atomically). Nothing here reuses the file or screen bodies: no paths,
extensions, panels, filters or sorts, and other tool names.

Objects: card ids (opaque, e.g. 'q07'; absent until they arrive), tray ids ('t1'..'t4'), mark objects
('m.urgent' ...), level objects ('l.high' ...). Every object has the same five attributes: kind, mark, tray, level,
value. Tool preconditions are enforced here but not exported: they are what the learner has to find.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

TRAYS = {'t1': 'amber', 't2': 'teal', 't3': 'plum', 't4': 'slate'}
MARKS = ('urgent', 'idea', 'defect', 'chore', 'memo')
LEVELS = ('low', 'mid', 'high')
VALUE_OBJECTS = tuple([f'm.{m}' for m in MARKS] + [f'l.{v}' for v in LEVELS])
TOOLS = {'stamp': 2, 'lodge': 2, 'unlodge': 1, 'lift': 2, 'scrap': 1}
CAPABILITY = {'scrap': 'scrap_cards'}
BLANK = {'kind': 'absent', 'mark': '-', 'tray': '-', 'level': '-', 'value': '-'}


def is_value(obj):
    return obj.startswith('m.') or obj.startswith('l.')


class BoardWorkspace:
    BODY = 'board'
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
    drift = frozenset()            # changed world rules: {'lodge_retired', 'stamp_retired'}

    def __init__(self, root, create=True, cards=None):
        self.root = Path(root).absolute()
        self.path = self.root / 'board.json'
        if create:
            self.root.mkdir(parents=True, exist_ok=False)
            self._write({'cards': dict(cards or {})})

    def _read(self):
        return json.loads(self.path.read_text(encoding='utf-8'))

    def _write(self, spec):
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(spec, indent=1, sort_keys=True), encoding='utf-8')
        tmp.replace(self.path)

    def add_cards(self, cards):
        """The world: new cards arrive (each {'mark': m}); they start in no tray, at the low level."""
        spec = self._read()
        for cid, c in cards.items():
            spec['cards'][cid] = {'mark': c['mark'], 'tray': '-', 'level': 'low'}
        self._write(spec)

    @staticmethod
    def attrs_of(spec, obj):
        if obj in TRAYS:
            return {'kind': 'tray', 'mark': '-', 'tray': '-', 'level': '-', 'value': TRAYS[obj]}
        if is_value(obj):
            k, v = obj.split('.', 1)
            return {'kind': 'mark' if k == 'm' else 'level', 'mark': '-', 'tray': '-', 'level': '-', 'value': v}
        c = spec['cards'].get(obj)
        if c is None:
            return dict(BLANK)
        return {'kind': 'card', 'mark': c['mark'], 'tray': TRAYS.get(c['tray'], '-'), 'level': c['level'], 'value': '-'}

    def tools(self):
        t = dict(TOOLS)
        if 'lodge_retired' in self.drift:
            t['slot'] = 2
        if 'stamp_retired' in self.drift:
            t['brand'] = 2
        return t

    def existing(self):
        return sorted(set(self._read()['cards']) | set(TRAYS) | set(VALUE_OBJECTS))

    def kind(self, obj):
        return self.attrs_of(self._read(), obj)['kind']

    def lab_copy(self, root, objs=(), seen=None):
        root = Path(root)
        if root.exists():
            import shutil
            shutil.rmtree(root)
        lab = BoardWorkspace(root, create=True)
        lab._write(self._read())
        lab.drift = self.drift
        return lab

    def lab_from_state(self, root, state):
        root = Path(root)
        if root.exists():
            import shutil
            shutil.rmtree(root)
        hue_tray = {h: t for t, h in TRAYS.items()}
        cards = {o: {'mark': a['mark'], 'tray': hue_tray.get(a['tray'], '-'), 'level': a['level']}
                 for o, a in state.items() if a.get('kind') == 'card'}
        lab = BoardWorkspace(root, create=True)
        lab._write({'cards': cards})
        lab.drift = self.drift
        return lab

    def universe(self, paths=()):
        return sorted(set(self._read()['cards']) | set(TRAYS) | set(VALUE_OBJECTS) | set(paths))

    def observe(self, paths=()):
        spec = self._read()
        return {o: self.attrs_of(spec, o) for o in self.universe(paths)}

    def actions(self_or_universe, universe=None):
        tools = self_or_universe.tools() if universe is not None else TOOLS
        universe = self_or_universe if universe is None else universe
        out = []
        for tool, ar in tools.items():
            if ar == 1:
                out += [(tool, (a,)) for a in universe]
            else:
                out += [(tool, (a, b)) for a in universe for b in universe if a != b]
        return out

    def execute(self, tool, args, capabilities):
        t0 = time.perf_counter()
        tools = self.tools()
        if tool not in tools or len(args) != tools[tool] or len(set(args)) != len(args):
            raise ValueError('invalid action')
        cap = CAPABILITY.get(tool)
        if cap and not capabilities.get(cap):
            return {'ok': False, 'blocked': True, 'error': f'capability {cap} not granted', 'ms': 0.0}
        spec = self._read()
        ok = getattr(self, '_' + tool)(spec, *args)
        if ok:
            self._write(spec)
        return {'ok': bool(ok), 'blocked': False, 'error': '' if ok else 'precondition', 'ms': (time.perf_counter() - t0) * 1000}

    # --- tool semantics (the board's rules) ---
    def _stamp(self, spec, c, m):
        if 'stamp_retired' in self.drift or c not in spec['cards'] or not m.startswith('m.'):
            return False
        spec['cards'][c]['mark'] = m[2:]
        return True

    def _brand(self, spec, m, c):
        """Changed world only: marks, mark first."""
        if 'stamp_retired' not in self.drift or c not in spec['cards'] or not m.startswith('m.'):
            return False
        spec['cards'][c]['mark'] = m[2:]
        return True

    def _lodge(self, spec, c, t):
        if 'lodge_retired' in self.drift or c not in spec['cards'] or t not in TRAYS:
            return False
        spec['cards'][c]['tray'] = t
        return True

    def _slot(self, spec, t, c):
        """Changed world only: puts a card in a tray, tray first."""
        if 'lodge_retired' not in self.drift or c not in spec['cards'] or t not in TRAYS:
            return False
        spec['cards'][c]['tray'] = t
        return True

    @staticmethod
    def _unlodge(spec, c):
        if c not in spec['cards'] or spec['cards'][c]['tray'] == '-':
            return False
        spec['cards'][c]['tray'] = '-'
        return True

    @staticmethod
    def _lift(spec, c, lv):
        if c not in spec['cards'] or not lv.startswith('l.') or spec['cards'][c]['tray'] == '-':   # only cards in a tray
            return False
        spec['cards'][c]['level'] = lv[2:]
        return True

    @staticmethod
    def _scrap(spec, c):
        if c not in spec['cards']:
            return False
        del spec['cards'][c]
        return True
