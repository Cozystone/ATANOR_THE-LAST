"""Second body (P3): a declarative workspace-viewer specification acted on by UI tools and drawn by a
trusted renderer (atanor_os/ui/renderer.py).

The world state is `view.json` inside a real directory (written atomically); the data the panels
show comes from a real file workspace. Objects: panel ids (absent until opened, like paths) and
value objects (`ext:txt`, `key:size`, `grp:ext`) that tools take as second arguments. Every object
has the same attributes: kind, filter, sort, group, value. Tool preconditions are enforced here
but, as in the filesystem body, not exported: they are what the learner has to find.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

PANELS = ('p1', 'p2', 'p3', 'cmp')
EXTS = ('all', 'txt', 'csv', 'md', 'log', 'json')
KEYS = ('name', 'ext', 'size')
GROUPS = ('none', 'ext')
VALUE_OBJECTS = tuple([f'ext:{e}' for e in EXTS] + [f'key:{k}' for k in KEYS] + [f'grp:{g}' for g in GROUPS])
TOOLS = {'open': 1, 'close': 1, 'filter': 2, 'sort': 2, 'group': 2, 'compare': 2}
CAPABILITY = {'close': 'close_panels'}
BLANK = {'kind': 'absent', 'filter': '-', 'sort': '-', 'group': '-', 'value': '-'}


def is_value(obj):
    return ':' in obj


class ViewWorkspace:
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
    drift = frozenset()            # P8b: changed world rules, e.g. {'compare_replace'}; empty = the original world

    def __init__(self, root, data, create=True, spec=None):
        self.root = Path(root).absolute()
        self.data = data                                  # fs_world.Workspace providing the real items
        self.spec_path = self.root / 'view.json'
        if create:
            self.root.mkdir(parents=True, exist_ok=False)
            self._write(spec or {})

    def _read(self):
        return json.loads(self.spec_path.read_text(encoding='utf-8'))

    def _write(self, spec):
        tmp = self.spec_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(spec, indent=1, sort_keys=True), encoding='utf-8')
        tmp.replace(self.spec_path)

    @staticmethod
    def attrs_of(spec, obj):
        if is_value(obj):
            k, v = obj.split(':', 1)
            return {'kind': k, 'filter': '-', 'sort': '-', 'group': '-', 'value': v}
        p = spec.get(obj)
        if p is None:
            return dict(BLANK)
        return {'kind': p['kind'], 'filter': p['filter'], 'sort': p['sort'], 'group': p['group'], 'value': '-'}

    def universe(self, paths=()):
        return sorted(set(PANELS) | set(VALUE_OBJECTS) | set(paths))

    def observe(self, paths=()):
        spec = self._read()
        return {o: self.attrs_of(spec, o) for o in self.universe(paths)}

    @staticmethod
    def actions(universe):
        out = []
        for tool, ar in TOOLS.items():
            if ar == 1:
                out += [(tool, (a,)) for a in universe]
            else:
                out += [(tool, (a, b)) for a in universe for b in universe if a != b]
        return out

    def execute(self, tool, args, capabilities):
        t0 = time.perf_counter()
        if tool not in TOOLS or len(args) != TOOLS[tool] or len(set(args)) != len(args):
            raise ValueError('invalid action')
        cap = CAPABILITY.get(tool)
        if cap and not capabilities.get(cap):
            return {'ok': False, 'blocked': True, 'error': f'capability {cap} not granted', 'ms': 0.0}
        spec = self._read()
        ok = self._compare(spec, *args, drift=self.drift) if tool == 'compare' else getattr(self, '_' + tool)(spec, *args)
        if ok:
            self._write(spec)
        return {'ok': bool(ok), 'blocked': False, 'error': '' if ok else 'precondition', 'ms': (time.perf_counter() - t0) * 1000}

    # --- tool semantics (the renderer's rules) ---
    @staticmethod
    def _open(spec, p):
        if p not in PANELS or p in spec:
            return False
        spec[p] = {'kind': 'panel', 'filter': 'all', 'sort': 'name', 'group': 'none'}
        return True

    @staticmethod
    def _close(spec, p):
        if p not in spec:
            return False
        del spec[p]
        return True

    @staticmethod
    def _filter(spec, p, v):
        if spec.get(p, {}).get('kind') != 'panel' or not v.startswith('ext:'):
            return False
        spec[p]['filter'] = v[4:]
        return True

    @staticmethod
    def _sort(spec, p, k):
        if p not in spec or not k.startswith('key:'):
            return False
        spec[p]['sort'] = k[4:]
        return True

    @staticmethod
    def _group(spec, p, g):
        if spec.get(p, {}).get('kind') != 'panel' or not g.startswith('grp:'):
            return False
        if g != 'grp:none' and spec[p]['filter'] != 'all':      # grouping by ext needs the unfiltered list
            return False
        spec[p]['group'] = g[4:]
        return True

    @staticmethod
    def _compare(spec, c, p, drift=frozenset()):
        replace = 'compare_replace' in drift and spec.get(c, {}).get('kind') == 'compare'   # P8b changed world
        if c not in PANELS or (c in spec and not replace) or spec.get(p, {}).get('kind') != 'panel':
            return False
        spec[c] = {'kind': 'compare', 'filter': spec[p]['filter'], 'sort': spec[p]['sort'], 'group': 'none'}
        return True
